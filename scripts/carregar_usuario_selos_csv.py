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

def enviar_dm_congratulacao(discord_id: str, nome_real: str, selos: list):
    """
    Envia uma mensagem privada (DM) da Jocasta para o aluno parabenizando pela conquista.
    Formato clássico e personalizado.
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token or not discord_id or not discord_id.isdigit():
        return False

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Abrir canal de DM com o usuário
        dm_channel_url = "https://discord.com/api/v10/users/@me/channels"
        res_dm = requests.post(dm_channel_url, headers=headers, json={"recipient_id": discord_id}, timeout=10)
        if res_dm.status_code not in (200, 201):
            return False

        channel_id = res_dm.json().get("id")
        if not channel_id:
            return False

        # 2. Montar mensagem no formato solicitado
        if len(selos) == 1:
            texto_dm = f"Parabéns <@{discord_id}> pela conquista do selo **\"{selos[0]}\"**! 🎖️🎉"
        else:
            selos_formatados = "\n".join([f"  • **{s}**" for s in selos])
            texto_dm = f"Parabéns <@{discord_id}> pela conquista dos seguintes selos! 🎖️🎉\n\n{selos_formatados}"

        embed = {
            "title": "🎖️ Conquista de Selo Reconhecida!",
            "description": (
                f"Olá **{nome_real or 'Aluno'}**!\n\n"
                f"{texto_dm}\n\n"
                f"Você pode consultar todos os seus selos conquistados a qualquer momento usando o comando `/meus_selos`."
            ),
            "color": 0x4285F4,
            "footer": {
                "text": "pyAnimaGamification • Google Cloud Skills Boost"
            }
        }

        # 3. Enviar mensagem na DM
        send_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        res_msg = requests.post(send_url, headers=headers, json={"embeds": [embed]}, timeout=10)
        return res_msg.status_code in (200, 201)
    except Exception as e:
        print(f"  [DM ERRO] Falha ao enviar DM para {discord_id}: {e}")
        return False

def enviar_congratulacoes_em_lote_discord(detalhes_novos: list):
    """
    1) Envia UMA ÚNICA mensagem no canal #aceleradora listando todos os alunos e seus novos selos (evita flood).
    2) Envia adicionalmente uma mensagem privada (DM) para cada um dos alunos congratulados.
    """
    if not detalhes_novos:
        return True

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("[AVISO] DISCORD_BOT_TOKEN não configurado no .env. Notificação Discord ignorada.")
        return False

    url = f"https://discord.com/api/v10/channels/{ACELERADORA_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    # Agrupar selos por aluno (tag, discord_id, nome_real)
    aluno_selos = {}
    aluno_info = {}

    for d in detalhes_novos:
        tag = d["aluno"]
        selo = d["selo"]
        did = d.get("discord_id")
        nreal = d.get("nome_real")

        if tag not in aluno_selos:
            aluno_selos[tag] = []
            aluno_info[tag] = {"discord_id": did, "nome_real": nreal}
        aluno_selos[tag].append(selo)

    linhas = []
    for tag, selos in aluno_selos.items():
        if len(selos) == 1:
            linhas.append(f"• {tag} conquistou o selo **\"{selos[0]}\"**! 🎖️")
        else:
            selos_str = ", ".join([f'"{s}"' for s in selos])
            linhas.append(f"• {tag} conquistou os selos: **{selos_str}**! 🎖️")

    corpo = "\n".join(linhas)

    embed = {
        "title": "🎉 Parabéns pelas Novas Conquistas de Selos! 🎖️",
        "description": f"Novos selos foram registrados na turma da Aceleradora:\n\n{corpo}",
        "color": 0x4285F4,
        "footer": {
            "text": "pyAnimaGamification • Google Cloud Skills Boost"
        }
    }

    try:
        # 1. Postagem pública única
        response = requests.post(url, headers=headers, json={"embeds": [embed]}, timeout=15)
        if response.status_code in (200, 201):
            print(f"[DISCORD OK] Congratulação em lista publicada para {len(aluno_selos)} aluno(s)!")
        else:
            print(f"[DISCORD ERRO] Falha ao enviar lista de congratulações ({response.status_code}): {response.text}")

        # 2. Envio de mensagem privada (DM) para cada aluno
        for tag, selos in aluno_selos.items():
            info = aluno_info.get(tag, {})
            did = info.get("discord_id")
            nreal = info.get("nome_real")
            if did:
                sucesso_dm = enviar_dm_congratulacao(did, nreal, selos)
                if sucesso_dm:
                    print(f"  [DM OK] Mensagem privada enviada para {nreal} ({did})")
                time.sleep(0.5)

        return True
    except Exception as e:
        print(f"[DISCORD ERRO] Exceção ao enviar congratulações: {e}")
        return False

def postar_ranking_discord():
    """
    Posta o ranking de selos atualizado no canal #aceleradora via API do Discord.
    Separa alunos com 9 selos em Hors-Concours e lista o Top 10 (< 9 selos).
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        return False

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT 
            u.usuario_id,
            u.usuario_nome,
            u.usuario_discord_id,
            u.usuario_discord_name,
            COUNT(aus.selo_id) AS total_selos,
            MIN(aus.usuario_selo_data) AS primeiro_selo,
            GROUP_CONCAT(s.selo_nome ORDER BY aus.usuario_selo_data ASC SEPARATOR '||') AS selos_nomes
        FROM anima_usuario_selo aus
        INNER JOIN usuario u ON u.usuario_id = aus.usuario_id
        INNER JOIN anima_selo s ON s.selo_id = aus.selo_id
        GROUP BY u.usuario_id, u.usuario_nome, u.usuario_discord_id, u.usuario_discord_name
        ORDER BY total_selos DESC, primeiro_selo ASC
    """)
    todos = cur.fetchall() or []
    cur.close()
    conn.close()

    hors_concours = [u for u in todos if u['total_selos'] >= 9]
    ranking_top10 = [u for u in todos if u['total_selos'] < 9][:10]

    fields = []

    # Seção Hors-Concours
    if hors_concours:
        hc_linhas = []
        for h in hors_concours:
            uid_str = str(h.get("usuario_discord_id") or "").strip()
            mention = f"<@{uid_str}>" if uid_str.isdigit() else (h.get("usuario_discord_name") or h.get("usuario_nome"))
            hc_linhas.append(f"👑 **{h.get('usuario_nome')}** ({mention}) — **{h.get('total_selos')} selos** (Trilha Completa!)")

        fields.append({
            "name": "🌟 Hors-Concours (Trilha Concluída - 9 Selos)",
            "value": "\n".join(hc_linhas),
            "inline": False
        })

    medalhas = {1: "🥇", 2: "🥈", 3: "🥉"}

    for pos, r in enumerate(ranking_top10, 1):
        icone = medalhas.get(pos, f"`#{pos:02d}`")
        uid_str = str(r.get("usuario_discord_id") or "").strip()
        nome_real = r.get("usuario_nome") or "Aluno"
        discord_fallback = r.get("usuario_discord_name") or "Desconhecido"
        total = r.get("total_selos") or 0

        member_mention = f"<@{uid_str}>" if uid_str.isdigit() else f"@{discord_fallback}"
        primeiro_data_str = ""
        if r.get("primeiro_selo"):
            primeiro_data_str = f"1º selo em `{r['primeiro_selo']:%d/%m/%Y}`"

        selos_lista = (r.get("selos_nomes") or "").split("||") if r.get("selos_nomes") else []
        selos_formatados = "\n".join([f"  └ 🔹 {s}" for s in selos_lista])

        campo_titulo = f"{icone} {nome_real} (@{discord_fallback}) — {total} selo{'s' if total != 1 else ''}"
        
        cabecalho_partes = []
        if uid_str.isdigit():
            cabecalho_partes.append(f"👤 {member_mention}")
        if primeiro_data_str:
            cabecalho_partes.append(f"⏱️ {primeiro_data_str}")

        cabecalho_corpo = " • ".join(cabecalho_partes)
        campo_valor = f"{cabecalho_corpo}\n{selos_formatados}" if cabecalho_corpo else selos_formatados

        if len(campo_valor) > 1024:
            campo_valor = campo_valor[:1000] + "\n  └ _... e mais selos_"

        fields.append({
            "name": campo_titulo,
            "value": campo_valor or "Nenhum detalhe",
            "inline": False
        })

    embed = {
        "title": "🏆 Ranking Geral de Selos e Conquistas (Top 10)",
        "description": "Critério: Quantidade de selos conquistados. Desempate: quem conquistou o primeiro selo mais cedo.\n*(Alunos com todos os 9 selos são homenageados como Hors-Concours)*\n",
        "color": 0xFFD700,
        "fields": fields,
        "footer": {
            "text": "pyAnimaGamification • Atualização Automática de Selos"
        }
    }

    url = f"https://discord.com/api/v10/channels/{ACELERADORA_CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(url, headers=headers, json={"embeds": [embed]}, timeout=15)
        if res.status_code in (200, 201):
            print("[DISCORD OK] Ranking geral postado automaticamente no canal #aceleradora!")
            return True
        else:
            print(f"[DISCORD ERRO] Falha ao postar ranking ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"[DISCORD ERRO] Exceção ao postar ranking: {e}")
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

def processar_arquivos_csv_selos(lista_caminhos_csv, logger_callback=print, postar_no_discord_ao_final=True):
    """
    Função reutilizável tanto pelo terminal (CLI) quanto por comandos do Discord.
    Recebe uma lista de caminhos para CSVs, executa a carga no banco.
    Se houver novos selos e postar_no_discord_ao_final=True:
      1) Envia UMA ÚNICA postagem em lista congratulando todos os alunos no canal público.
      2) Envia mensagem privada (DM) para cada aluno parabenizando-o.
      3) Publica o ranking atualizado com Hors-Concours e Top 10.
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
                "discord_id": discord_id if discord_id.isdigit() else None,
                "nome_real": nome_real,
                "selo": activity
            })

    cursor.close()
    conn.close()

    # 4. Enviar congratulações em postagem ÚNICA, DMs e publicar ranking se houver novos selos
    congratulou = False
    if postar_no_discord_ao_final:
        if total_novos_inseridos > 0:
            logger_callback("Novos selos cadastrados. Enviando congratulações pública (lista) e privadas (DM)...")
            congratulou = enviar_congratulacoes_em_lote_discord(detalhes_novos)
            time.sleep(1.0)
            logger_callback("Postando ranking atualizado no canal de aceleradora...")
            postar_ranking_discord()
        else:
            logger_callback("Nenhum novo selo inserido nesta execução. Postagens ignoradas para evitar flood.")

    resultado = {
        "novos_inseridos": total_novos_inseridos,
        "ja_existentes": total_ja_existentes,
        "congratulacoes_enviadas": len(detalhes_novos) if congratulou else 0,
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

    resultado = processar_arquivos_csv_selos(arquivos_csv, logger_callback=print, postar_no_discord_ao_final=True)

    print("\n" + "=" * 60)
    print("RESUMO FINAL DA EXECUÇÃO:")
    print(f"  • Selos já existentes ignorados: {resultado['ja_existentes']}")
    print(f"  • Novos selos cadastrados: {resultado['novos_inseridos']}")
    print(f"  • Conquistas listadas: {len(resultado['detalhes_novos'])}")
    if resultado['nao_encontrados']:
        print(f"  • E-mails não localizados ({len(resultado['nao_encontrados'])}):")
        for ne in sorted(resultado['nao_encontrados']):
            print(f"    - {ne}")
    print("=" * 60)

if __name__ == '__main__':
    main()
