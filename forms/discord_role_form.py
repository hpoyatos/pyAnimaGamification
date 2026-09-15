from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp

class AnimaDiscordRoleForm(FlaskForm):
    role_id = StringField('ID do Cargo (Role ID do Discord)', validators=[
        DataRequired(message="O ID do Cargo no Discord é obrigatório."),
        Length(min=15, max=25, message="O ID do Discord deve ter entre 15 e 25 caracteres numéricos."),
        Regexp(r'^\d+$', message="O ID do Cargo deve conter apenas dígitos numéricos (Snowflake ID do Discord).")
    ])
    role_descricao = StringField('Descrição / Nome do Cargo', validators=[
        DataRequired(message="A descrição ou nome do cargo é obrigatória."),
        Length(max=150, message="A descrição deve ter no máximo 150 caracteres.")
    ])
    role_ativo = BooleanField('Cargo Ativo (Disponível nos Menus / Turmas / Temas)', default=True)
    submit = SubmitField('Salvar Cargo')

