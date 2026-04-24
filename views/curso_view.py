from flask import Blueprint, render_template, redirect, url_for, flash
from extensions import db
from models.curso import Curso
from forms.curso_form import CursoForm

curso_ui_bp = Blueprint('curso_ui', __name__, url_prefix='/ui/cursos')

@curso_ui_bp.route('/')
def list_cursos():
    cursos = Curso.query.all()
    return render_template('curso/list.html', cursos=cursos)

@curso_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_curso():
    form = CursoForm()
    if form.validate_on_submit():
        novo_curso = Curso()
        form.populate_obj(novo_curso)
        db.session.add(novo_curso)
        db.session.commit()
        flash('Curso criado com sucesso!', 'success')
        return redirect(url_for('curso_ui.list_cursos'))
    return render_template('curso/form.html', form=form, title="Novo Curso")

@curso_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_curso(id):
    curso = Curso.query.get_or_404(id)
    form = CursoForm(obj=curso)
    if form.validate_on_submit():
        form.populate_obj(curso)
        db.session.commit()
        flash('Curso atualizado com sucesso!', 'success')
        return redirect(url_for('curso_ui.list_cursos'))
    return render_template('curso/form.html', form=form, title="Editar Curso")

@curso_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_curso(id):
    curso = Curso.query.get_or_404(id)
    db.session.delete(curso)
    db.session.commit()
    flash('Curso excluído com sucesso!', 'success')
    return redirect(url_for('curso_ui.list_cursos'))
