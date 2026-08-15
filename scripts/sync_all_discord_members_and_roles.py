import os
import requests
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("[ERRO] DISCORD_BOT_TOKEN não configurado.")
    exit(1)

headers = {"Authorization": f"Bot {token}"}

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
    print("1. Adicionando coluna 'role_ativo' em 'anima_discord_role' se não existir...")
    cur.execute("DESCRIBE anima_discord_role")
    cols = [r['Field'] for r in cur.fetchall()]
    if 'role_ativo' not in cols:
        cur.execute("ALTER TABLE anima_discord_role ADD COLUMN role_ativo TINYINT(1) NOT NULL DEFAULT 1 AFTER role_descricao")
        print("[OK] Coluna 'role_ativo' adicionada com sucesso.")
    else:
        print("[INFO] Coluna 'role_ativo' já existe.")

    # 2. Obtem collation de discord_user_id e role_id
    cur.execute("SHOW FULL COLUMNS FROM anima_usuario_discord WHERE Field = 'discord_user_id'")
    user_col = cur.fetchone()
    user_col_collation = user_col.get('Collation', 'utf8mb4_unicode_ci')

    cur.execute("SHOW FULL COLUMNS FROM anima_discord_role WHERE Field = 'role_id'")
    role_col = cur.fetchone()
    role_col_collation = role_col.get('Collation', 'utf8mb4_general_ci')

    print(f"\n2. Criando tabela 'anima_usuario_discord_role' com collations compatíveis ({user_col_collation} / {role_col_collation})...")
    create_tbl_sql = f"""
        CREATE TABLE IF NOT EXISTS anima_usuario_discord_role (
            discord_user_id VARCHAR(25) CHARACTER SET utf8mb4 COLLATE {user_col_collation} NOT NULL,
            role_id CHAR(20) CHARACTER SET utf8mb4 COLLATE {role_col_collation} NOT NULL,
            data_associacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (discord_user_id, role_id),
            CONSTRAINT fk_audr_user FOREIGN KEY (discord_user_id) REFERENCES anima_usuario_discord(discord_user_id) ON DELETE CASCADE ON UPDATE CASCADE,
            CONSTRAINT fk_audr_role FOREIGN KEY (role_id) REFERENCES anima_discord_role(role_id) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cur.execute(create_tbl_sql)
    conn.commit()
    print("[OK] Tabela 'anima_usuario_discord_role' criada com sucesso.")

    # 3. Mapeia usuarios do banco (usuario_discord_id -> usuario_id)
    cur.execute("SELECT usuario_id, usuario_discord_id FROM usuario WHERE usuario_discord_id IS NOT NULL AND usuario_discord_id != ''")
    usuario_id_map = {str(r['usuario_discord_id']): r['usuario_id'] for r in cur.fetchall()}
    print(f"[INFO] {len(usuario_id_map)} usuários já vinculados na tabela 'usuario'.")

    # 4. Busca as guilds do bot
    res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
    guilds = res_guilds.json()
    print(f"\n[INFO] {len(guilds)} guild(s) encontrada(s).")

    all_members = []
    for g in guilds:
        g_id = g['id']
        g_name = g['name']
        print(f"Buscando membros da guilda: {g_name} ({g_id})...")
        
        after = "0"
        while True:
            url = f"https://discord.com/api/v10/guilds/{g_id}/members?limit=1000&after={after}"
            res_m = requests.get(url, headers=headers)
            if res_m.status_code != 200:
                print(f"[ERRO] Falha ao buscar membros: {res_m.status_code} - {res_m.text}")
                break
            
            batch = res_m.json()
            if not batch:
                break
                
            all_members.extend(batch)
            after = batch[-1]['user']['id']
            print(f"  -> Lote de {len(batch)} membros carregado (Total acumulado: {len(all_members)})...")
            
            if len(batch) < 1000:
                break

    print(f"\n[OK] Total de membros extraídos do Discord: {len(all_members)}")

    # 5. Salva membros em 'anima_usuario_discord' e associações em 'anima_usuario_discord_role'
    insert_user_sql = """
        INSERT INTO anima_usuario_discord (discord_user_id, discord_username, discord_global_name, discord_avatar_url, usuario_id)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE 
            discord_username = VALUES(discord_username),
            discord_global_name = VALUES(discord_global_name),
            discord_avatar_url = VALUES(discord_avatar_url),
            usuario_id = IF(VALUES(usuario_id) IS NOT NULL, VALUES(usuario_id), usuario_id)
    """

    insert_user_role_sql = """
        INSERT INTO anima_usuario_discord_role (discord_user_id, role_id)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE data_associacao = CURRENT_TIMESTAMP
    """

    insert_role_fallback_sql = """
        INSERT INTO anima_discord_role (role_id, role_descricao, role_ativo)
        VALUES (%s, %s, 1)
        ON DUPLICATE KEY UPDATE role_ativo = role_ativo
    """

    # Carrega roles já cadastradas no banco para evitar FK errors
    cur.execute("SELECT role_id FROM anima_discord_role")
    known_roles = {str(r['role_id']) for r in cur.fetchall()}

    total_users_saved = 0
    total_roles_associated = 0

    for m in all_members:
        u = m.get('user')
        if not u:
            continue

        uid = str(u['id'])
        uname = u.get('username')
        gname = u.get('global_name') or m.get('nick') or uname
        avatar = u.get('avatar')
        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png" if avatar else None
        db_user_id = usuario_id_map.get(uid)

        cur.execute(insert_user_sql, (uid, uname, gname, avatar_url, db_user_id))
        total_users_saved += 1

        # Processa as roles do membro
        member_roles = m.get('roles', [])
        for rid in member_roles:
            rid_str = str(rid)
            if rid_str not in known_roles:
                cur.execute(insert_role_fallback_sql, (rid_str, f"Cargo Discord {rid_str}"))
                known_roles.add(rid_str)
            
            cur.execute(insert_user_role_sql, (uid, rid_str))
            total_roles_associated += 1

    conn.commit()
    print(f"\n[SUCESSO] {total_users_saved} usuários salvos em 'anima_usuario_discord'!")
    print(f"[SUCESSO] {total_roles_associated} associações de usuários com cargos salvas em 'anima_usuario_discord_role'!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO GERAL] {e}")
finally:
    cur.close()
    conn.close()
