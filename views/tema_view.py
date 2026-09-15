import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy import or_
from extensions import db
from models.quiz import TemaInteresse
from models.discord_role import AnimaDiscordRole
from forms.tema_form import TemaInteresseForm

logger = logging.getLogger("tema_ui")
tema_ui_bp = Blueprint('tema_ui', __name__, url_prefix='/ui/temas')

def _garantir_coluna_db():
    try:
        with db.engine.connect() as conn:
            try:
                conn.execute(db.text("ALTER TABLE anima_temas_interesse ADD COLUMN discord_role_id VARCHAR(20) NULL"))
                conn.commit()
            except Exception:
                pass
    except Exception:
        pass

def _populate_roles_choices(form, current_role_id=None):
    role_query = AnimaDiscordRole.query
    if current_role_id:
        role_query = role_query.filter(or_(AnimaDiscordRole.role_ativo == True, AnimaDiscordRole.role_id == current_role_id))
    else:
        role_query = role_query.filter(AnimaDiscordRole.role_ativo == True)
        
    roles = role_query.order_by(AnimaDiscordRole.role_descricao.asc()).all()
    choices = [('', '--- Nenhum Cargo Vinculado ---')]
    for r in roles:
        tag = "" if r.role_ativo else " (Inativo)"
        choices.append((r.role_id, f"{r.role_descricao}{tag} ({r.role_id})"))
    form.discord_role_id.choices = choices

@tema_ui_bp.route('/')
def list_temas():
    _garantir_coluna_db()
    temas = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome.asc()).all()
    return render_template('tema/list.html', temas=temas)

@tema_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_tema():
    _garantir_coluna_db()
    form = TemaInteresseForm()
    _populate_roles_choices(form)

    if form.validate_on_submit():
        novo_tema = TemaInteresse(
            temas_interesse_nome=form.temas_interesse_nome.data.strip(),
            temas_interesse_tag=form.temas_interesse_tag.data.strip().lstrip('#') if form.temas_interesse_tag.data else None,
            temas_interesse_descricao=form.temas_interesse_descricao.data.strip() if form.temas_interesse_descricao.data else None,
            discord_role_id=form.discord_role_id.data.strip() if form.discord_role_id.data else None
        )
        db.session.add(novo_tema)
        db.session.commit()
        flash('Tema de Interesse cadastrado com sucesso!', 'success')
        return redirect(url_for('tema_ui.list_temas'))

    return render_template('tema/form.html', form=form, title="Novo Tema de Interesse")

@tema_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_tema(id):
    _garantir_coluna_db()
    tema = TemaInteresse.query.get_or_404(id)
    form = TemaInteresseForm(obj=tema)
    _populate_roles_choices(form, current_role_id=tema.discord_role_id)

    if form.validate_on_submit():
        tema.temas_interesse_nome = form.temas_interesse_nome.data.strip()
        tema.temas_interesse_tag = form.temas_interesse_tag.data.strip().lstrip('#') if form.temas_interesse_tag.data else None
        tema.temas_interesse_descricao = form.temas_interesse_descricao.data.strip() if form.temas_interesse_descricao.data else None
        tema.discord_role_id = form.discord_role_id.data.strip() if form.discord_role_id.data else None
        db.session.commit()
        flash(f"Tema '{tema.temas_interesse_nome}' atualizado com sucesso!", 'success')
        return redirect(url_for('tema_ui.list_temas'))

    return render_template('tema/form.html', form=form, title="Editar Tema de Interesse", tema=tema)

@tema_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_tema(id):
    _garantir_coluna_db()
    tema = TemaInteresse.query.get_or_404(id)
    try:
        nome = tema.temas_interesse_nome
        db.session.delete(tema)
        db.session.commit()
        flash(f"Tema '{nome}' excluído com sucesso!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir tema: {str(e)}', 'danger')
    return redirect(url_for('tema_ui.list_temas'))
