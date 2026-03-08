from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from wtforms_sqlalchemy.fields import QuerySelectField
from models.usuario import Usuario
from models.uc import Uc
from datetime import date

def get_usuarios():
    # Order alphabetically for easier selection
    return Usuario.query.order_by(Usuario.usuario_nome).all()

def get_ucs():
    return Uc.query.all()

class KahootLoteForm(FlaskForm):
    uc_id = QuerySelectField('UC', query_factory=get_ucs, allow_blank=False, get_label='uc_nome', validators=[DataRequired()])
    data_kahoot = DateField('Data', default=date.today, format='%Y-%m-%d', validators=[DataRequired()])
    nome_jogo = StringField('Nome do Jogo Kahoot', validators=[DataRequired(), Length(max=100)])
    
    # 10 user fields
    usuario_1 = QuerySelectField('1º Lugar (1.0 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_2 = QuerySelectField('2º Lugar (1.0 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_3 = QuerySelectField('3º Lugar (1.0 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_4 = QuerySelectField('4º Lugar (0.8 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_5 = QuerySelectField('5º Lugar (0.8 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_6 = QuerySelectField('6º Lugar (0.8 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_7 = QuerySelectField('7º Lugar (0.5 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_8 = QuerySelectField('8º Lugar (0.5 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_9 = QuerySelectField('9º Lugar (0.5 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    usuario_10 = QuerySelectField('10º Lugar (0.5 pt)', query_factory=get_usuarios, allow_blank=True, get_label='usuario_nome')
    
    submit = SubmitField('Salvar Kahoot')
