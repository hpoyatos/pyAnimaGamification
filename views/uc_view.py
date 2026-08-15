from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.uc import Uc
from forms.uc_form import UcForm

uc_ui_bp = Blueprint('uc_ui', __name__, url_prefix='/ui/ucs')

@uc_ui_bp.route('/')
def list_ucs():
    ucs = Uc.query.order_by(Uc.uc_ano_semestre.desc(), Uc.uc_nome.asc()).all()
    return render_template('uc/list.html', ucs=ucs)

@uc_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_uc():
    form = UcForm()
    if form.validate_on_submit():
        dia_sem = int(form.uc_dia_semana.data) if form.uc_dia_semana.data else None
        nova_uc = Uc(
            uc_nome=form.uc_nome.data,
            uc_ano_semestre=form.uc_ano_semestre.data,
            uc_discord_role=form.uc_discord_role.data,
            uc_channel_id=form.uc_channel_id.data or None,
            uc_dia_semana=dia_sem
        )
        db.session.add(nova_uc)
        db.session.commit()
        flash('Unidade Curricular (UC) criada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Nova Unidade Curricular (UC)")

@uc_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_uc(id):
    uc = Uc.query.get_or_404(id)
    form = UcForm(obj=uc)

    if request.method == 'GET':
        form.uc_dia_semana.data = str(uc.uc_dia_semana) if uc.uc_dia_semana is not None else ''

    if form.validate_on_submit():
        dia_sem = int(form.uc_dia_semana.data) if form.uc_dia_semana.data else None
        uc.uc_nome = form.uc_nome.data
        uc.uc_ano_semestre = form.uc_ano_semestre.data
        uc.uc_discord_role = form.uc_discord_role.data
        uc.uc_channel_id = form.uc_channel_id.data or None
        uc.uc_dia_semana = dia_sem

        db.session.commit()
        flash('Unidade Curricular (UC) atualizada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Editar Unidade Curricular (UC)", uc=uc)

@uc_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_uc(id):
    uc = Uc.query.get_or_404(id)
    try:
        db.session.delete(uc)
        db.session.commit()
        flash('UC excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Não foi possível excluir a UC: {str(e)}', 'danger')
    return redirect(url_for('uc_ui.list_ucs'))
