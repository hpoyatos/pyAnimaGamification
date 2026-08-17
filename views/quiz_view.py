from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db
from models.quiz import (
    Quiz, QuizPergunta, QuizAlternativa, QuizAplicacao,
    QuizResposta, QuizParticipante, TemaInteresse
)
from models.uc import Uc
from models.usuario import Usuario
from models.usuario_discord import UsuarioDiscord
from forms.quiz_form import QuizForm, PerguntaForm, AplicacaoQuizForm
from datetime import datetime

quiz_ui_bp = Blueprint('quiz_ui', __name__, url_prefix='/quiz')

# ============================================================
# QUIZES (CRUD)
# ============================================================

@quiz_ui_bp.route('/')
def list_quizes():
    quizes = Quiz.query.order_by(Quiz.data_criacao.desc()).all()
    return render_template('quiz/list.html', quizes=quizes)

@quiz_ui_bp.route('/new', methods=['GET', 'POST'])
def create_quiz():
    form = QuizForm()
    temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} ({t.temas_interesse_tag or ''})") for t in temas]
    
    perguntas_banco = QuizPergunta.query.order_by(QuizPergunta.pergunta_id.desc()).all()
    form.perguntas_selecionadas.choices = [(p.pergunta_id, f"#{p.pergunta_id} - {p.pergunta_enunciado[:60]}...") for p in perguntas_banco]

    if form.validate_on_submit():
        novo_quiz = Quiz(
            quiz_titulo=form.quiz_titulo.data,
            quiz_descricao=form.quiz_descricao.data,
            pontos_1_lugar=form.pontos_1_lugar.data,
            pontos_2_lugar=form.pontos_2_lugar.data,
            pontos_3_lugar=form.pontos_3_lugar.data,
            pontos_4_lugar=form.pontos_4_lugar.data,
            pontos_5_lugar=form.pontos_5_lugar.data,
            pontos_6_lugar=form.pontos_6_lugar.data,
            pontos_7_lugar=form.pontos_7_lugar.data,
            pontos_8_lugar=form.pontos_8_lugar.data,
            pontos_9_lugar=form.pontos_9_lugar.data,
            pontos_10_lugar=form.pontos_10_lugar.data,
        )
        if form.temas.data:
            selected_temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()
            novo_quiz.temas = selected_temas

        if form.perguntas_selecionadas.data:
            selected_perguntas = QuizPergunta.query.filter(QuizPergunta.pergunta_id.in_(form.perguntas_selecionadas.data)).all()
            novo_quiz.perguntas = selected_perguntas
        
        db.session.add(novo_quiz)
        db.session.commit()
        flash('Quiz criado com sucesso! Você pode gerenciar as perguntas associadas.', 'success')
        return redirect(url_for('quiz_ui.list_perguntas', quiz_id=novo_quiz.quiz_id))

    return render_template('quiz/form.html', form=form, title='Novo Quiz')

@quiz_ui_bp.route('/<int:quiz_id>/edit', methods=['GET', 'POST'])
def edit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuizForm(obj=quiz)
    temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} ({t.temas_interesse_tag or ''})") for t in temas]

    perguntas_banco = QuizPergunta.query.order_by(QuizPergunta.pergunta_id.desc()).all()
    form.perguntas_selecionadas.choices = [(p.pergunta_id, f"#{p.pergunta_id} - {p.pergunta_enunciado[:60]}...") for p in perguntas_banco]

    if request.method == 'GET':
        form.temas.data = [t.temas_interesse_id for t in quiz.temas]
        form.perguntas_selecionadas.data = [p.pergunta_id for p in quiz.perguntas]

    if form.validate_on_submit():
        quiz.quiz_titulo = form.quiz_titulo.data
        quiz.quiz_descricao = form.quiz_descricao.data
        quiz.pontos_1_lugar = form.pontos_1_lugar.data
        quiz.pontos_2_lugar = form.pontos_2_lugar.data
        quiz.pontos_3_lugar = form.pontos_3_lugar.data
        quiz.pontos_4_lugar = form.pontos_4_lugar.data
        quiz.pontos_5_lugar = form.pontos_5_lugar.data
        quiz.pontos_6_lugar = form.pontos_6_lugar.data
        quiz.pontos_7_lugar = form.pontos_7_lugar.data
        quiz.pontos_8_lugar = form.pontos_8_lugar.data
        quiz.pontos_9_lugar = form.pontos_9_lugar.data
        quiz.pontos_10_lugar = form.pontos_10_lugar.data

        if form.temas.data:
            quiz.temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()
        else:
            quiz.temas = []

        if form.perguntas_selecionadas.data:
            quiz.perguntas = QuizPergunta.query.filter(QuizPergunta.pergunta_id.in_(form.perguntas_selecionadas.data)).all()
        else:
            quiz.perguntas = []
        
        db.session.commit()
        flash('Quiz atualizado com sucesso!', 'success')
        return redirect(url_for('quiz_ui.list_quizes'))

    return render_template('quiz/form.html', form=form, title='Editar Quiz', quiz=quiz)

