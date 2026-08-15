import os
import requests
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
    print("1. Criando tabela 'anima_discord_role' se não existir...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `anima_discord_role` (
            `role_id` CHAR(20) NOT NULL,
            `role_descricao` VARCHAR(150) NOT NULL,
            `role_created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`role_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # 2. Busca todas as roles da guilda no Discord via REST API
    token = os.getenv("DISCORD_BOT_TOKEN")
    discord_roles_map = {}
    if token:
        headers = {"Authorization": f"Bot {token}"}
        try:
            res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
            if res_guilds.status_code == 200:
                guilds = res_guilds.json()
                for g in guilds:
                    g_id = g['id']
                    res_roles = requests.get(f"https://discord.com/api/v10/guilds/{g_id}/roles", headers=headers)
                    if res_roles.status_code == 200:
                        for r in res_roles.json():
                            if r['name'] != '@everyone':
                                discord_roles_map[str(r['id'])] = r['name']
            print(f"[OK] {len(discord_roles_map)} roles obtidas da API do Discord.")
        except Exception as e_api:
            print(f"[AVISO] Falha ao consultar API do Discord: {e_api}")

    # 3. Coleta todos os role_ids presentes nas tabelas existentes
    tables_queries = [
        ("anima_curso", "SELECT DISTINCT curso_role AS rid FROM anima_curso WHERE curso_role IS NOT NULL AND curso_role != ''"),
        ("anima_ies", "SELECT DISTINCT ies_discord_role AS rid FROM anima_ies WHERE ies_discord_role IS NOT NULL AND ies_discord_role != ''"),
        ("anima_uc", "SELECT DISTINCT uc_discord_role AS rid FROM anima_uc WHERE uc_discord_role IS NOT NULL AND uc_discord_role != ''"),
        ("curso", "SELECT DISTINCT curso_role AS rid FROM curso WHERE curso_role IS NOT NULL AND curso_role != ''"),
        ("uc", "SELECT DISTINCT uc_role_id AS rid FROM uc WHERE uc_role_id IS NOT NULL AND uc_role_id != ''")
    ]

    referenced_role_ids = set()
    for tbl, q in tables_queries:
        try:
            cur.execute(q)
            for row in cur.fetchall():
                rid = str(row['rid']).strip()
                if rid:
                    referenced_role_ids.add(rid)
        except Exception as e:
            print(f"[INFO] Tabela {tbl} sem consulta: {e}")

    print(f"Total de role_ids únicos referenciados nas tabelas: {len(referenced_role_ids)}")

    # 4. Popula anima_discord_role com todas as roles do Discord e todas as referenciadas
    all_role_ids = set(discord_roles_map.keys()).union(referenced_role_ids)
    
    insert_sql = """
        INSERT INTO anima_discord_role (role_id, role_descricao)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE role_descricao = VALUES(role_descricao)
    """

    for rid in all_role_ids:
        # Se veio do Discord, pega o nome real, senão cria uma descrição padrão
        desc = discord_roles_map.get(rid, f"Cargo Discord {rid}")
        cur.execute(insert_sql, (rid, desc))

    conn.commit()
    print(f"[OK] {len(all_role_ids)} roles inseridas/atualizadas na tabela 'anima_discord_role'.")

    # 5. Ajusta tipos das colunas para CHAR(20) e adiciona Foreign Keys
    cur.execute("ALTER TABLE curso MODIFY COLUMN curso_role CHAR(20) NULL;")
    cur.execute("ALTER TABLE anima_uc MODIFY COLUMN uc_discord_role CHAR(20) NOT NULL;")
    
    # Adiciona Foreign Keys com proteção
    fk_configs = [
        ("curso", "fk_curso_discord_role", "ALTER TABLE curso ADD CONSTRAINT fk_curso_discord_role FOREIGN KEY (curso_role) REFERENCES anima_discord_role(role_id) ON DELETE SET NULL ON UPDATE CASCADE;"),
        ("anima_uc", "fk_animauc_discord_role", "ALTER TABLE anima_uc ADD CONSTRAINT fk_animauc_discord_role FOREIGN KEY (uc_discord_role) REFERENCES anima_discord_role(role_id) ON DELETE RESTRICT ON UPDATE CASCADE;"),
        ("anima_ies", "fk_animaies_discord_role", "ALTER TABLE anima_ies ADD CONSTRAINT fk_animaies_discord_role FOREIGN KEY (ies_discord_role) REFERENCES anima_discord_role(role_id) ON DELETE SET NULL ON UPDATE CASCADE;"),
        ("anima_curso", "fk_animacurso_discord_role", "ALTER TABLE anima_curso ADD CONSTRAINT fk_animacurso_discord_role FOREIGN KEY (curso_role) REFERENCES anima_discord_role(role_id) ON DELETE SET NULL ON UPDATE CASCADE;")
    ]

    for tbl, fk_name, alter_sql in fk_configs:
        try:
            # Verifica se a FK já existe
            cur.execute(f"""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{tbl}' AND CONSTRAINT_NAME = '{fk_name}'
            """)
            if not cur.fetchone():
                cur.execute(alter_sql)
                print(f"[OK] Foreign Key '{fk_name}' adicionada na tabela '{tbl}'.")
            else:
                print(f"[INFO] Foreign Key '{fk_name}' já existe na tabela '{tbl}'.")
        except Exception as e_fk:
            print(f"[AVISO] Não foi possível adicionar FK '{fk_name}' em '{tbl}': {e_fk}")

    conn.commit()
    print("[SUCESSO] Migração e sincronização de roles concluídas com sucesso!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO GERAL] {e}")
finally:
    cur.close()
    conn.close()
