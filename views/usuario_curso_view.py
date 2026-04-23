from flask import Blueprint, render_template, redirect, url_for, flash
from extensions import db
from models.usuario_curso import UsuarioCurso
from forms.usuario_curso_form import UsuarioCursoForm

usuario_curso_ui_bp = Blueprint('usuario_curso_ui', __name__, url_prefix='/ui/matriculas')

@usuario_curso_ui_bp.route('/')
def list_matriculas():
    # O sqlalchemy faz os joins via relationships backref se precisamos do nome do curso ou user, 
    # ou podemos usar db.session.query... Faremos query all para mandar a entidade que possui a propriedade usuario e curso.
    matriculas = UsuarioCurso.query.all()
    return render_template('usuario_curso/list.html', matriculas=matriculas)

@usuario_curso_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_matricula():
    form = UsuarioCursoForm()
    if form.validate_on_submit():
        nova_matricula = UsuarioCurso(
            usuario_id=form.usuario_id.data.usuario_id,
            curso_id=form.curso_id.data.curso_id,
            usuario_redhat_id=form.usuario_redhat_id.data if form.usuario_redhat_id.data else None,
            usuario_redhat_email=form.usuario_redhat_email.data if form.usuario_redhat_email.data else None,
            usuario_curso_dt_solicitacao=form.usuario_curso_dt_solicitacao.data,
            usuario_curso_dt_inscricao=form.usuario_curso_dt_inscricao.data if form.usuario_curso_dt_inscricao.data else None,
            usuario_curso_situacao=form.usuario_curso_situacao.data
        )
        db.session.add(nova_matricula)
        db.session.commit()
        flash('Matrícula criada com sucesso!', 'success')
        return redirect(url_for('usuario_curso_ui.list_matriculas'))
    return render_template('usuario_curso/form.html', form=form, title="Nova Matrícula")

@usuario_curso_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_matricula(id):
    matricula = UsuarioCurso.query.get_or_404(id)
    form = UsuarioCursoForm(obj=matricula)
    # wtforms-sqlalchemy requer a instância completa no field quando instanciado a partir do objeto.
    # Populate_obj falha às vezes se os queryselectfields não estiverem carregados com as instâncias. Ele mapeia objeto para DB.
    if form.validate_on_submit():
        form.populate_obj(matricula)
        # Fix query select objects populating instance logic not id. 
        matricula.usuario_id = form.usuario_id.data.usuario_id
        matricula.curso_id = form.curso_id.data.curso_id
        db.session.commit()
        flash('Matrícula atualizada com sucesso!', 'success')
        return redirect(url_for('usuario_curso_ui.list_matriculas'))
    
    # Pre-select instances for forms
    if not form.is_submitted():
        form.usuario_id.data = matricula.usuario
        form.curso_id.data = matricula.curso
        
    return render_template('usuario_curso/form.html', form=form, title="Editar Matrícula")

@usuario_curso_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_matricula(id):
    matricula = UsuarioCurso.query.get_or_404(id)
    db.session.delete(matricula)
    db.session.commit()
    flash('Matrícula excluída com sucesso!', 'success')
    return redirect(url_for('usuario_curso_ui.list_matriculas'))

@usuario_curso_ui_bp.route('/download/<int:id>')
def download_certificado(id):
    matricula = UsuarioCurso.query.get_or_404(id)
    if not matricula.usuario_curso_certificado:
        flash('Certificado não disponível para esta matrícula.', 'warning')
        return redirect(url_for('usuario_curso_ui.list_matriculas'))
    
    from flask import send_file
    import io
    return send_file(
        io.BytesIO(matricula.usuario_curso_certificado),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"certificado_{matricula.usuario.usuario_nome}_{matricula.curso.curso_nome}.pdf"
    )
