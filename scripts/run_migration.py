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

with open('sql/kahoot_schema.sql', 'r', encoding='utf-8') as f:
    sql_script = f.read()

# Filter out comments and split by semicolon
statements = [stmt.strip() for stmt in sql_script.split(';') if stmt.strip()]

for stmt in statements:
    # ignore empty lines or comments
    clean_lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
    clean_stmt = '\n'.join(clean_lines).strip()
    if clean_stmt:
        print(f"Executando:\n{clean_stmt[:60]}...")
        cursor.execute(clean_stmt)

conn.commit()
print("[OK] Todas as tabelas foram criadas com sucesso!")

cursor.execute("SHOW TABLES LIKE 'anima_quiz%'")
print("Tabelas de Quiz:", [r[0] for r in cursor.fetchall()])

cursor.execute("SHOW TABLES LIKE 'anima_usuario_discord'")
print("Tabela Usuario Discord:", [r[0] for r in cursor.fetchall()])

cursor.close()
conn.close()
