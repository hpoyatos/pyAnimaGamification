import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models.quiz import (
    Quiz, QuizPergunta, QuizAlternativa, QuizAplicacao,
    QuizResposta, QuizParticipante, TemaInteresse
)
from models.uc import Uc
from models.usuario import Usuario
from models.usuario_discord import UsuarioDiscord
from models.ponto import Pontuacao

app = create_app()

with app.app_context():
    print("[1/5] Testando conexão com Flask e Banco de Dados...")
    
    # 1. Obter ou criar temas de interesse de teste
    tema = TemaInteresse.query.first()
    if not tema:
        tema = TemaInteresse(
            temas_interesse_nome="Redes de Computadores",
            temas_interesse_tag="REDES",
            temas_interesse_descricao="Conceitos de TCP/IP e protocolos"
        )
        db.session.add(tema)
        db.session.commit()
    print(f"Tema encontrado/criado: {tema.temas_interesse_nome} (ID: {tema.temas_interesse_id})")

    # 2. Criar ou obter Quiz de teste
    quiz = Quiz.query.filter_by(quiz_titulo="Quiz de Teste - Kahoot Bot").first()
    if not quiz:
        quiz = Quiz(
            quiz_titulo="Quiz de Teste - Kahoot Bot",
            quiz_descricao="Quiz interativo para validação da funcionalidade Kahoot no Discord."
        )
        quiz.temas.append(tema)
        db.session.add(quiz)
        db.session.commit()
        print(f"Quiz de teste criado: ID {quiz.quiz_id}")
    else:
        print(f"Quiz de teste já existente: ID {quiz.quiz_id}")

    # 3. Adicionar Perguntas e 4 Alternativas
    if not quiz.perguntas:
        p1 = QuizPergunta(
            quiz_id=quiz.quiz_id,
            pergunta_ordem=1,
            pergunta_enunciado="Qual camada do modelo OSI é responsável pelo roteamento de pacotes?",
            tempo_limite_segundos=20,
            pontos_base=1000
        )
        db.session.add(p1)
        db.session.flush()

        alts_p1 = [
            QuizAlternativa(pergunta_id=p1.pergunta_id, alternativa_letra='A', alternativa_texto='Camada Física', is_correta=False),
            QuizAlternativa(pergunta_id=p1.pergunta_id, alternativa_letra='B', alternativa_texto='Camada de Enlace', is_correta=False),
            QuizAlternativa(pergunta_id=p1.pergunta_id, alternativa_letra='C', alternativa_texto='Camada de Rede', is_correta=True),
            QuizAlternativa(pergunta_id=p1.pergunta_id, alternativa_letra='D', alternativa_texto='Camada de Aplicação', is_correta=False),
        ]
        db.session.add_all(alts_p1)

        p2 = QuizPergunta(
            quiz_id=quiz.quiz_id,
            pergunta_ordem=2,
            pergunta_enunciado="Qual protocolo da camada de transporte é orientado a conexão e garante entrega ordenada?",
            tempo_limite_segundos=15,
            pontos_base=1000
        )
        db.session.add(p2)
        db.session.flush()

        alts_p2 = [
            QuizAlternativa(pergunta_id=p2.pergunta_id, alternativa_letra='A', alternativa_texto='UDP', is_correta=False),
            QuizAlternativa(pergunta_id=p2.pergunta_id, alternativa_letra='B', alternativa_texto='TCP', is_correta=True),
            QuizAlternativa(pergunta_id=p2.pergunta_id, alternativa_letra='C', alternativa_texto='ICMP', is_correta=False),
            QuizAlternativa(pergunta_id=p2.pergunta_id, alternativa_letra='D', alternativa_texto='ARP', is_correta=False),
        ]
        db.session.add_all(alts_p2)
        db.session.commit()
        print("[2/5] 2 Perguntas com 4 alternativas cadastradas com sucesso!")
    else:
        print(f"[2/5] Quiz já possui {len(quiz.perguntas)} perguntas cadastradas.")

    # 4. Agendar Aplicação na UC 'teste' (uc_id = 11, uc_channel_id = 1538186862533939211)
    uc_teste = Uc.query.filter((Uc.uc_nome == 'teste') | (Uc.uc_channel_id == '1538186862533939211')).first()
    if not uc_teste:
        uc_teste = Uc(
            uc_nome='teste',
            uc_ano_semestre='2026/02',
            uc_discord_role='1538186587630993599',
            uc_dia_semana=6,
            uc_channel_id='1538186862533939211'
        )
        db.session.add(uc_teste)
        db.session.commit()
        print(f"UC Teste criada: ID {uc_teste.uc_id}")
    else:
        print(f"UC Teste localizada: ID {uc_teste.uc_id} (Canal {uc_teste.uc_channel_id})")

    # Cria agendamento
    aplicacao = QuizAplicacao(
        quiz_id=quiz.quiz_id,
        uc_id=uc_teste.uc_id,
        data_hora_prevista=datetime.now(),
        discord_channel_id=uc_teste.uc_channel_id,
        status='Agendado',
        pontos_1_lugar=1.0,
        pontos_2_lugar=1.0,
        pontos_3_lugar=1.0,
        pontos_4_lugar=0.8,
        pontos_5_lugar=0.8,
        pontos_6_lugar=0.8,
        pontos_7_lugar=0.5,
        pontos_8_lugar=0.5,
        pontos_9_lugar=0.5,
        pontos_10_lugar=0.5
    )
    db.session.add(aplicacao)
    db.session.commit()
    print(f"[3/5] Aplicação agendada com sucesso: ID #{aplicacao.aplicacao_id}")

    # 5. Simular Resposta de Usuário Discord com precisão de milissegundos
    dummy_discord_id = "123456789012345678"
    usuario_disc = UsuarioDiscord.query.get(dummy_discord_id)
    if not usuario_disc:
        usuario_disc = UsuarioDiscord(
            discord_user_id=dummy_discord_id,
            discord_username="aluno_teste",
            discord_global_name="Aluno Teste Discord"
        )
        db.session.add(usuario_disc)
        db.session.commit()

    # Registra resposta
    p1 = quiz.perguntas[0]
    alt_correta = [a for a in p1.alternativas if a.is_correta][0]
    resp = QuizResposta(
        aplicacao_id=aplicacao.aplicacao_id,
        pergunta_id=p1.pergunta_id,
        alternativa_id=alt_correta.alternativa_id,
        discord_user_id=dummy_discord_id,
        data_hora_resposta=datetime.now(),
        tempo_gasto_ms=2345,
        is_correta=True,
        pontos_ganhos=941
    )
    db.session.add(resp)

    # Registra no participante
    part = QuizParticipante(
        aplicacao_id=aplicacao.aplicacao_id,
        discord_user_id=dummy_discord_id,
        pontuacao_total=941,
        acertos=1,
        tempo_total_ms=2345,
        posicao_final=1,
        pontos_atribuidos=1.00
    )
    db.session.add(part)
    db.session.commit()
    print("[4/5] Resposta com precisão de milissegundos e ranking registrados com sucesso!")

    # 6. Testar rotas do Flask com o test_client
    client = app.test_client()
    res_list = client.get('/quiz/')
    assert res_list.status_code == 200, f"Status code {res_list.status_code}"
    print(f"GET /quiz/ status: {res_list.status_code} OK")

    res_perguntas = client.get(f'/quiz/{quiz.quiz_id}/perguntas')
    assert res_perguntas.status_code == 200, f"Status code {res_perguntas.status_code}"
    print(f"GET /quiz/{quiz.quiz_id}/perguntas status: {res_perguntas.status_code} OK")

    res_apps = client.get('/quiz/aplicacoes')
    assert res_apps.status_code == 200, f"Status code {res_apps.status_code}"
    print(f"GET /quiz/aplicacoes status: {res_apps.status_code} OK")

    res_result = client.get(f'/quiz/aplicacoes/{aplicacao.aplicacao_id}/resultado')
    assert res_result.status_code == 200, f"Status code {res_result.status_code}"
    print(f"GET /quiz/aplicacoes/{aplicacao.aplicacao_id}/resultado status: {res_result.status_code} OK")

    print("[5/5] Todos os testes passaram com 100% de sucesso!")
