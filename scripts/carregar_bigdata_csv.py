import os
import sys
import csv
import argparse
import logging
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_CSV_PATH = r"D:\OneDrive - Anima Educacao - Ambiente Acadêmico\Graduação\2026.2\bigdata.csv"

def clean_val(val):
    if val is None:
        return None
    val_str = str(val).strip().strip('"').strip("'").strip()
    if not val_str or val_str.lower() == 'nan' or val_str.lower() == 'null':
        return None
    return val_str

def load_csv_to_mariadb(csv_path=None, uc_id=None):
    if not csv_path:
        csv_path = os.getenv("CSV_PATH", DEFAULT_CSV_PATH)
    
    if not uc_id:
        uc_id = os.getenv("UC_ID", "2")
    
    try:
        uc_id = int(uc_id)
    except ValueError:
        uc_id = 2

    host = os.getenv("DB_HOST", "192.168.15.254")
    port = int(os.getenv("DB_PORT", "30306"))
    database = os.getenv("DB_NAME", "anima")
    user = os.getenv("DB_USER", "anima_bot")
    password = os.getenv("DB_PASSWORD")

    logging.info(f"Conectando ao MariaDB em {host}:{port}/{database}...")
    conn = mysql.connector.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True
    )
    cur = conn.cursor(dictionary=True)

    # 1. Garantir que a tabela anima_uc_usuario existe
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anima_uc_usuario (
                usuario_id INT NOT NULL,
                uc_id INT NOT NULL,
                PRIMARY KEY (usuario_id, uc_id),
                CONSTRAINT fk_anima_uc_usuario_user FOREIGN KEY (usuario_id) REFERENCES usuario (usuario_id) ON DELETE CASCADE ON UPDATE CASCADE,
                CONSTRAINT fk_anima_uc_usuario_uc FOREIGN KEY (uc_id) REFERENCES anima_uc (uc_id) ON DELETE CASCADE ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)
        conn.commit()
    except Exception as e_tbl:
        logging.warning(f"Alerta ao verificar tabela anima_uc_usuario: {e_tbl}")

    # 2. Verificar dados da UC selecionada
    try:
        cur.execute("SELECT uc_id, uc_nome FROM anima_uc WHERE uc_id = %s", (uc_id,))
        uc_row = cur.fetchone()
        if uc_row:
            logging.info(f"UC selecionada para associação: ID {uc_row['uc_id']} - '{uc_row['uc_nome']}'")
        else:
            logging.warning(f"UC com ID {uc_id} não encontrada em anima_uc. O vinculo sera realizado com uc_id={uc_id}.")
    except Exception as e_uc_check:
        logging.warning(f"Erro ao verificar UC {uc_id}: {e_uc_check}")

    # Adjust columns in usuario if missing
    try:
        cur.execute("ALTER TABLE usuario MODIFY COLUMN usuario_ra VARCHAR(20) NULL")
        conn.commit()
    except Exception:
        pass

    cols_to_add = [
        ("ies_sigla", "CHAR(15) NULL"),
        ("curso_sigla", "CHAR(3) NULL"),
        ("usuario_email_pessoal", "VARCHAR(150) NULL"),
        ("turma_descricao", "VARCHAR(100) NULL")
    ]

    cur.execute("DESCRIBE usuario")
    existing_cols = {row['Field'] for row in cur.fetchall()}

    for col_name, col_def in cols_to_add:
        if col_name not in existing_cols:
            logging.info(f"Adicionando coluna {col_name} na tabela usuario...")
            try:
                cur.execute(f"ALTER TABLE usuario ADD COLUMN {col_name} {col_def}")
                conn.commit()
                existing_cols.add(col_name)
            except Exception as e_col:
                logging.warning(f"Não foi possível adicionar coluna {col_name}: {e_col}")

    # Read CSV
    encodings = ['utf-8-sig', 'latin1', 'cp1252']
    rows = []
    
    for enc in encodings:
        try:
            with open(csv_path, mode='r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames
                logging.info(f"Lendo CSV '{csv_path}' com encoding '{enc}'. Colunas: {fieldnames}")
                
                email_acad_col = next((c for c in fieldnames if 'acad' in c.lower() or 'ulife' in c.lower() or 'acadêmico' in c.lower()), 'E-mail Acadêmico')
                email_pess_col = next((c for c in fieldnames if 'pessoal' in c.lower()), 'E-mail pessoal')

                for row in reader:
                    nome = clean_val(row.get('Nome Completo'))
                    email = clean_val(row.get(email_acad_col))
                    if not email or not nome:
                        continue
                    rows.append({
                        'usuario_nome': nome,
                        'turma_descricao': clean_val(row.get('Turma')),
                        'curso_sigla': clean_val(row.get('Tur')),
                        'ies_sigla': clean_val(row.get('IES')),
                        'usuario_ra': clean_val(row.get('RA')),
                        'usuario_email': email,
                        'usuario_email_pessoal': clean_val(row.get(email_pess_col)),
                        'usuario_discord_id': clean_val(row.get('discord id'))
                    })
            logging.info(f"Leitura concluída! Total de registros válidos lidos: {len(rows)}")
            break
        except Exception as e:
            logging.warning(f"Falha ao ler com encoding {enc}: {e}")

    if not rows:
        logging.error("Nenhum registro lido do arquivo CSV.")
        return

    # Inserção / Atualização (UPSERT no usuario) + Vínculo na anima_uc_usuario
    inserted = 0
    updated = 0
    vinculados = 0

    has_extra_cols = ('ies_sigla' in existing_cols and 'curso_sigla' in existing_cols)

    for record in rows:
        email = record['usuario_email']
        nome = record['usuario_nome']
        ra = record['usuario_ra']
        discord_id = record['usuario_discord_id']
        email_pessoal = record['usuario_email_pessoal']
        ies = record['ies_sigla']
        curso = record['curso_sigla']
        turma = record['turma_descricao']

        # Check existing user by email
        cur.execute("SELECT usuario_id FROM usuario WHERE usuario_email = %s", (email,))
        row_user = cur.fetchone()

        if row_user:
            usuario_id = row_user['usuario_id']
            # Update user info
            if has_extra_cols:
                cur.execute("""
                    UPDATE usuario 
                    SET usuario_nome = %s,
                        usuario_ra = COALESCE(%s, usuario_ra),
                        usuario_discord_id = COALESCE(%s, usuario_discord_id),
                        usuario_email_pessoal = COALESCE(%s, usuario_email_pessoal),
                        ies_sigla = COALESCE(%s, ies_sigla),
                        curso_sigla = COALESCE(%s, curso_sigla),
                        turma_descricao = COALESCE(%s, turma_descricao)
                    WHERE usuario_id = %s
                """, (nome, ra, discord_id, email_pessoal, ies, curso, turma, usuario_id))
            else:
                cur.execute("""
                    UPDATE usuario 
                    SET usuario_nome = %s,
                        usuario_ra = COALESCE(%s, usuario_ra),
                        usuario_discord_id = COALESCE(%s, usuario_discord_id)
                    WHERE usuario_id = %s
                """, (nome, ra, discord_id, usuario_id))
            updated += 1
        else:
            # Insert user
            if has_extra_cols:
                cur.execute("""
                    INSERT INTO usuario (usuario_nome, usuario_email, usuario_ra, usuario_discord_id, usuario_email_pessoal, ies_sigla, curso_sigla, turma_descricao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (nome, email, ra, discord_id, email_pessoal, ies, curso, turma))
            else:
                cur.execute("""
                    INSERT INTO usuario (usuario_nome, usuario_email, usuario_ra, usuario_discord_id)
                    VALUES (%s, %s, %s, %s)
                """, (nome, email, ra, discord_id))
            usuario_id = cur.lastrowid
            inserted += 1

        # Associa o usuário à UC na tabela anima_uc_usuario
        if usuario_id and uc_id:
            try:
                cur.execute("""
                    INSERT IGNORE INTO anima_uc_usuario (usuario_id, uc_id)
                    VALUES (%s, %s)
                """, (usuario_id, uc_id))
                if cur.rowcount > 0:
                    vinculados += 1
            except Exception as e_vinc:
                logging.error(f"Erro ao vincular usuario_id {usuario_id} à uc_id {uc_id}: {e_vinc}")

    conn.commit()
    cur.close()
    conn.close()

    logging.info("Processamento de carga finalizado!")
    logging.info(f"Novos usuários inseridos: {inserted}")
    logging.info(f"Usuários existentes atualizados: {updated}")
    logging.info(f"Novos vínculos inseridos em anima_uc_usuario (UC {uc_id}): {vinculados}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Carregar usuários do CSV para a base e associar à UC em anima_uc_usuario.")
    parser.add_argument("--csv", type=str, help="Caminho do arquivo CSV", default=None)
    parser.add_argument("--uc-id", type=int, help="ID da UC em anima_uc (ex: 2)", default=None)
    args = parser.parse_args()

    load_csv_to_mariadb(csv_path=args.csv, uc_id=args.uc_id)
