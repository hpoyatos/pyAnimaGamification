from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateTimeLocalField, SubmitField
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired, Optional, Length
from models.usuario import Usuario
from models.curso import Curso

def usuario_query():
    return Usuario.query.order_by(Usuario.usuario_nome)

def curso_query():
    return Curso.query.order_by(Curso.curso_nome)

class UsuarioCursoForm(FlaskForm):
    usuario_id = QuerySelectField('Aluno', query_factory=usuario_query, allow_blank=False, get_label='usuario_nome', validators=[DataRequired()])
    curso_id = QuerySelectField('Curso', query_factory=curso_query, allow_blank=False, get_label='curso_nome', validators=[DataRequired()])
    
    usuario_redhat_id = StringField('Red Hat ID (se aplicável)', validators=[Optional(), Length(max=60)])
    
    usuario_curso_dt_solicitacao = DateTimeLocalField('Data da Solicitação', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    usuario_curso_dt_inscricao = DateTimeLocalField('Data Efetiva da Matrícula', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    
    usuario_curso_situacao = SelectField('Situação da Matrícula', choices=[
        ('Pendente', 'Pendente (Aguardando Plataforma)'),
        ('Concluído', 'Concluído (Ativo em plataforma)')
    ], validators=[DataRequired()])
    
    submit = SubmitField('Salvar Matrícula')
