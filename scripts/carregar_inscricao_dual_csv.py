import os
import sys
import csv
import argparse
import logging
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_CSV_PATH = "/home/hpoyatos/CodeProjects/pyAnimaGamification/arquivos/Aprendizagem Dual_Formulário de Inscrição Aceleradora Profissional Dual 2026_1_ate_16_09_2026.csv"
DEFAULT_UC_ID = 16

def clean_val(val):
    if val is None:
        return None
    val_str = str(val).strip().strip('"').strip("'").strip()
    if not val_str or val_str.lower() in ('nan', 'null', 'none'):
        return None
    return val_str

def get_db_connection():
    host = os.getenv("DB_HOST", "192.168.15.254")
    port = int(os.getenv("DB_PORT", "30306"))
    database = os.getenv("DB_NAME", "anima")
    user = os.getenv("DB_USER", "anima_bot")
    password = os.getenv("DB_PASSWORD")

    logging.info(f"Conectando ao MariaDB em {host}:{port}/{database}...")
    return mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True
    )

def setup_database_schema(conn):
    cur = conn.cursor(dictionary=True)
    
    # 1. Adiciona coluna usuario_telefone se não existir
    cur.execute("DESCRIBE usuario")
    existing_cols = {row['Field']: row for row in cur.fetchall()}

    if "usuario_telefone" not in existing_cols:
        logging.info("Adicionando coluna 'usuario_telefone' na tabela usuario...")
        cur.execute("ALTER TABLE usuario ADD COLUMN usuario_telefone VARCHAR(30) NULL AFTER usuario_email_pessoal")
        conn.commit()
        logging.info("Coluna 'usuario_telefone' criada com sucesso.")
    else:
        logging.info("Coluna 'usuario_telefone' já existe na tabela usuario.")

    # 2. Ajusta usuario_email para permitir NULL caso haja emails puramente pessoais na inserção
    # Como a tabela original tem usuario_email VARCHAR(60) NOT NULL, mas a regra de negócio
    # define que emails não-ulife vão em usuario_email_pessoal, precisamos que usuario_email aceite NULL.
    user_email_info = existing_cols.get('usuario_email')
    if user_email_info and user_email_info.get('Null') == 'NO':
        logging.info("Ajustando coluna 'usuario_email' para permitir valores NULL...")
        try:
            cur.execute("ALTER TABLE usuario MODIFY COLUMN usuario_email VARCHAR(60) NULL")
            conn.commit()
            logging.info("Coluna 'usuario_email' agora permite NULL.")
        except Exception as e:
            logging.warning(f"Não foi possível alterar usuario_email para NULL: {e}")

    # 3. Garante que a tabela anima_uc_usuario existe
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anima_uc_usuario (
                uc_id INT NOT NULL,
                usuario_id INT NOT NULL,
                PRIMARY KEY (usuario_id, uc_id),
                CONSTRAINT fk_anima_uc_usuario_user FOREIGN KEY (usuario_id) REFERENCES usuario (usuario_id) ON DELETE CASCADE ON UPDATE CASCADE,
                CONSTRAINT fk_anima_uc_usuario_uc FOREIGN KEY (uc_id) REFERENCES anima_uc (uc_id) ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)
        conn.commit()
    except Exception as e:
        logging.warning(f"Alerta ao verificar tabela anima_uc_usuario: {e}")

    cur.close()

