import os
import sys
import pandas as pd
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

CSV_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    'arquivos',
    'ql-group_activity-report-1792235920.csv'
)

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        charset="utf8mb4"
    )

def main():
    if not os.path.exists(CSV_PATH):
        print(f"[ERRO] Arquivo CSV não encontrado em: {CSV_PATH}")
        sys.exit(1)

    print(f"Lendo CSV: {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)

    # 1. Obter selos cadastrados no banco
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT selo_id, selo_nome FROM anima_selo")
    selos = cursor.fetchall()
    selo_dict = {s['selo_nome'].strip(): s['selo_id'] for s in selos}
    print(f"Selos mapeados no banco ({len(selo_dict)}):")
    for nome, sid in selo_dict.items():
        print(f"  - [{sid}] {nome}")

    # 2. Filtrar DataFrame pelas Activities válidas e Passed == True
    # Normalização de Passed para booleano seguro
    passed_mask = df['Passed'].astype(str).str.strip().str.lower() == 'true'
    activity_mask = df['Activity'].isin(selo_dict.keys())
    filtered_df = df[passed_mask & activity_mask].copy()

    print(f"\nTotal de registros no CSV: {len(df)}")
    print(f"Registros filtrados (Passed=True & Activity no catálogo): {len(filtered_df)}")

    # 3. Mapear e-mails para usuario_id
    cursor.execute("SELECT usuario_id, usuario_email, usuario_email_pessoal FROM usuario")
    usuarios = cursor.fetchall()

    cursor.execute("""
        SELECT usuario_id, usuario_redhat_email 
        FROM usuario_curso 
        WHERE usuario_redhat_email IS NOT NULL AND usuario_redhat_email != ''
    """)
    usuario_cursos = cursor.fetchall()

    email_to_uid = {}
    for u in usuarios:
        uid = u['usuario_id']
        if u['usuario_email']:
            email_to_uid[u['usuario_email'].strip().lower()] = uid
        if u['usuario_email_pessoal']:
            email_to_uid[u['usuario_email_pessoal'].strip().lower()] = uid

    for uc in usuario_cursos:
        uid = uc['usuario_id']
        if uc['usuario_redhat_email']:
            em = uc['usuario_redhat_email'].strip().lower()
            if em not in email_to_uid:
                email_to_uid[em] = uid

    print(f"Total de e-mails indexados para match: {len(email_to_uid)}")

    # 4. Processar registros e preparar inserts
    # Formatar Date completed se disponível
    filtered_df['parsed_date'] = pd.to_datetime(filtered_df['Date completed'], errors='coerce')
    filtered_df['formatted_date'] = filtered_df['parsed_date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    insert_query = """
        INSERT INTO anima_usuario_selo (usuario_id, selo_id, usuario_selo_data)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            usuario_selo_data = VALUES(usuario_selo_data)
    """

    registros_inseridos = 0
    nao_encontrados = set()

    for _, row in filtered_df.iterrows():
        raw_email = str(row['Member']).strip().lower()
        activity = row['Activity'].strip()
        selo_id = selo_dict.get(activity)
        data_selo = row['formatted_date'] if pd.notnull(row['formatted_date']) else None

        usuario_id = email_to_uid.get(raw_email)
        if not usuario_id:
            nao_encontrados.add(raw_email)
            continue

        cursor.execute(insert_query, (usuario_id, selo_id, data_selo))
        registros_inseridos += 1

    conn.commit()

    print(f"\n[OK] Processamento concluído!")
    print(f"Registros vinculados em anima_usuario_selo: {registros_inseridos}")
    if nao_encontrados:
        print(f"E-mails não localizados no banco ({len(nao_encontrados)}):")
        for ne in sorted(nao_encontrados):
            print(f"  - {ne}")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
