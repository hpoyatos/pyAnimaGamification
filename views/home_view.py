from flask import Blueprint, render_template
from models.quiz import Quiz, QuizPergunta, QuizAplicacao
from models.usuario import Usuario
from models.uc import Uc

home_ui_bp = Blueprint('home_ui', __name__, url_prefix='/ui')

@home_ui_bp.route('/')
def index():
    total_quizes = 0
    total_perguntas = 0
    total_usuarios = 0
    total_ucs = 0
    proximas_aplicacoes = []

    try:
        total_quizes = Quiz.query.count()
        total_perguntas = QuizPergunta.query.count()
        total_usuarios = Usuario.query.count()
        total_ucs = Uc.query.count()
        proximas_aplicacoes = QuizAplicacao.query.filter(
            QuizAplicacao.status.in_(['Agendado', 'Em Andamento'])
        ).order_by(QuizAplicacao.data_hora_prevista.asc()).limit(3).all()
    except Exception:
        pass

    return render_template(
        'home.html',
        total_quizes=total_quizes,
        total_perguntas=total_perguntas,
        total_usuarios=total_usuarios,
        total_ucs=total_ucs,
        proximas_aplicacoes=proximas_aplicacoes
    )
