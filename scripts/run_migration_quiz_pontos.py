import os
import sys
import mysql.connector
from dotenv import load_dotenv

def run_migration():
    load_dotenv()
    host = os.getenv("DB_HOST", "db")
    port = int(os.getenv("DB_PORT", "3306"))
    database = os.getenv("DB_NAME", "anima")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    print(f"Conectando ao banco {database} em {host}:{port}...")
    conn = mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci"
    )
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SHOW COLUMNS FROM anima_quiz")
        existing_cols = {col['Field'] for col in cur.fetchall()}
        print(f"Colunas em anima_quiz: {sorted(list(existing_cols))}")

        columns_to_add = [
            ("pontos_1_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 1.00"),
            ("pontos_2_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 1.00"),
            ("pontos_3_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 1.00"),
            ("pontos_4_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.80"),
            ("pontos_5_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.80"),
            ("pontos_6_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.80"),
            ("pontos_7_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.50"),
            ("pontos_8_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.50"),
            ("pontos_9_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.50"),
            ("pontos_10_lugar", "DECIMAL(5,2) NOT NULL DEFAULT 0.50")
        ]

        for col_name, col_def in columns_to_add:
            if col_name not in existing_cols:
                sql = f"ALTER TABLE anima_quiz ADD COLUMN `{col_name}` {col_def};"
                print(f"Executando: {sql}")
                cur.execute(sql)
            else:
                print(f"Coluna {col_name} ja existe.")

        conn.commit()
        print("Migracao concluida com sucesso!")

    except Exception as e:
        conn.rollback()
        print(f"Erro na migracao: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    run_migration()