@quiz_ui_bp.route('/<int:quiz_id>/delete', methods=['POST'])
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    try:
        db.session.delete(quiz)
        db.session.commit()
        flash('Quiz excluído com sucesso! (As perguntas continuam disponíveis no Banco de Perguntas).', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir quiz: {str(e)}', 'danger')
    return redirect(url_for('quiz_ui.list_quizes'))


# ============================================================
# BANCO DE PERGUNTAS INDEPENDENTE (CLASSIFICADO POR TEMAS)
# ============================================================

@quiz_ui_bp.route('/banco-perguntas')
def banco_perguntas():
    tema_filtro = request.args.get('tema_id', type=int)
    busca = request.args.get('q', '').strip()

    query = QuizPergunta.query
    if tema_filtro:
        query = query.join(QuizPergunta.temas).filter(TemaInteresse.temas_interesse_id == tema_filtro)
    if busca:
        query = query.filter(QuizPergunta.pergunta_enunciado.ilike(f"%{busca}%"))

    perguntas = query.order_by(QuizPergunta.pergunta_id.desc()).all()
    todos_temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()

    return render_template(
        'quiz/banco_perguntas.html',
        perguntas=perguntas,
        temas=todos_temas,
        tema_filtro=tema_filtro,
        busca=busca
    )

@quiz_ui_bp.route('/banco-perguntas/new', methods=['GET', 'POST'])
def create_pergunta_banco():
    form = PerguntaForm()
    temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} ({t.temas_interesse_tag or ''})") for t in temas]

    quiz_id_redirect = request.args.get('quiz_id', type=int)

    if form.validate_on_submit():
        nova_pergunta = QuizPergunta(
            pergunta_ordem=form.pergunta_ordem.data,
            pergunta_enunciado=form.pergunta_enunciado.data,
            pergunta_imagem_url=form.pergunta_imagem_url.data or None,
            tempo_limite_segundos=form.tempo_limite_segundos.data,
            pontos_base=form.pontos_base.data
        )
        if form.temas.data:
            nova_pergunta.temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()

        db.session.add(nova_pergunta)
        db.session.flush()

        # Cria as 4 alternativas
        letras = ['A', 'B', 'C', 'D']
        textos = [
            form.alt_a_texto.data,
            form.alt_b_texto.data,
            form.alt_c_texto.data,
            form.alt_d_texto.data
        ]
        correta_letra = form.correta.data

        for letra, texto in zip(letras, textos):
            alt = QuizAlternativa(
                pergunta_id=nova_pergunta.pergunta_id,
                alternativa_letra=letra,
                alternativa_texto=texto[:100],
                is_correta=(letra == correta_letra)
            )
            db.session.add(alt)

        # Se veio de um quiz específico, já vincula a ele
        if quiz_id_redirect:
            quiz_target = Quiz.query.get(quiz_id_redirect)
            if quiz_target:
                quiz_target.perguntas.append(nova_pergunta)

        db.session.commit()
        flash('Pergunta cadastrada no Banco com sucesso!', 'success')

        if quiz_id_redirect:
            return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id_redirect))
        return redirect(url_for('quiz_ui.banco_perguntas'))

    return render_template('quiz/pergunta_form.html', form=form, title='Nova Pergunta no Banco', quiz_id_redirect=quiz_id_redirect)

