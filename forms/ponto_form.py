from flask_wtf import FlaskForm
from wtforms import FloatField, SelectField, TextAreaField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired
from wtforms_sqlalchemy.fields import QuerySelectField
from models import Usuario, Uc
from datetime import datetime, timezone, timedelta

def get_usuarios():
    return Usuario.query.all()

def get_ucs():
    return Uc.query.all()

def get_current_time_sp():
    return datetime.now(timezone(timedelta(hours=-3)))

class PontoForm(FlaskForm):
    uc_id = QuerySelectField('UC', query_factory=get_ucs, allow_blank=True, blank_text='-- Selecione a UC --', get_label='uc_nome', validators=[DataRequired()])
    usuario_id = SelectField('Usuário', coerce=int, choices=[], validators=[DataRequired()])
    dt_ponto = DateTimeLocalField('Data e Hora', format='%Y-%m-%dT%H:%M', default=get_current_time_sp, validators=[DataRequired()])
    tipo_ponto = SelectField('Tipo de Ponto', choices=[('Presença', 'Presença'), ('Participação', 'Participação'), ('Kahoot', 'Kahoot'), ('Curso', 'Curso')], validators=[DataRequired()])
    num_ponto = FloatField('Número de Pontos', validators=[DataRequired()])
    comentario_ponto = TextAreaField('Comentário', validators=[DataRequired()])
    
    submit = SubmitField('Salvar')
