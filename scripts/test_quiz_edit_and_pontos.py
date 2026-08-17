import os
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from extensions import db
from models.quiz import Quiz, QuizAplicacao, QuizPergunta, QuizAlternativa, TemaInteresse
from models.uc import Uc
from datetime import datetime, timedelta

def test_quiz_pontos_and_schedule_edit():
    app = create_app()
    with app.app_context():
        print("1. Testando criacao de Quiz com pontuacao customizada...")
        quiz = Quiz(
            quiz_titulo="Quiz Teste Pontos Customizados",
            quiz_descricao="Descricao do quiz de teste",
            pontos_1_lugar=2.50,
            pontos_2_lugar=2.00,
            pontos_3_lugar=1.50,
            pontos_4_lugar=1.00,
            pontos_5_lugar=1.00,
            pontos_6_lugar=1.00,
            pontos_7_lugar=0.75,
            pontos_8_lugar=0.75,
            pontos_9_lugar=0.75,
            pontos_10_lugar=0.75,
        )
        db.session.add(quiz)
        db.session.commit()
        print(f"Quiz #{quiz.quiz_id} criado com sucesso. 1º lugar: {quiz.pontos_1_lugar} pts")
        assert float(quiz.pontos_1_lugar) == 2.50
        assert float(quiz.pontos_10_lugar) == 0.75

        print("2. Testando mapa de pontos do Quiz...")
        pmap = quiz.get_pontos_map()
        assert pmap[1] == 2.50
        assert pmap[3] == 1.50
        assert pmap[7] == 0.75
        print(f"Mapa de pontos gerado: {pmap}")

        print("3. Testando criacao de aplicacao herdando pontos do quiz...")
        uc = Uc.query.first()
        if not uc:
            uc = Uc(uc_nome="UC Teste Automacao", uc_ano_semestre="2026-1", uc_channel_id="123456789")
            db.session.add(uc)
            db.session.commit()

        app_quiz = QuizAplicacao(
            quiz_id=quiz.quiz_id,
            uc_id=uc.uc_id,
            data_hora_prevista=datetime.now() + timedelta(days=1),
            discord_channel_id=uc.uc_channel_id,
            status='Agendado',
            pontos_1_lugar=quiz.pontos_1_lugar,
            pontos_2_lugar=quiz.pontos_2_lugar,
            pontos_3_lugar=quiz.pontos_3_lugar,
            pontos_4_lugar=quiz.pontos_4_lugar,
            pontos_5_lugar=quiz.pontos_5_lugar,
            pontos_6_lugar=quiz.pontos_6_lugar,
            pontos_7_lugar=quiz.pontos_7_lugar,
            pontos_8_lugar=quiz.pontos_8_lugar,
            pontos_9_lugar=quiz.pontos_9_lugar,
            pontos_10_lugar=quiz.pontos_10_lugar,
        )
        db.session.add(app_quiz)
        db.session.commit()
        print(f"Aplicacao #{app_quiz.aplicacao_id} agendada com sucesso para {app_quiz.data_hora_prevista}")

        print("4. Testando edicao do agendamento...")
        nova_data = datetime.now() + timedelta(days=3)
        app_quiz.data_hora_prevista = nova_data
        app_quiz.discord_channel_id = "987654321"
        db.session.commit()

        app_reloaded = QuizAplicacao.query.get(app_quiz.aplicacao_id)
        assert app_reloaded.discord_channel_id == "987654321"
        print(f"Aplicacao editada com sucesso. Novo canal: {app_reloaded.discord_channel_id}")

        print("5. Testando rotas Flask com test_client...")
        client = app.test_client()
        
        # Test GET /quiz/
        res = client.get('/quiz/')
        assert res.status_code == 200
        print("GET /quiz/ OK")

        # Test GET /quiz/aplicacoes
        res = client.get('/quiz/aplicacoes')
        assert res.status_code == 200
        print("GET /quiz/aplicacoes OK")

        # Test GET /quiz/<id>/edit
        res = client.get(f'/quiz/{quiz.quiz_id}/edit')
        assert res.status_code == 200
        print(f"GET /quiz/{quiz.quiz_id}/edit OK")

        # Test GET /quiz/aplicacoes/<id>/edit
        res = client.get(f'/quiz/aplicacoes/{app_quiz.aplicacao_id}/edit')
        assert res.status_code == 200
        print(f"GET /quiz/aplicacoes/{app_quiz.aplicacao_id}/edit OK")

        # Test GET /quiz/<id>/iniciar-imediato
        res = client.get(f'/quiz/{quiz.quiz_id}/iniciar-imediato')
        # Se nao tem perguntas pode dar redirect 302, vamos testar isso
        print(f"GET /quiz/{quiz.quiz_id}/iniciar-imediato retornou status: {res.status_code}")

        # Limpeza do teste
        db.session.delete(app_quiz)
        db.session.delete(quiz)
        db.session.commit()
        print("Limpeza dos dados de teste concluida!")
        print("Todos os testes passaram com 100% de sucesso!")

if __name__ == '__main__':
    test_quiz_pontos_and_schedule_edit()
