import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

host = os.getenv('DB_HOST')
port = int(os.getenv('DB_PORT', 3306))
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
database = os.getenv('DB_NAME')

conn = mysql.connector.connect(
    host=host,
    port=port,
    user=user,
    password=password,
    database=database,
    charset="utf8mb4"
)

cursor = conn.cursor()

script_path = os.path.join(os.path.dirname(__file__), 'create_table_anima_selo.sql')
with open(script_path, 'r', encoding='utf-8') as f:
    sql_script = f.read()

statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]

for stmt in statements:
    clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith('--')]
    clean_stmt = '\n'.join(clean_lines).strip()
    if clean_stmt:
        print(f"Executando:\n{clean_stmt[:70]}...")
        cursor.execute(clean_stmt)

conn.commit()
print("[OK] Tabelas anima_selo e anima_usuario_selo criadas com sucesso!")

cursor.execute("SHOW TABLES LIKE 'anima%selo%'")
print("Tabelas encontradas:", [r[0] for r in cursor.fetchall()])

cursor.close()
conn.close()
