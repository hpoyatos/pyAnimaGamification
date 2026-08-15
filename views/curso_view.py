from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.curso import Curso
from forms.curso_form import CursoForm

curso_ui_bp = Blueprint('curso_ui', __name__, url_prefix='/ui/cursos')

def _populate_prerequisito_choices(form, current_curso_id=None):
    query = Curso.query.order_by(Curso.curso_parceira.asc(), Curso.curso_nome.asc())
    if current_curso_id:
        query = query.filter(Curso.curso_id != current_curso_id)
    cursos = query.all()
    
    choices = [(0, '--- Nenhum Pré-requisito ---')]
    for c in cursos:
        ch = f" ({c.curso_carga_horaria}h)" if c.curso_carga_horaria else ""
        choices.append((c.curso_id, f"[{c.curso_parceira}] {c.curso_nome}{ch}"))
    form.curso_prerequisito_id.choices = choices

@curso_ui_bp.route('/')
def list_cursos():
    cursos = Curso.query.order_by(Curso.curso_parceira.asc(), Curso.curso_nome.asc()).all()
    return render_template('curso/list.html', cursos=cursos)

@curso_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_curso():
    form = CursoForm()
    _populate_prerequisito_choices(form)

    if form.validate_on_submit():
        novo_curso = Curso()
        form.populate_obj(novo_curso)
        if form.curso_prerequisito_id.data == 0:
            novo_curso.curso_prerequisito_id = None
        db.session.add(novo_curso)
        db.session.commit()
        flash('Curso criado com sucesso!', 'success')
        return redirect(url_for('curso_ui.list_cursos'))
    return render_template('curso/form.html', form=form, title="Novo Curso")

@curso_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_curso(id):
    curso = Curso.query.get_or_404(id)
    form = CursoForm(obj=curso)
    _populate_prerequisito_choices(form, current_curso_id=id)

    if request.method == 'GET':
        form.curso_prerequisito_id.data = curso.curso_prerequisito_id or 0

    if form.validate_on_submit():
        form.populate_obj(curso)
        if form.curso_prerequisito_id.data == 0:
            curso.curso_prerequisito_id = None
        db.session.commit()
        flash('Curso atualizado com sucesso!', 'success')
        return redirect(url_for('curso_ui.list_cursos'))
    return render_template('curso/form.html', form=form, title="Editar Curso", curso=curso)

@curso_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_curso(id):
    curso = Curso.query.get_or_404(id)
    try:
        db.session.delete(curso)
        db.session.commit()
        flash('Curso excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir curso: {str(e)}', 'danger')
    return redirect(url_for('curso_ui.list_cursos'))
