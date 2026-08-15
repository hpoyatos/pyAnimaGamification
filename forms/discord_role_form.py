from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length

class AnimaDiscordRoleForm(FlaskForm):
    role_id = StringField('ID do Cargo (Role ID do Discord)', validators=[DataRequired(), Length(min=15, max=20)])
    role_descricao = StringField('Descrição / Nome do Cargo', validators=[DataRequired(), Length(max=150)])
    role_ativo = BooleanField('Cargo Ativo (Disponível nos Menus / Turmas)', default=True)
    submit = SubmitField('Salvar Cargo')