@quiz_ui_bp.route('/banco-perguntas/<int:pergunta_id>/edit', methods=['GET', 'POST'])
def edit_pergunta_banco(pergunta_id):
    pergunta = QuizPergunta.query.get_or_404(pergunta_id)
    form = PerguntaForm(obj=pergunta)
    temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} ({t.temas_interesse_tag or ''})") for t in temas]

    quiz_id_redirect = request.args.get('quiz_id', type=int)

    if request.method == 'GET':
        form.temas.data = [t.temas_interesse_id for t in pergunta.temas]
        alts_map = {alt.alternativa_letra: alt for alt in pergunta.alternativas}
        if 'A' in alts_map:
            form.alt_a_texto.data = alts_map['A'].alternativa_texto
            if alts_map['A'].is_correta: form.correta.data = 'A'
        if 'B' in alts_map:
            form.alt_b_texto.data = alts_map['B'].alternativa_texto
            if alts_map['B'].is_correta: form.correta.data = 'B'
        if 'C' in alts_map:
            form.alt_c_texto.data = alts_map['C'].alternativa_texto
            if alts_map['C'].is_correta: form.correta.data = 'C'
        if 'D' in alts_map:
            form.alt_d_texto.data = alts_map['D'].alternativa_texto
            if alts_map['D'].is_correta: form.correta.data = 'D'

    if form.validate_on_submit():
        pergunta.pergunta_ordem = form.pergunta_ordem.data
        pergunta.pergunta_enunciado = form.pergunta_enunciado.data
        pergunta.pergunta_imagem_url = form.pergunta_imagem_url.data or None
        pergunta.tempo_limite_segundos = form.tempo_limite_segundos.data
        pergunta.pontos_base = form.pontos_base.data

        if form.temas.data:
            pergunta.temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()
        else:
            pergunta.temas = []

        correta_letra = form.correta.data
        alts_map = {alt.alternativa_letra: alt for alt in pergunta.alternativas}
        novos_textos = {
            'A': form.alt_a_texto.data[:100],
            'B': form.alt_b_texto.data[:100],
            'C': form.alt_c_texto.data[:100],
            'D': form.alt_d_texto.data[:100],
        }

        for letra, texto in novos_textos.items():
            if letra in alts_map:
                alts_map[letra].alternativa_texto = texto
                alts_map[letra].is_correta = (letra == correta_letra)
            else:
                nova_alt = QuizAlternativa(
                    pergunta_id=pergunta.pergunta_id,
                    alternativa_letra=letra,
                    alternativa_texto=texto,
                    is_correta=(letra == correta_letra)
                )
                db.session.add(nova_alt)

        db.session.commit()
        flash('Pergunta atualizada com sucesso!', 'success')
        
        if quiz_id_redirect:
            return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id_redirect))
        return redirect(url_for('quiz_ui.banco_perguntas'))

    return render_template('quiz/pergunta_form.html', form=form, pergunta=pergunta, title='Editar Pergunta', quiz_id_redirect=quiz_id_redirect)

@quiz_ui_bp.route('/banco-perguntas/<int:pergunta_id>/delete', methods=['POST'])
def delete_pergunta_banco(pergunta_id):
    pergunta = QuizPergunta.query.get_or_404(pergunta_id)
    quiz_id_redirect = request.args.get('quiz_id', type=int)
    db.session.delete(pergunta)
    db.session.commit()
    flash('Pergunta removida do Banco com sucesso!', 'success')
    if quiz_id_redirect:
        return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id_redirect))
    return redirect(url_for('quiz_ui.banco_perguntas'))


# ============================================================
# GERENCIAMENTO DE PERGUNTAS DENTRO DE UM QUIZ
# ============================================================

@quiz_ui_bp.route('/<int:quiz_id>/perguntas')
def list_perguntas(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    # Perguntas disponíveis no banco que ainda não estão vinculadas
    perguntas_ja_no_quiz = [p.pergunta_id for p in quiz.perguntas]
    perguntas_disponiveis = QuizPergunta.query.filter(~QuizPergunta.pergunta_id.in_(perguntas_ja_no_quiz) if perguntas_ja_no_quiz else True).all()
    
    return render_template(
        'quiz/perguntas.html',
        quiz=quiz,
        perguntas_disponiveis=perguntas_disponiveis
    )

@quiz_ui_bp.route('/<int:quiz_id>/perguntas/vincular', methods=['POST'])
def vincular_pergunta_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    pergunta_id = request.form.get('pergunta_id', type=int)
    if pergunta_id:
        pergunta = QuizPergunta.query.get(pergunta_id)
        if pergunta and pergunta not in quiz.perguntas:
            quiz.perguntas.append(pergunta)
            db.session.commit()
            flash(f'Pergunta #{pergunta_id} vinculada ao Quiz com sucesso!', 'success')
    return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id))

