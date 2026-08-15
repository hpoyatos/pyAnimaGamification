from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class UCForm(FlaskForm):
    uc_nome = StringField('Nome da UC (Disciplina)', validators=[DataRequired(), Length(max=100)])
    
    uc_ano_semestre = StringField('Ano/Semestre (Ex: 2026/1)', validators=[DataRequired(), Length(max=10)])
    
    uc_discord_role = SelectField('Cargo Discord (Role Vinculada)', validators=[DataRequired()])
    
    uc_channel_id = StringField('ID do Canal Discord (Opcional)', validators=[Optional(), Length(max=20)])
    
    uc_dia_semana = SelectField('Dia da Semana', choices=[
        ('', '--- Selecione o Dia ---'),
        ('2', 'Segunda-feira'),
        ('3', 'Terça-feira'),
        ('4', 'Quarta-feira'),
        ('5', 'Quinta-feira'),
        ('6', 'Sexta-feira'),
        ('7', 'Sábado')
    ], validators=[Optional()])

    submit = SubmitField('Salvar UC')

# Alias for compatibility
UcForm = UCForm
