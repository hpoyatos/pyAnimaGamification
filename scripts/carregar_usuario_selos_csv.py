import os
import sys
import glob
import time
import requests
import pandas as pd
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

ARQUIVOS_DIR = os.path.join(os.path.dirname(__file__), '..', 'arquivos')
ACELERADORA_CHANNEL_ID = os.getenv("DISCORD_ACELERADORA_CHANNEL_ID", "1551244523152216166")

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset="utf8mb4"
    )

def enviar_congratulacao_discord(aluno_identificacao: str, selo_nome: str):
    """
    Envia mensagem no canal de #aceleradora pelo bot JocastaBOT.
    Ex: Parabéns @fulano pela conquista do selo "[NOME DO SELO]"! 🎖️🎉
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("[AVISO] DISCORD_BOT_TOKEN não configurado no .env. Notificação Discord ignorada.")
        return False

    url = f"https://discord.com/api/v10/channels/{ACELERADORA_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    conteudo = f"Parabéns {aluno_identificacao} pela conquista do selo \"{selo_nome}\"! 🎖️🎉"
    payload = {"content": conteudo}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code in (200, 201):
            print(f"  [DISCORD OK] {conteudo}")
            return True
        else:
            print(f"  [DISCORD ERRO] ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"  [DISCORD ERRO] Exceção: {e}")
        return False

def obter_arquivos_csv():
    """
    Retorna a lista de caminhos de arquivos CSV a serem processados via CLI.
    """
    if len(sys.argv) > 1:
        param = sys.argv[1]
        if os.path.isabs(param) or os.path.exists(param):
            candidato = param
        else:
            candidato = os.path.join(ARQUIVOS_DIR, param)

        if not os.path.exists(candidato):
            print(f"[ERRO] Arquivo especificado não encontrado: {candidato}")
            sys.exit(1)
        return [candidato]

    padrao = os.path.join(ARQUIVOS_DIR, "ql-group_activity-report*.csv")
    encontrados = sorted(glob.glob(padrao))
    if not encontrados:
        print(f"[ERRO] Nenhum arquivo correspondente a '{padrao}' encontrado.")
        sys.exit(1)
    return encontrados

def processar_arquivos_csv_selos(lista_caminhos_csv, logger_callback=print):
    """
    Função reutilizável tanto pelo terminal (CLI) quanto por comandos do Discord.
    Recebe uma lista de caminhos para CSVs e executa a carga e congratulação.
    Retorna um dicionário com estatísticas e mensagens.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Obter selos cadastrados no banco
    cursor.execute("SELECT selo_id, selo_nome FROM anima_selo")
    selos = cursor.fetchall()
    selo_dict = {s['selo_nome'].strip(): s['selo_id'] for s in selos}
    logger_callback(f"Selos mapeados no catálogo ({len(selo_dict)}).")

    # 2. Mapear usuários para busca por e-mail e dados do Discord
    cursor.execute("""
        SELECT 
            usuario_id, 
            usuario_nome, 
            usuario_email, 
            usuario_email_pessoal, 
            usuario_discord_id, 
            usuario_discord_name 
        FROM usuario
    """)
    usuarios = cursor.fetchall()

    cursor.execute("""
        SELECT usuario_id, usuario_redhat_email 
        FROM usuario_curso 
        WHERE usuario_redhat_email IS NOT NULL AND usuario_redhat_email != ''
    """)
    usuario_cursos = cursor.fetchall()

    email_to_uid = {}
    user_info_map = {}

    for u in usuarios:
        uid = u['usuario_id']
        user_info_map[uid] = u
        if u['usuario_email']:
            email_to_uid[u['usuario_email'].strip().lower()] = uid
        if u['usuario_email_pessoal']:
            email_to_uid[u['usuario_email_pessoal'].strip().lower()] = uid

    for uc in usuario_cursos:
        uid = uc['usuario_id']
        if uc['usuario_redhat_email']:
            em = uc['usuario_redhat_email'].strip().lower()
            if em not in email_to_uid:
                email_to_uid[em] = uid

    # 3. Obter selos JÁ CADASTRADOS no banco para checagem prévia
    cursor.execute("SELECT usuario_id, selo_id FROM anima_usuario_selo")
    selos_existentes = set((r['usuario_id'], r['selo_id']) for r in cursor.fetchall())

    insert_query = """
        INSERT INTO anima_usuario_selo (usuario_id, selo_id, usuario_selo_data)
        VALUES (%s, %s, %s)
    """

    total_novos_inseridos = 0
    total_ja_existentes = 0
    total_congratulacoes = 0
    todos_nao_encontrados = set()
    detalhes_novos = []

    for caminho_csv in lista_caminhos_csv:
        nome_arquivo = os.path.basename(caminho_csv)
        logger_callback(f"Lendo e processando: {nome_arquivo}")
        df = pd.read_csv(caminho_csv)

        # Filtrar passed == True e Activity no catálogo
        passed_mask = df['Passed'].astype(str).str.strip().str.lower() == 'true'
        activity_mask = df['Activity'].isin(selo_dict.keys())
        filtered_df = df[passed_mask & activity_mask].copy()

        filtered_df['parsed_date'] = pd.to_datetime(filtered_df['Date completed'], errors='coerce')
        filtered_df['formatted_date'] = filtered_df['parsed_date'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Ordenar por data cronológica
        filtered_df = filtered_df.sort_values(by='parsed_date', ascending=True)

        for _, row in filtered_df.iterrows():
            raw_email = str(row['Member']).strip().lower()
            activity = row['Activity'].strip()
            selo_id = selo_dict.get(activity)
            data_selo = row['formatted_date'] if pd.notnull(row['formatted_date']) else None

            usuario_id = email_to_uid.get(raw_email)
            if not usuario_id:
                todos_nao_encontrados.add(raw_email)
                continue

            # Checagem prévia: só insere se não existir
            if (usuario_id, selo_id) in selos_existentes:
                total_ja_existentes += 1
                continue

            # Inserção do novo selo
            cursor.execute(insert_query, (usuario_id, selo_id, data_selo))
            conn.commit()

            selos_existentes.add((usuario_id, selo_id))
            total_novos_inseridos += 1

            # Resolver identificação no Discord
            u_data = user_info_map.get(usuario_id, {})
            discord_id = str(u_data.get('usuario_discord_id') or '').strip()
            discord_name = u_data.get('usuario_discord_name')
            nome_real = u_data.get('usuario_nome')

            if discord_id.isdigit():
                aluno_tag = f"<@{discord_id}>"
            elif discord_name:
                aluno_tag = f"@{discord_name}"
            else:
                aluno_tag = nome_real or "Aluno"

            detalhes_novos.append({
                "aluno": aluno_tag,
                "nome_real": nome_real,
                "selo": activity
            })

            enviou = enviar_congratulacao_discord(aluno_tag, activity)
            if enviou:
                total_congratulacoes += 1
                time.sleep(1.0)  # Rate limit do Discord

    cursor.close()
    conn.close()

    resultado = {
        "novos_inseridos": total_novos_inseridos,
        "ja_existentes": total_ja_existentes,
        "congratulacoes_enviadas": total_congratulacoes,
        "nao_encontrados": list(todos_nao_encontrados),
        "detalhes_novos": detalhes_novos
    }
    return resultado

def main():
    arquivos_csv = obter_arquivos_csv()
    print("=" * 60)
    print(f"Arquivos CSV a processar ({len(arquivos_csv)}):")
    for f in arquivos_csv:
        print(f"  • {os.path.basename(f)}")
    print("=" * 60)

    resultado = processar_arquivos_csv_selos(arquivos_csv, logger_callback=print)

    print("\n" + "=" * 60)
    print("RESUMO FINAL DA EXECUÇÃO:")
    print(f"  • Selos já existentes ignorados: {resultado['ja_existentes']}")
    print(f"  • Novos selos cadastrados: {resultado['novos_inseridos']}")
    print(f"  • Mensagens de congratulações enviadas pela Jocasta: {resultado['congratulacoes_enviadas']}")
    if resultado['nao_encontrados']:
        print(f"  • E-mails não localizados ({len(resultado['nao_encontrados'])}):")
        for ne in sorted(resultado['nao_encontrados']):
            print(f"    - {ne}")
    print("=" * 60)

if __name__ == '__main__':
    main()