def load_inscricao_csv(csv_path=None, uc_id=None):
    if not csv_path:
        csv_path = DEFAULT_CSV_PATH
    if not uc_id:
        uc_id = DEFAULT_UC_ID

    try:
        uc_id = int(uc_id)
    except ValueError:
        uc_id = DEFAULT_UC_ID

    if not os.path.exists(csv_path):
        logging.error(f"Arquivo CSV não encontrado: {csv_path}")
        return

    conn = get_db_connection()
    setup_database_schema(conn)

    cur = conn.cursor(dictionary=True)

    # Verifica se UC existe
    cur.execute("SELECT uc_id, uc_nome FROM anima_uc WHERE uc_id = %s", (uc_id,))
    uc_row = cur.fetchone()
    if uc_row:
        logging.info(f"UC selecionada: ID {uc_row['uc_id']} - '{uc_row['uc_nome']}'")
    else:
        logging.warning(f"UC com ID {uc_id} não encontrada na tabela anima_uc.")

    # Leitura do CSV
    encodings = ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']
    rows = []

    for enc in encodings:
        try:
            with open(csv_path, mode='r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames or []
                logging.info(f"Lendo CSV '{csv_path}' com encoding '{enc}'. Colunas encontradas: {fieldnames}")

                col_nome = next((c for c in fieldnames if 'nome' in c.lower()), None)
                col_email = next((c for c in fieldnames if 'mail' in c.lower()), None)
                col_tel = next((c for c in fieldnames if 'tel' in c.lower() or 'cel' in c.lower() or 'fone' in c.lower()), None)

                if not col_nome or not col_email or not col_tel:
                    logging.warning(f"Colunas esperadas não localizadas com clareza. Tentando cabeçalhos diretos...")
                    col_nome = col_nome or 'Nome do estudante:'
                    col_email = col_email or 'E-mail:'
                    col_tel = col_tel or 'Telefone:'

                for row in reader:
                    nome = clean_val(row.get(col_nome))
                    email = clean_val(row.get(col_email))
                    telefone = clean_val(row.get(col_tel))

                    if not nome and not email:
                        continue

                    rows.append({
                        'nome': nome,
                        'email': email,
                        'telefone': telefone
                    })
            logging.info(f"Leitura concluída com sucesso! Total de linhas: {len(rows)}")
            break
        except Exception as e:
            logging.warning(f"Tentativa de leitura com encoding '{enc}' falhou: {e}")

    if not rows:
        logging.error("Nenhuma linha válida encontrada no CSV.")
        cur.close()
        conn.close()
        return

    users_updated = 0
    users_inserted = 0
    uc_vinculados = 0
    uc_ja_existentes = 0

    for idx, row_data in enumerate(rows, start=1):
        nome = row_data['nome']
        email_bruto = row_data['email']
        telefone = row_data['telefone']

        email_ulife = None
        email_pessoal = None

        if email_bruto:
            if '@ulife.com.br' in email_bruto.lower():
                email_ulife = email_bruto
            else:
                email_pessoal = email_bruto

        usuario_id = None
        user_row = None

        # 1. Consulta pelo nome completo em minúsculas
        if nome:
            cur.execute("""
                SELECT usuario_id, usuario_nome, usuario_email, usuario_email_pessoal, usuario_telefone
                FROM usuario
                WHERE LOWER(TRIM(usuario_nome)) = LOWER(TRIM(%s))
                LIMIT 1
            """, (nome,))
            user_row = cur.fetchone()

        # 2. Alternativamente, procura o e-mail em usuario_email e usuario_email_pessoal
        if not user_row and email_bruto:
            cur.execute("""
                SELECT usuario_id, usuario_nome, usuario_email, usuario_email_pessoal, usuario_telefone
                FROM usuario
                WHERE LOWER(TRIM(COALESCE(usuario_email, ''))) = LOWER(TRIM(%s))
                   OR LOWER(TRIM(COALESCE(usuario_email_pessoal, ''))) = LOWER(TRIM(%s))
                LIMIT 1
            """, (email_bruto, email_bruto))
            user_row = cur.fetchone()

        # 3. Se localizado: UPDATE adicionando telefone e guardando email conforme a regra
        if user_row:
            usuario_id = user_row['usuario_id']
            
            # Decide atualização de email mantendo ou completando dados existentes
            current_email = user_row.get('usuario_email')
            current_pessoal = user_row.get('usuario_email_pessoal')

            new_email = email_ulife if email_ulife else current_email
            new_pessoal = email_pessoal if email_pessoal else current_pessoal

            cur.execute("""
                UPDATE usuario
                SET usuario_telefone = COALESCE(%s, usuario_telefone),
                    usuario_email = %s,
                    usuario_email_pessoal = %s
                WHERE usuario_id = %s
            """, (telefone, new_email, new_pessoal, usuario_id))
            users_updated += 1

        # 4. Se não encontrado: INSERT na tabela usuario
        else:
            cur.execute("""
                INSERT INTO usuario (
                    usuario_nome,
                    usuario_email,
                    usuario_email_pessoal,
                    usuario_telefone,
                    usuario_validado
                )
                VALUES (%s, %s, %s, %s, 0)
            """, (nome, email_ulife, email_pessoal, telefone))
            usuario_id = cur.lastrowid
            users_inserted += 1

        # 5. Cruzamento com anima_uc_usuario (uc_id = 16)
        if usuario_id and uc_id:
            cur.execute("""
                SELECT 1 FROM anima_uc_usuario
                WHERE usuario_id = %s AND uc_id = %s
                LIMIT 1
            """, (usuario_id, uc_id))
            vinc_existe = cur.fetchone()

            if not vinc_existe:
                cur.execute("""
                    INSERT INTO anima_uc_usuario (usuario_id, uc_id)
                    VALUES (%s, %s)
                """, (usuario_id, uc_id))
                uc_vinculados += 1
            else:
                uc_ja_existentes += 1

    conn.commit()
    cur.close()
    conn.close()

    logging.info("=" * 60)
    logging.info("Processamento de carga concluído com sucesso!")
    logging.info(f"Total de registros processados: {len(rows)}")
    logging.info(f"Usuários encontrados e atualizados: {users_updated}")
    logging.info(f"Novos usuários inseridos: {users_inserted}")
    logging.info(f"Novos vínculos inseridos em anima_uc_usuario (UC {uc_id}): {uc_vinculados}")
    logging.info(f"Vínculos já existentes preservados: {uc_ja_existentes}")
    logging.info("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carga de CSV de Inscrição Aceleradora Dual para MariaDB")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV_PATH, help="Caminho do arquivo CSV")
    parser.add_argument("--uc-id", type=int, default=DEFAULT_UC_ID, help="ID da UC (padrão: 16)")
    args = parser.parse_args()

    load_inscricao_csv(csv_path=args.csv, uc_id=args.uc_id)
