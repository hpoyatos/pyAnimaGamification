import os
import sys
from datetime import datetime
import pandas as pd
import pymysql
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env')

CSV_PATH = '/home/hpoyatos/CodeProjects/pyAnimaGamification/arquivos/HENRIQUE RUIZ POYATOS NETO_25102026_113615.csv'
UC_ID = 1
PONTUACAO_VALOR = 2.0
DESCRICAO = 'Realizou o curso da Cisco Fundamentos de Análise de Dados'

def main():
    print(f"Lendo CSV: {CSV_PATH}")
    
    # Tentativa de leitura com encodings comuns
    df = None
    for enc in ['latin1', 'cp1252', 'iso-8859-1', 'utf-8']:
        try:
            df = pd.read_csv(CSV_PATH, sep=';', encoding=enc)
            print(f"Arquivo lido com sucesso usando encoding '{enc}'.")
            break
        except Exception as e:
            continue
            
    if df is None:
        print("Erro: Não foi possível ler o arquivo CSV com nenhum encoding testado.")
        sys.exit(1)

    # Identificar colunas A (índice 0) e E (índice 4)
    col_a = df.columns[0]
    col_e = df.columns[4]
    
    print(f"Coluna A: '{col_a}'")
    print(f"Coluna E: '{col_e}'")
    
    # Filtrar onde a coluna E é '100%'
    # Remover espaços em branco extras
    df_filtrado = df[df[col_e].astype(str).str.strip() == '100%']
    print(f"Total de registros com 100%: {len(df_filtrado)}")
    
    # Conexão com o banco MariaDB
    conn = pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        port=int(os.getenv('DB_PORT', 3306)),
        charset='utf8mb4',
        autocommit=False
    )
    
    cursor = conn.cursor()
    agora = datetime.now()
    
    inseridos = 0
    nao_encontrados = []
    ja_existentes = 0
    
    try:
        for idx, row in df_filtrado.iterrows():
            nome_aluno = str(row[col_a]).strip()
            
            # Buscar usuario_id procurando usuario_nome exato
            cursor.execute("SELECT usuario_id FROM usuario WHERE usuario_nome = %s", (nome_aluno,))
            res = cursor.fetchone()
            
            if not res:
                nao_encontrados.append(nome_aluno)
                continue
                
            usuario_id = res[0]
            
            # Verificar se já recebeu essa pontuação específica para evitar duplicidade
            cursor.execute(
                """
                SELECT pontuacao_id FROM pontuacao 
                WHERE usuario_id = %s AND uc_id = %s AND pontuacao_descricao = %s
                """,
                (usuario_id, UC_ID, DESCRICAO)
            )
            ponto_existente = cursor.fetchone()
            
            if ponto_existente:
                ja_existentes += 1
                continue
            
            # Inserir pontuação
            cursor.execute(
                """
                INSERT INTO pontuacao (usuario_id, uc_id, pontuacao, data_pontuacao, pontuacao_descricao)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (usuario_id, UC_ID, PONTUACAO_VALOR, agora, DESCRICAO)
            )
            inseridos += 1
            
        conn.commit()
        print("\n=== RESUMO DO PROCESSAMENTO ===")
        print(f"Novas pontuações inseridas: {inseridos}")
        print(f"Já haviam sido pontuados anteriormente: {ja_existentes}")
        print(f"Alunos não encontrados no banco: {len(nao_encontrados)}")
        if nao_encontrados:
            print("Lista de alunos não encontrados:")
            for n in nao_encontrados:
                print(f" - {n}")
                
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a execução: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
