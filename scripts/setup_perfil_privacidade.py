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
    print("1. Inspecionando colunas de 'anima_usuario_discord'...")
    cur.execute("DESCRIBE anima_usuario_discord")
    cols = [r['Field'] for r in cur.fetchall()]

    new_cols = [
        ("linkedin_url", "VARCHAR(255) NULL"),
        ("instagram_user", "VARCHAR(100) NULL"),
        ("share_nome", "TINYINT(1) NOT NULL DEFAULT 1"),
        ("share_email_academico", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("share_email_pessoal", "TINYINT(1) NOT NULL DEFAULT 0"),
        ("share_linkedin", "TINYINT(1) NOT NULL DEFAULT 1"),
        ("share_instagram", "TINYINT(1) NOT NULL DEFAULT 1"),
        ("share_temas", "TINYINT(1) NOT NULL DEFAULT 1")
    ]

    for col_name, col_def in new_cols:
        if col_name not in cols:
            cur.execute(f"ALTER TABLE anima_usuario_discord ADD COLUMN {col_name} {col_def}")
            print(f"[OK] Coluna '{col_name}' adicionada com sucesso.")
        else:
            print(f"[INFO] Coluna '{col_name}' já existe.")

    conn.commit()
    print("[SUCESSO] Migração de perfil e privacidade concluída com sucesso!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
