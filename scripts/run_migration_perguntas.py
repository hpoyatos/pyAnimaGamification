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

migration_file = 'sql/banco_perguntas_migration.sql'
with open(migration_file, 'r', encoding='utf-8') as f:
    sql_script = f.read()

statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]

for stmt in statements:
    clean_lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
    clean_stmt = '\n'.join(clean_lines).strip()
    if clean_stmt:
        print(f"Executando:\n{clean_stmt[:70]}...")
        cursor.execute(clean_stmt)

conn.commit()
print("[OK] Banco de Perguntas migrado com sucesso no MariaDB!")

cursor.execute("SHOW TABLES LIKE 'anima_pergunta%'")
print("Tabelas pergunta:", [r[0] for r in cursor.fetchall()])

cursor.execute("SHOW TABLES LIKE 'anima_quiz_pergunta%'")
print("Tabelas quiz pergunta:", [r[0] for r in cursor.fetchall()])

cursor.close()
conn.close()