@quiz_ui_bp.route('/<int:quiz_id>/perguntas/<int:pergunta_id>/desvincular', methods=['POST'])
def desvincular_pergunta_quiz(quiz_id, pergunta_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    pergunta = QuizPergunta.query.get_or_404(pergunta_id)
    if pergunta in quiz.perguntas:
        quiz.perguntas.remove(pergunta)
        db.session.commit()
        flash(f'Pergunta #{pergunta_id} desvinculada deste Quiz (permanece no Banco de Perguntas).', 'success')
    return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id))


# ============================================================
# AGENDAMENTOS E APLICAÇÕES
# ============================================================

@quiz_ui_bp.route('/aplicacoes')
def list_aplicacoes():
    aplicacoes = QuizAplicacao.query.order_by(QuizAplicacao.data_hora_prevista.desc()).all()
    return render_template('quiz/aplicacoes.html', aplicacoes=aplicacoes)

@quiz_ui_bp.route('/aplicacoes/new', methods=['GET', 'POST'])
def create_aplicacao():
    form = AplicacaoQuizForm()
    
    req_quiz_id = request.args.get('quiz_id', type=int)
    if req_quiz_id and request.method == 'GET':
        quiz_obj = Quiz.query.get(req_quiz_id)
        if quiz_obj:
            form.quiz_id.data = quiz_obj

    if form.validate_on_submit():
        quiz = form.quiz_id.data
        uc = form.uc_id.data
        channel_id = form.discord_channel_id.data or uc.uc_channel_id

        nova_app = QuizAplicacao(
            quiz_id=quiz.quiz_id,
            uc_id=uc.uc_id,
            data_hora_prevista=form.data_hora_prevista.data,
            discord_channel_id=channel_id,
            status='Agendado',
            pontos_1_lugar=quiz.pontos_1_lugar if quiz.pontos_1_lugar is not None else 1.00,
            pontos_2_lugar=quiz.pontos_2_lugar if quiz.pontos_2_lugar is not None else 1.00,
            pontos_3_lugar=quiz.pontos_3_lugar if quiz.pontos_3_lugar is not None else 1.00,
            pontos_4_lugar=quiz.pontos_4_lugar if quiz.pontos_4_lugar is not None else 0.80,
            pontos_5_lugar=quiz.pontos_5_lugar if quiz.pontos_5_lugar is not None else 0.80,
            pontos_6_lugar=quiz.pontos_6_lugar if quiz.pontos_6_lugar is not None else 0.80,
            pontos_7_lugar=quiz.pontos_7_lugar if quiz.pontos_7_lugar is not None else 0.50,
            pontos_8_lugar=quiz.pontos_8_lugar if quiz.pontos_8_lugar is not None else 0.50,
            pontos_9_lugar=quiz.pontos_9_lugar if quiz.pontos_9_lugar is not None else 0.50,
            pontos_10_lugar=quiz.pontos_10_lugar if quiz.pontos_10_lugar is not None else 0.50,
        )
        db.session.add(nova_app)
        db.session.commit()
        flash('Aplicação do Quiz agendada com sucesso!', 'success')
        return redirect(url_for('quiz_ui.list_aplicacoes'))

    return render_template('quiz/aplicacao_form.html', form=form, title='Agendar Aplicação de Quiz')

@quiz_ui_bp.route('/aplicacoes/<int:aplicacao_id>/edit', methods=['GET', 'POST'])
def edit_aplicacao(aplicacao_id):
    aplicacao = QuizAplicacao.query.get_or_404(aplicacao_id)
    form = AplicacaoQuizForm(obj=aplicacao)

    if request.method == 'GET':
        form.quiz_id.data = aplicacao.quiz
        form.uc_id.data = aplicacao.uc
        form.data_hora_prevista.data = aplicacao.data_hora_prevista
        form.discord_channel_id.data = aplicacao.discord_channel_id

    if form.validate_on_submit():
        quiz = form.quiz_id.data
        uc = form.uc_id.data
        channel_id = form.discord_channel_id.data or uc.uc_channel_id

        aplicacao.quiz_id = quiz.quiz_id
        aplicacao.uc_id = uc.uc_id
        aplicacao.data_hora_prevista = form.data_hora_prevista.data
        aplicacao.discord_channel_id = channel_id
        
        # Sincroniza pontos com o Quiz selecionado
        if quiz:
            aplicacao.pontos_1_lugar = quiz.pontos_1_lugar
            aplicacao.pontos_2_lugar = quiz.pontos_2_lugar
            aplicacao.pontos_3_lugar = quiz.pontos_3_lugar
            aplicacao.pontos_4_lugar = quiz.pontos_4_lugar
            aplicacao.pontos_5_lugar = quiz.pontos_5_lugar
            aplicacao.pontos_6_lugar = quiz.pontos_6_lugar
            aplicacao.pontos_7_lugar = quiz.pontos_7_lugar
            aplicacao.pontos_8_lugar = quiz.pontos_8_lugar
            aplicacao.pontos_9_lugar = quiz.pontos_9_lugar
            aplicacao.pontos_10_lugar = quiz.pontos_10_lugar

        db.session.commit()
        flash(f'Agendamento #{aplicacao.aplicacao_id} atualizado com sucesso!', 'success')
        return redirect(url_for('quiz_ui.list_aplicacoes'))

    return render_template('quiz/aplicacao_form.html', form=form, title=f'Editar Agendamento #{aplicacao.aplicacao_id}', aplicacao=aplicacao)

