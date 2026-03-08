from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.usuario import Usuario
from models.ponto import Ponto
from sqlalchemy import func
from forms.usuario_form import UsuarioForm
from forms.extrato_form import ExtratoForm

usuario_ui_bp = Blueprint('usuario_ui', __name__, url_prefix='/ui/usuarios')

@usuario_ui_bp.route('/extrato', methods=['GET', 'POST'])
def extrato_pontos():
    form = ExtratoForm()
    selected_user = None
    total_pontos = 0
    extratos = []

    # Se um usuário vier por GET (da lista de alunos, por exemplo)
    user_id = request.args.get('user_id')
    if user_id:
        user = Usuario.query.get(user_id)
        if user:
            form.usuario_id.data = user
            selected_user = user
    
    # Processa o POST ou se já tiver usuário pelo GET
    if form.validate_on_submit() or selected_user:
        if not selected_user:
            selected_user = form.usuario_id.data
        
        # Total de Pontos
        total = db.session.query(func.sum(Ponto.num_ponto)).filter(Ponto.usuario_id == selected_user.usuario_id).scalar()
        total_pontos = total if total else 0
        
        # Extrato detalhado
        extratos = Ponto.query.filter(Ponto.usuario_id == selected_user.usuario_id)\
                              .order_by(Ponto.dt_ponto.desc()).all()
                              
    return render_template('usuario/extrato.html', form=form, selected_user=selected_user, total_pontos=total_pontos, extratos=extratos)

@usuario_ui_bp.route('/')
def list_usuarios():
    usuarios = Usuario.query.all()
    return render_template('usuario/list.html', usuarios=usuarios)

@usuario_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_usuario():
    form = UsuarioForm()
    if form.validate_on_submit():
        novo_usuario = Usuario(
            usuario_nome=form.usuario_nome.data,
            usuario_email=form.usuario_email.data,
            usuario_ra=form.usuario_ra.data,
            usuario_discord_id=form.usuario_discord_id.data,
            usuario_discord_name=form.usuario_discord_name.data,
            usuario_validado=form.usuario_validado.data,
            usuario_validado_data=form.usuario_validado_data.data if form.usuario_validado_data.data else None
        )
        db.session.add(novo_usuario)
        db.session.commit()
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('usuario_ui.list_usuarios'))
    return render_template('usuario/form.html', form=form, title="Novo Usuário")

@usuario_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        form.populate_obj(usuario)
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('usuario_ui.list_usuarios'))
    return render_template('usuario/form.html', form=form, title="Editar Usuário")

@usuario_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuário excluído com sucesso!', 'success')
    return redirect(url_for('usuario_ui.list_usuarios'))
