from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.uc import Uc
from forms.uc_form import UcForm

uc_ui_bp = Blueprint('uc_ui', __name__, url_prefix='/ui/ucs')

@uc_ui_bp.route('/')
def list_ucs():
    ucs = Uc.query.all()
    return render_template('uc/list.html', ucs=ucs)

@uc_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_uc():
    form = UcForm()
    if form.validate_on_submit():
        nova_uc = Uc(
            uc_nome=form.uc_nome.data,
            uc_role_id=form.uc_role_id.data,
            uc_ano=form.uc_ano.data,
            uc_semestre=form.uc_semestre.data,
            uc_dia_semana=form.uc_dia_semana.data
        )
        db.session.add(nova_uc)
        db.session.commit()
        flash('UC criada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Nova UC")

@uc_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_uc(id):
    uc = Uc.query.get_or_404(id)
    form = UcForm(obj=uc)
    if form.validate_on_submit():
        form.populate_obj(uc)
        db.session.commit()
        flash('UC atualizada com sucesso!', 'success')
        return redirect(url_for('uc_ui.list_ucs'))
    return render_template('uc/form.html', form=form, title="Editar UC")

@uc_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_uc(id):
    uc = Uc.query.get_or_404(id)
    db.session.delete(uc)
    db.session.commit()
    flash('UC excluída com sucesso!', 'success')
    return redirect(url_for('uc_ui.list_ucs'))
