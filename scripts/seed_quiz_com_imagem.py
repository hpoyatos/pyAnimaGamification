import os
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
    # 1. Encontrar a UC de teste
    cur.execute("SELECT uc_id, uc_nome, uc_channel_id FROM anima_uc WHERE uc_nome LIKE '%teste%' LIMIT 1")
    uc_row = cur.fetchone()
    if not uc_row:
        cur.execute("SELECT uc_id, uc_nome, uc_channel_id FROM anima_uc LIMIT 1")
        uc_row = cur.fetchone()
    
    uc_id = uc_row['uc_id']
    channel_id = uc_row['uc_channel_id'] or '1538186862533939211'
    print(f"UC de Teste: #{uc_id} - {uc_row['uc_nome']} (Canal: {channel_id})")

    # 2. Criar as Perguntas no Banco de Perguntas
    # Pergunta 1
    p1_enunciado = "Qual componente da arquitetura do Kubernetes é o agente primário executado em cada nó de trabalho?"
    p1_img = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Kubernetes_logo_without_workmark.svg/512px-Kubernetes_logo_without_workmark.svg.png"
    cur.execute("""
        INSERT INTO anima_quiz_pergunta (pergunta_ordem, pergunta_enunciado, pergunta_imagem_url, tempo_limite_segundos, pontos_base)
        VALUES (1, %s, %s, 20, 1000)
    """, (p1_enunciado, p1_img))
    p1_id = cur.lastrowid

    # Alternativas P1
    alts_p1 = [
        ('A', 'kube-proxy', False),
        ('B', 'kubelet', True),
        ('C', 'etcd cluster', False),
        ('D', 'ingress-nginx', False),
    ]
    for letra, texto, correta in alts_p1:
        cur.execute("""
            INSERT INTO anima_quiz_alternativa (pergunta_id, alternativa_letra, alternativa_texto, is_correta)
            VALUES (%s, %s, %s, %s)
        """, (p1_id, letra, texto, 1 if correta else 0))

    # Vincular Temas P1 (Cloud e Eng de Software)
    cur.execute("INSERT IGNORE INTO anima_pergunta_tema (pergunta_id, temas_interesse_id) VALUES (%s, 3), (%s, 7)", (p1_id, p1_id))

    # Pergunta 2
    p2_enunciado = "Na área de Inteligência Artificial, qual paradigma de aprendizado utiliza dados previamente rotulados (features + labels) para treinar modelos?"
    p2_img = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Hey_Machine_Learning_Logo.png/512px-Hey_Machine_Learning_Logo.png"
    cur.execute("""
        INSERT INTO anima_quiz_pergunta (pergunta_ordem, pergunta_enunciado, pergunta_imagem_url, tempo_limite_segundos, pontos_base)
        VALUES (2, %s, %s, 20, 1000)
    """, (p2_enunciado, p2_img))
    p2_id = cur.lastrowid

    # Alternativas P2
    alts_p2 = [
        ('A', 'Aprendizado Não Supervisionado', False),
        ('B', 'Aprendizado por Reforço (Q-Learning)', False),
        ('C', 'Aprendizado Supervisionado', True),
        ('D', 'Algoritmos Genéticos Evolutivos', False),
    ]
    for letra, texto, correta in alts_p2:
        cur.execute("""
            INSERT INTO anima_quiz_alternativa (pergunta_id, alternativa_letra, alternativa_texto, is_correta)
            VALUES (%s, %s, %s, %s)
        """, (p2_id, letra, texto, 1 if correta else 0))

    # Vincular Temas P2 (IA e Data Science)
    cur.execute("INSERT IGNORE INTO anima_pergunta_tema (pergunta_id, temas_interesse_id) VALUES (%s, 1), (%s, 4)", (p2_id, p2_id))

    # 3. Criar o Quiz
    cur.execute("""
        INSERT INTO anima_quiz (quiz_titulo, quiz_descricao)
        VALUES ('Quiz Ilustrado: Cloud & Inteligência Artificial', 'Quiz interativo com imagens ilustrativas e perguntas técnicas sobre Cloud Native e IA.')
    """)
    quiz_id = cur.lastrowid

    # Vincular Temas ao Quiz
    cur.execute("INSERT IGNORE INTO anima_quiz_tema (quiz_id, temas_interesse_id) VALUES (%s, 1), (%s, 3), (%s, 4)", (quiz_id, quiz_id, quiz_id))

    # Vincular Perguntas ao Quiz via anima_quiz_pergunta_assoc
    cur.execute("INSERT INTO anima_quiz_pergunta_assoc (quiz_id, pergunta_id, ordem) VALUES (%s, %s, 1), (%s, %s, 2)", (quiz_id, p1_id, quiz_id, p2_id))

    # 4. Criar Agendamento de Aplicação
    data_prevista = datetime.now() + timedelta(days=1)
    cur.execute("""
        INSERT INTO anima_quiz_aplicacao 
        (quiz_id, uc_id, data_hora_prevista, discord_channel_id, status, pontos_1_lugar, pontos_2_lugar, pontos_3_lugar)
        VALUES (%s, %s, %s, %s, 'Agendado', 1.00, 1.00, 1.00)
    """, (quiz_id, uc_id, data_prevista, channel_id))
    app_id = cur.lastrowid

    conn.commit()
    print(f"✅ Quiz #{quiz_id} 'Quiz Ilustrado: Cloud & Inteligência Artificial' criado com sucesso!")
    print(f"✅ Perguntas #{p1_id} e #{p2_id} cadastradas no Banco de Perguntas com imagens ilustrativas!")
    print(f"✅ Aplicação #{app_id} agendada para UC #{uc_id} no canal {channel_id}.")

except Exception as e:
    conn.rollback()
    print(f"❌ Erro ao criar quiz ilustrado: {e}")
finally:
    cur.close()
    conn.close()
