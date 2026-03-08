from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class UcForm(FlaskForm):
    uc_nome = StringField('Nome da UC', validators=[DataRequired(), Length(max=100)])
    uc_role_id = StringField('Role ID (Discord)', validators=[Optional(), Length(max=20)])
    uc_ano = StringField('Ano', validators=[Optional(), Length(max=4)])
    uc_semestre = StringField('Semestre', validators=[Optional(), Length(max=1)])
    uc_dia_semana = IntegerField('Dia da Semana (0-6)', validators=[Optional()])
    
    submit = SubmitField('Salvar')
