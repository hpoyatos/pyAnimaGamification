from flask_wtf import FlaskForm
from wtforms import SubmitField
from wtforms.validators import DataRequired
from wtforms_sqlalchemy.fields import QuerySelectField
from models.usuario import Usuario

def get_usuarios_extrato():
    return Usuario.query.order_by(Usuario.usuario_nome).all()

class ExtratoForm(FlaskForm):
    usuario_id = QuerySelectField('Selecione o Usuário', query_factory=get_usuarios_extrato, allow_blank=True, get_label='usuario_nome', validators=[DataRequired()])
    submit = SubmitField('Consultar Extrato')
