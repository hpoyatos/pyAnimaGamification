from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class TemaInteresseForm(FlaskForm):
    temas_interesse_nome = StringField(
        'Nome do Tema', 
        validators=[DataRequired(message='O nome do tema é obrigatório.'), Length(max=120)]
    )
    temas_interesse_tag = StringField(
        'Tag / Slug (#tag)', 
        validators=[Optional(), Length(max=30, message='Tag pode ter até 30 caracteres.')]
    )
    temas_interesse_descricao = TextAreaField(
        'Descrição / Tópicos Relacionados', 
        validators=[Optional()]
    )
    discord_role_id = SelectField(
        'Cargo Discord Vinculado (Role ID)', 
        validators=[Optional()]
    )
    submit = SubmitField('Salvar Tema de Interesse')
