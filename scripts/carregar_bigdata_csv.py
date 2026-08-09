import os
import csv
import logging
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CSV_PATH = r"D:\OneDrive - Anima Educacao - Ambiente Acadêmico\Graduação\2026.2\bigdata.csv"

def clean_val(val):
    if val is None:
        return None
    val_str = str(val).strip().strip('"').strip("'").strip()
    if not val_str or val_str.lower() == 'nan' or val_str.lower() == 'null':
        return None
    return val_str

def load_csv_to_mariadb():
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

    # Adiciona/Ajusta colunas na tabela usuario
    cur.execute("ALTER TABLE usuario MODIFY COLUMN usuario_ra VARCHAR(20) NULL")
    conn.commit()

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
            cur.execute(f"ALTER TABLE usuario ADD COLUMN {col_name} {col_def}")
            conn.commit()

    # Leitura do CSV
    encodings = ['utf-8-sig', 'latin1', 'cp1252']
    rows = []
    
    for enc in encodings:
        try:
            with open(CSV_PATH, mode='r', encoding=enc) as f:
                reader = csv.DictReader(f, delimiter=';')
                fieldnames = reader.fieldnames
                logging.info(f"Lendo CSV com encoding '{enc}'. Colunas encontradas: {fieldnames}")
                
                # Identifica colunas de e-mail acadêmico e pessoal flexivelmente
                email_acad_col = next((c for c in fieldnames if 'acad' in c.lower() or 'ulife' in c.lower() or 'acadêmico' in c.lower()), 'E-mail Acadêmico')
                email_pess_col = next((c for c in fieldnames if 'pessoal' in c.lower()), 'E-mail pessoal')

                for row in reader:
                    rows.append({
                        'usuario_nome': clean_val(row.get('Nome Completo')),
                        'turma_descricao': clean_val(row.get('Turma')),
                        'curso_sigla': clean_val(row.get('Tur')),
                        'ies_sigla': clean_val(row.get('IES')),
                        'usuario_ra': clean_val(row.get('RA')),
                        'usuario_email': clean_val(row.get(email_acad_col)),
                        'usuario_email_pessoal': clean_val(row.get(email_pess_col)),
                        'usuario_discord_id': clean_val(row.get('discord id'))
                    })
            logging.info(f"Leitura concluída com sucesso! Total de registros lidos: {len(rows)}")
            break
        except Exception as e:
            logging.warning(f"Falha ao ler com encoding {enc}: {e}")

    if not rows:
        logging.error("Não foi possível ler os registros do CSV.")
        return

    # Inserção / Atualização (UPSERT)
    inserted = 0
    updated = 0

    sql_upsert = """
        INSERT INTO usuario (
            usuario_nome,
            turma_descricao,
            curso_sigla,
            ies_sigla,
            usuario_ra,
            usuario_email,
            usuario_email_pessoal,
            usuario_discord_id,
            usuario_data_ultima_atualizacao
        ) VALUES (
            %(usuario_nome)s,
            %(turma_descricao)s,
            %(curso_sigla)s,
            %(ies_sigla)s,
            %(usuario_ra)s,
            %(usuario_email)s,
            %(usuario_email_pessoal)s,
            %(usuario_discord_id)s,
            NOW()
        )
        ON DUPLICATE KEY UPDATE
            usuario_nome = VALUES(usuario_nome),
            turma_descricao = COALESCE(VALUES(turma_descricao), turma_descricao),
            curso_sigla = COALESCE(VALUES(curso_sigla), curso_sigla),
            ies_sigla = COALESCE(VALUES(ies_sigla), ies_sigla),
            usuario_ra = COALESCE(VALUES(usuario_ra), usuario_ra),
            usuario_email_pessoal = COALESCE(VALUES(usuario_email_pessoal), usuario_email_pessoal),
            usuario_discord_id = COALESCE(VALUES(usuario_discord_id), usuario_discord_id),
            usuario_data_ultima_atualizacao = NOW()
    """

    for record in rows:
        if not record['usuario_email']:
            continue
        try:
            cur.execute(sql_upsert, record)
            if cur.rowcount == 1:
                inserted += 1
            elif cur.rowcount == 2:
                updated += 1
        except Exception as e:
            logging.error(f"Erro ao inserir/atualizar {record['usuario_email']}: {e}")

    conn.commit()
    cur.close()
    conn.close()

    logging.info(f"Processamento finalizado!")
    logging.info(f"Novos registros inseridos: {inserted}")
    logging.info(f"Registros atualizados: {updated}")

if __name__ == "__main__":
    load_csv_to_mariadb()
