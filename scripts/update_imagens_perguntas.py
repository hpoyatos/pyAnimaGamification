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
    # 1. Atualizar Perguntas existentes com URLs diretas PNG do CDN do GitHub
    cur.execute("""
        UPDATE anima_quiz_pergunta 
        SET pergunta_imagem_url = 'https://raw.githubusercontent.com/github/explore/main/topics/linux/linux.png'
        WHERE pergunta_id = 1
    """)

    cur.execute("""
        UPDATE anima_quiz_pergunta 
        SET pergunta_imagem_url = 'https://raw.githubusercontent.com/github/explore/main/topics/python/python.png'
        WHERE pergunta_id = 2
    """)

    cur.execute("""
        UPDATE anima_quiz_pergunta 
        SET pergunta_imagem_url = 'https://raw.githubusercontent.com/github/explore/main/topics/kubernetes/kubernetes.png'
        WHERE pergunta_id = 3
    """)

    cur.execute("""
        UPDATE anima_quiz_pergunta 
        SET pergunta_imagem_url = 'https://raw.githubusercontent.com/github/explore/main/topics/docker/docker.png'
        WHERE pergunta_id = 4
    """)

    # 2. Criar mais uma Pergunta Ilustrada com SQL
    cur.execute("""
        INSERT INTO anima_quiz_pergunta (pergunta_ordem, pergunta_enunciado, pergunta_imagem_url, tempo_limite_segundos, pontos_base)
        VALUES (5, 'Qual cláusula SQL é utilizada para agrupar registros e permitir o cálculo de funções agregadas como COUNT, SUM e AVG?', 
                'https://raw.githubusercontent.com/github/explore/main/topics/sql/sql.png', 20, 1000)
    """)
    p5_id = cur.lastrowid

    alts_p5 = [
        ('A', 'ORDER BY', False),
        ('B', 'GROUP BY', True),
        ('C', 'HAVING', False),
        ('D', 'JOIN ON', False),
    ]
    for letra, texto, correta in alts_p5:
        cur.execute("""
            INSERT INTO anima_quiz_alternativa (pergunta_id, alternativa_letra, alternativa_texto, is_correta)
            VALUES (%s, %s, %s, %s)
        """, (p5_id, letra, texto, 1 if correta else 0))

    # Vincular pergunta 5 ao Quiz 2
    cur.execute("INSERT IGNORE INTO anima_quiz_pergunta_assoc (quiz_id, pergunta_id, ordem) VALUES (2, %s, 3)", (p5_id,))

    # Vincular perguntas 1 e 2 ao Quiz 1 caso ainda não estejam na tabela associativa
    cur.execute("INSERT IGNORE INTO anima_quiz_pergunta_assoc (quiz_id, pergunta_id, ordem) VALUES (1, 1, 1), (1, 2, 2)")

    conn.commit()
    print("[OK] Todas as perguntas atualizadas com imagens diretas de alta fidelidade e nova pergunta de SQL cadastrada!")

except Exception as e:
    conn.rollback()
    print(f"[ERRO] {e}")
finally:
    cur.close()
    conn.close()
