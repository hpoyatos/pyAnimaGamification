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
    
    if 'curso_idioma' not in cols:
        cur.execute("ALTER TABLE curso ADD COLUMN curso_idioma VARCHAR(20) DEFAULT 'pt-br' AFTER curso_carga_horaria")
        print("[OK] Coluna 'curso_idioma' adicionada na tabela 'curso'.")
    else:
        print("[INFO] Coluna 'curso_idioma' já existe.")

    # Atualiza idiomas dos cursos conhecidos em inglês
    cur.execute("UPDATE curso SET curso_idioma = 'en-us' WHERE curso_nome LIKE '%Essentials with Python%' OR curso_nome LIKE '%Red Hat System Administration%'")
    cur.execute("UPDATE curso SET curso_idioma = 'pt-br' WHERE curso_idioma IS NULL")

    conn.commit()
    print("[OK] Idiomas atualizados com sucesso no banco!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
