import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 3306)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    charset="utf8mb4"
)
cur = conn.cursor(dictionary=True)

try:
    # 1. Verificar se a coluna curso_descricao ja existe
    cur.execute("DESCRIBE curso")
    cols = [r['Field'] for r in cur.fetchall()]
    
    if 'curso_descricao' not in cols:
        cur.execute("ALTER TABLE curso ADD COLUMN curso_descricao TEXT NULL AFTER curso_nome")
        print("[OK] Coluna 'curso_descricao' adicionada com sucesso na tabela 'curso'.")
    else:
        print("[INFO] Coluna 'curso_descricao' já existe.")

    # 2. Adicionar algumas descrições ricas de exemplo nos cursos ativos
    cur.execute("""
        UPDATE curso 
        SET curso_descricao = 'Aprenda os fundamentos da computação em nuvem AWS, serviços centrais (EC2, S3, RDS, IAM) e conceitos de segurança para certificação Cloud Practitioner.'
        WHERE curso_parceira = 'AWS' AND curso_nome LIKE '%Foundations%' AND curso_descricao IS NULL
    """)

    cur.execute("""
        UPDATE curso 
        SET curso_descricao = 'Curso oficial Red Hat para formação de administradores de sistemas Linux, automação em linha de comando, permissões, processos e storage.'
        WHERE curso_parceira = 'Red Hat' AND curso_descricao IS NULL
    """)

    cur.execute("""
        UPDATE curso 
        SET curso_descricao = 'Capacitação prática em análise exploratória de dados, visualização estatística e tomada de decisão com ferramentas modernas.'
        WHERE curso_parceira = 'Cisco' AND curso_nome LIKE '%análise de dados%' AND curso_descricao IS NULL
    """)

    conn.commit()
    print("[OK] Descrições iniciais atualizadas com sucesso!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
