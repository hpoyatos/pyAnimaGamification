from flask import Blueprint, render_template, redirect, url_for, flash, request
from sqlalchemy import or_
from extensions import db
from models.uc import UC, Uc
from models.discord_role import AnimaDiscordRole
from forms.uc_form import UCForm, UcForm

uc_ui_bp = Blueprint('uc_ui', __name__, url_prefix='/ui/ucs')

def _populate_uc_role_choices(form, current_role_id=None):
    role_query = AnimaDiscordRole.query
    if current_role_id:
        role_query = role_query.filter(or_(AnimaDiscordRole.role_ativo == True, AnimaDiscordRole.role_id == current_role_id))
    else:
        role_query = role_query.filter(AnimaDiscordRole.role_ativo == True)

    roles = role_query.order_by(AnimaDiscordRole.role_descricao.asc()).all()
    choices = [('', '--- Selecione o Cargo do Discord ---')]
    for r in roles:
        tag = "" if r.role_ativo else " (Inativo)"
        choices.append((r.role_id, f"{r.role_descricao}{tag} ({r.role_id})"))
    form.uc_discord_role.choices = choices

@uc_ui_bp.route('/')
def list_ucs():
    ucs = UC.query.order_by(UC.uc_ano_semestre.desc(), UC.uc_nome.asc()).all()
    return render_template('uc/list.html', ucs=ucs)

@uc_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_uc():
    form = UCForm()
    _populate_uc_role_choices(form)

    if form.validate_on_submit():
        dia_sem = int(form.uc_dia_semana.data) if form.uc_dia_semana.data else None
        nova_uc = UC(
            uc_nome=form.uc_nome.data.strip(),
            uc_ano_semestre=form.uc_ano_semestre.data.strip(),
            uc_discord_role=form.uc_discord_role.data.strip(),
            uc_channel_id=form.uc_channel_id.data.strip() if form.uc_channel_id.data else None,
            uc_dia_semana=dia_sem
        )
        db.session.add(nova_uc)
        db.session.commit()
        flash('Unidade Curricular (UC) criada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Nova Unidade Curricular (UC)")

@uc_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_uc(id):
    uc = UC.query.get_or_404(id)
    form = UCForm(obj=uc)
    _populate_uc_role_choices(form, current_role_id=uc.uc_discord_role)

    if request.method == 'GET':
        form.uc_dia_semana.data = str(uc.uc_dia_semana) if uc.uc_dia_semana is not None else ''
        form.uc_discord_role.data = uc.uc_discord_role

    if form.validate_on_submit():
        dia_sem = int(form.uc_dia_semana.data) if form.uc_dia_semana.data else None
        uc.uc_nome = form.uc_nome.data.strip()
        uc.uc_ano_semestre = form.uc_ano_semestre.data.strip()
        uc.uc_discord_role = form.uc_discord_role.data.strip()
        uc.uc_channel_id = form.uc_channel_id.data.strip() if form.uc_channel_id.data else None
        uc.uc_dia_semana = dia_sem

        db.session.commit()
        flash('Unidade Curricular (UC) atualizada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Editar Unidade Curricular (UC)", uc=uc)

@uc_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_uc(id):
    uc = UC.query.get_or_404(id)
    try:
        db.session.delete(uc)
        db.session.commit()
        flash('UC excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Não foi possível excluir a UC: {str(e)}', 'danger')
    return redirect(url_for('uc_ui.list_ucs'))
