from flask_wtf import FlaskForm
from wtforms import SelectField, DecimalField, StringField, SubmitField
from wtforms_sqlalchemy.fields import QuerySelectField
from wtforms.validators import DataRequired
from models.uc import Uc

def uc_query():
    return Uc.query.order_by(Uc.uc_nome).all()

class ParticipacaoForm(FlaskForm):
    uc_id = QuerySelectField('Unidade Curricular', query_factory=uc_query, get_label='uc_nome', allow_blank=True, blank_text='-- Selecione a UC --', validators=[DataRequired(message="A UC é obrigatória.")])
    usuario_id = SelectField('Usuário', coerce=int, choices=[], validators=[DataRequired(message="O usuário é obrigatório.")])
    tipo_participacao = SelectField('Tipo de Participação', choices=[('', '-- Selecione --'), ('Pergunta', 'Pergunta'), ('Resposta', 'Resposta')], validators=[DataRequired(message="O tipo de participação é obrigatório.")])
    pontos = DecimalField('Pontos', default=0.5, places=1, validators=[DataRequired(message="Os pontos são obrigatórios.")])
    comentario = StringField('Comentário', validators=[DataRequired(message="O comentário é obrigatório.")])
    submit = SubmitField('Lançar Participação')