@quiz_ui_bp.route('/<int:quiz_id>/iniciar-imediato', methods=['GET', 'POST'])
def iniciar_quiz_imediato(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    if not quiz.perguntas:
        flash('Este quiz ainda não possui perguntas associadas. Adicione perguntas antes de iniciar!', 'warning')
        return redirect(url_for('quiz_ui.list_perguntas', quiz_id=quiz_id))

    ucs = Uc.query.order_by(Uc.uc_nome).all()

    if request.method == 'POST':
        uc_id = request.form.get('uc_id', type=int)
        if not uc_id:
            flash('Por favor, selecione uma Unidade Curricular.', 'danger')
            return redirect(url_for('quiz_ui.iniciar_quiz_imediato', quiz_id=quiz_id))

        uc = Uc.query.get_or_404(uc_id)
        channel_id = request.form.get('discord_channel_id') or uc.uc_channel_id

        nova_app = QuizAplicacao(
            quiz_id=quiz.quiz_id,
            uc_id=uc.uc_id,
            data_hora_prevista=datetime.now(),
            discord_channel_id=channel_id,
            status='Agendado',
            pontos_1_lugar=quiz.pontos_1_lugar if quiz.pontos_1_lugar is not None else 1.00,
            pontos_2_lugar=quiz.pontos_2_lugar if quiz.pontos_2_lugar is not None else 1.00,
            pontos_3_lugar=quiz.pontos_3_lugar if quiz.pontos_3_lugar is not None else 1.00,
            pontos_4_lugar=quiz.pontos_4_lugar if quiz.pontos_4_lugar is not None else 0.80,
            pontos_5_lugar=quiz.pontos_5_lugar if quiz.pontos_5_lugar is not None else 0.80,
            pontos_6_lugar=quiz.pontos_6_lugar if quiz.pontos_6_lugar is not None else 0.80,
            pontos_7_lugar=quiz.pontos_7_lugar if quiz.pontos_7_lugar is not None else 0.50,
            pontos_8_lugar=quiz.pontos_8_lugar if quiz.pontos_8_lugar is not None else 0.50,
            pontos_9_lugar=quiz.pontos_9_lugar if quiz.pontos_9_lugar is not None else 0.50,
            pontos_10_lugar=quiz.pontos_10_lugar if quiz.pontos_10_lugar is not None else 0.50,
        )
        db.session.add(nova_app)
        db.session.commit()

        flash(f'🚀 Quiz "{quiz.quiz_titulo}" disparado para início imediato na UC "{uc.uc_nome}" (Canal {channel_id})!', 'success')
        return redirect(url_for('quiz_ui.list_aplicacoes'))

    return render_template('quiz/iniciar_imediato.html', quiz=quiz, ucs=ucs)

@quiz_ui_bp.route('/aplicacoes/<int:aplicacao_id>/iniciar', methods=['POST'])
def iniciar_aplicacao(aplicacao_id):
    aplicacao = QuizAplicacao.query.get_or_404(aplicacao_id)
    if aplicacao.status in ['Concluido', 'Cancelado']:
        flash('Esta aplicação já foi concluída ou cancelada.', 'danger')
        return redirect(url_for('quiz_ui.list_aplicacoes'))
    
    canal_override = request.form.get('discord_channel_id', '').strip()
    if canal_override:
        aplicacao.discord_channel_id = canal_override
    elif not aplicacao.discord_channel_id and aplicacao.uc and aplicacao.uc.uc_channel_id:
        aplicacao.discord_channel_id = aplicacao.uc.uc_channel_id
    
    aplicacao.data_hora_prevista = datetime.now()
    aplicacao.status = 'Agendado'
    db.session.commit()
    flash(f'🚀 Quiz #{aplicacao.aplicacao_id} disparado para execução imediata no canal {aplicacao.discord_channel_id}!', 'success')
    return redirect(url_for('quiz_ui.list_aplicacoes'))

@quiz_ui_bp.route('/aplicacoes/<int:aplicacao_id>/cancelar', methods=['POST'])
def cancelar_aplicacao(aplicacao_id):
    aplicacao = QuizAplicacao.query.get_or_404(aplicacao_id)
    aplicacao.status = 'Cancelado'
    db.session.commit()
    flash('Aplicação cancelada!', 'success')
    return redirect(url_for('quiz_ui.list_aplicacoes'))

@quiz_ui_bp.route('/aplicacoes/<int:aplicacao_id>/delete', methods=['POST'])
def delete_aplicacao(aplicacao_id):
    aplicacao = QuizAplicacao.query.get_or_404(aplicacao_id)
    try:
        db.session.delete(aplicacao)
        db.session.commit()
        flash(f'Agendamento #{aplicacao_id} excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir agendamento: {str(e)}', 'danger')
    return redirect(url_for('quiz_ui.list_aplicacoes'))

@quiz_ui_bp.route('/aplicacoes/<int:aplicacao_id>/resultado')
def resultado_aplicacao(aplicacao_id):
    aplicacao = QuizAplicacao.query.get_or_404(aplicacao_id)
    participantes = QuizParticipante.query.filter_by(aplicacao_id=aplicacao_id).order_by(QuizParticipante.pontuacao_total.desc()).all()
    respostas = QuizResposta.query.filter_by(aplicacao_id=aplicacao_id).order_by(QuizResposta.data_hora_resposta.asc()).all()

    # Perguntas vinculadas ao Quiz
    quiz = aplicacao.quiz
    perguntas = quiz.perguntas if quiz else []

    # Estatísticas individuais por pergunta
    perguntas_stats = []
    for p in perguntas:
        resp_p = [r for r in respostas if r.pergunta_id == p.pergunta_id]
        total_p = len(resp_p)
        acertos_p = sum(1 for r in resp_p if r.is_correta)
        erros_p = total_p - acertos_p
        pct_acertos = (acertos_p / total_p * 100) if total_p > 0 else 0
        pct_erros = (erros_p / total_p * 100) if total_p > 0 else 0
        tempo_medio_ms = (sum(r.tempo_gasto_ms for r in resp_p) / total_p) if total_p > 0 else 0

        # Estatísticas por alternativa
        alts_stats = []
        for alt in p.alternativas:
            count_alt = sum(1 for r in resp_p if r.alternativa_id == alt.alternativa_id)
            pct_alt = (count_alt / total_p * 100) if total_p > 0 else 0
            alts_stats.append({
                'alternativa': alt,
                'count': count_alt,
                'pct': pct_alt
            })

        perguntas_stats.append({
            'pergunta': p,
            'total_respostas': total_p,
            'acertos': acertos_p,
            'erros': erros_p,
            'pct_acertos': pct_acertos,
            'pct_erros': pct_erros,
            'tempo_medio_ms': tempo_medio_ms,
            'alternativas': alts_stats
        })

    # Estatísticas gerais do topo
    total_participantes = len(participantes)
    total_respostas = len(respostas)
    total_acertos_global = sum(1 for r in respostas if r.is_correta)
    pct_acertos_global = (total_acertos_global / total_respostas * 100) if total_respostas > 0 else 0
    tempo_medio_global_s = (sum(r.tempo_gasto_ms for r in respostas) / total_respostas / 1000.0) if total_respostas > 0 else 0

    stats_gerais = {
        'total_participantes': total_participantes,
        'total_perguntas': len(perguntas),
        'total_respostas': total_respostas,
        'pct_acertos': pct_acertos_global,
        'tempo_medio_s': tempo_medio_global_s
    }

    return render_template(
        'quiz/resultado.html',
        aplicacao=aplicacao,
        participantes=participantes,
        respostas=respostas,
        stats_gerais=stats_gerais,
        perguntas_stats=perguntas_stats
    )
