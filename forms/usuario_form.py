from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, DateField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

class UsuarioForm(FlaskForm):
    usuario_nome = StringField('Nome', validators=[DataRequired(), Length(max=120)])
    usuario_email = StringField('E-mail Institucional (@ulife.com.br)', validators=[Optional(), Email(), Length(max=60)])
    usuario_email_pessoal = StringField('E-mail Pessoal', validators=[Optional(), Email(), Length(max=150)])
    usuario_telefone = StringField('Telefone / WhatsApp', validators=[Optional(), Length(max=50)])
    usuario_ra = StringField('RA', validators=[Optional(), Length(max=20)])
    usuario_discord_id = StringField('Discord ID', validators=[Optional(), Length(max=20)])
    usuario_discord_name = StringField('Discord Name', validators=[Optional(), Length(max=60)])
    usuario_validado = BooleanField('Validado?')
    usuario_validado_data = DateField('Data de Validação', format='%Y-%m-%d', validators=[Optional()])
    
    submit = SubmitField('Salvar')
