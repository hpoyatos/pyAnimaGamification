import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST', 'db'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME', 'anima'),
    charset="utf8mb4"
)
cur = conn.cursor(dictionary=True)

try:
    print("1. Adicionando coluna 'discord_role_id' em 'anima_temas_interesse' se não existir...")
    cur.execute("""
        SELECT COUNT(*) AS total 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
          AND TABLE_NAME = 'anima_temas_interesse' 
          AND COLUMN_NAME = 'discord_role_id'
    """)
    res = cur.fetchone()
    if res and res['total'] == 0:
        cur.execute("ALTER TABLE anima_temas_interesse ADD COLUMN discord_role_id VARCHAR(20) NULL AFTER temas_interesse_descricao")
        print("Coluna 'discord_role_id' adicionada com sucesso!")
    else:
        print("Coluna 'discord_role_id' já existe em 'anima_temas_interesse'.")

    print("2. Vinculando o cargo de IA (1212540672482222151) ao tema correspondente...")
    cur.execute("""
        UPDATE anima_temas_interesse
        SET discord_role_id = '1212540672482222151'
        WHERE temas_interesse_nome LIKE '%Inteligência Artificial%' 
           OR temas_interesse_nome LIKE '%IA%' 
           OR temas_interesse_tag = 'IA'
    """)
    linhas_afetadas = cur.rowcount
    conn.commit()
    print(f"Sucesso! {linhas_afetadas} tema(s) de IA atualizado(s) com a role 1212540672482222151.")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
