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
    cur.execute("DESCRIBE curso")
    cols = [r['Field'] for r in cur.fetchall()]
    
    if 'curso_prerequisito_id' not in cols:
        cur.execute("""
            ALTER TABLE curso 
            ADD COLUMN curso_prerequisito_id INT(11) NULL AFTER curso_idioma,
            ADD CONSTRAINT fk_curso_prerequisito FOREIGN KEY (curso_prerequisito_id) REFERENCES curso(curso_id) ON DELETE SET NULL
        """)
        print("[OK] Coluna 'curso_prerequisito_id' e Foreign Key adicionadas com sucesso.")
    else:
        print("[INFO] Coluna 'curso_prerequisito_id' já existe.")

    # Exemplo: AWS Cloud Architecting (3) e Developing (4) têm Foundations (2) como pré-requisito
    cur.execute("UPDATE curso SET curso_prerequisito_id = 2 WHERE curso_id IN (3, 4, 5) AND curso_prerequisito_id IS NULL")

    conn.commit()
    print("[OK] Pré-requisitos de exemplo configurados com sucesso!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
