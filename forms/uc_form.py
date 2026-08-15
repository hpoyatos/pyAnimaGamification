from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

DIAS_SEMANA_CHOICES = [
    ('', 'Selecione o dia da semana (opcional)...'),
    ('1', 'Segunda-feira'),
    ('2', 'Terça-feira'),
    ('3', 'Quarta-feira'),
    ('4', 'Quinta-feira'),
    ('5', 'Sexta-feira'),
    ('6', 'Sábado'),
    ('0', 'Domingo')
]

class UcForm(FlaskForm):
    uc_nome = StringField('Nome da UC / Disciplina', validators=[DataRequired(), Length(max=150)])
    uc_ano_semestre = StringField('Ano / Semestre (ex: 2026/02)', validators=[DataRequired(), Length(max=10)])
    uc_discord_role = StringField('ID da Role do Discord (Cargo)', validators=[DataRequired(), Length(max=25)])
    uc_channel_id = StringField('ID do Canal do Discord (Texto/Voz)', validators=[Optional(), Length(max=25)])
    uc_dia_semana = SelectField('Dia da Semana da Aula', choices=DIAS_SEMANA_CHOICES, validators=[Optional()])
    
    submit = SubmitField('Salvar UC')
