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
    print("1. Verificando collation de anima_usuario_discord.discord_user_id...")
    cur.execute("SHOW FULL COLUMNS FROM anima_usuario_discord WHERE Field = 'discord_user_id'")
    user_col = cur.fetchone()
    user_col_collation = user_col.get('Collation', 'utf8mb4_unicode_ci')

    print("2. Recriando tabela 'anima_usuario_temas_interesse' apontando para 'anima_usuario_discord'...")
    cur.execute("DROP TABLE IF EXISTS anima_usuario_temas_interesse;")
    
    create_sql = f"""
        CREATE TABLE anima_usuario_temas_interesse (
            discord_user_id VARCHAR(25) CHARACTER SET utf8mb4 COLLATE {user_col_collation} NOT NULL,
            temas_interesse_id INT(11) NOT NULL,
            data_associacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (discord_user_id, temas_interesse_id),
            CONSTRAINT fk_autid_user FOREIGN KEY (discord_user_id) REFERENCES anima_usuario_discord(discord_user_id) ON DELETE CASCADE ON UPDATE CASCADE,
            CONSTRAINT fk_autid_tema FOREIGN KEY (temas_interesse_id) REFERENCES anima_temas_interesse(temas_interesse_id) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cur.execute(create_sql)
    conn.commit()
    print("[SUCESSO] Tabela 'anima_usuario_temas_interesse' recriada e associada com sucesso ao 'anima_usuario_discord'!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
