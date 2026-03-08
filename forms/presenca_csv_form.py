from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import DateField, DecimalField, SubmitField
from wtforms.validators import DataRequired
from wtforms_sqlalchemy.fields import QuerySelectField
from models.uc import Uc
from datetime import date

def get_ucs():
    return Uc.query.order_by(Uc.uc_nome).all()

class PresencaCsvForm(FlaskForm):
    uc_id = QuerySelectField('Unidade Curricular (UC)', query_factory=get_ucs, allow_blank=True, get_label='uc_nome', validators=[DataRequired()])
    data_aula = DateField('Data da Aula', default=date.today, validators=[DataRequired()])
    pontos = DecimalField('Pontos Computados', default=0.7, places=2, validators=[DataRequired()])
    arquivo = FileField('Relatório do Microsoft Teams (.csv)', validators=[
        FileRequired(message="O arquivo CSV é obrigatório."),
        FileAllowed(['csv'], 'Somente arquivos .csv são permitidos!')
    ])
    submit = SubmitField('Processar Presenças')
