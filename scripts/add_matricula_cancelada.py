import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset="utf8mb4"
)
cur = conn.cursor(dictionary=True)

try:
    # 1. Atualiza o ENUM de situacao para incluir 'Cancelado'
    cur.execute("""
        ALTER TABLE usuario_curso 
        MODIFY COLUMN usuario_curso_situacao 
        ENUM('Pendente','Inscrito','Concluído','Validado','Creditado','Cancelado') 
        NOT NULL DEFAULT 'Pendente'
    """)
    print("[OK] ENUM de 'usuario_curso_situacao' atualizado para incluir 'Cancelado'.")

    # 2. Adiciona a coluna usuario_curso_motivo se não existir
    cur.execute("DESCRIBE usuario_curso")
    cols = [r['Field'] for r in cur.fetchall()]
    
    if 'usuario_curso_motivo' not in cols:
        cur.execute("ALTER TABLE usuario_curso ADD COLUMN usuario_curso_motivo TEXT NULL AFTER usuario_curso_situacao")
        print("[OK] Coluna 'usuario_curso_motivo' adicionada com sucesso.")
    else:
        print("[INFO] Coluna 'usuario_curso_motivo' já existe.")

    conn.commit()

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
