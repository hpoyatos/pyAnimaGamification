from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, IntegerField, DecimalField,
    RadioField, SelectMultipleField, SubmitField, DateTimeLocalField
)
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from wtforms_sqlalchemy.fields import QuerySelectField
from models.quiz import Quiz, QuizPergunta, TemaInteresse
from models.uc import Uc
from datetime import datetime

def get_quizes():
    return Quiz.query.order_by(Quiz.quiz_titulo).all()

def get_ucs():
    return Uc.query.order_by(Uc.uc_nome).all()

def get_temas():
    return TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()

class QuizForm(FlaskForm):
    quiz_titulo = StringField('Título do Quiz', validators=[DataRequired(), Length(max=150)])
    quiz_descricao = TextAreaField('Descrição / Observações', validators=[Optional()])
    temas = SelectMultipleField('Temas de Interesse', coerce=int, validators=[Optional()])
    perguntas_selecionadas = SelectMultipleField('Perguntas do Banco', coerce=int, validators=[Optional()])
    submit = SubmitField('Salvar Quiz')

class PerguntaForm(FlaskForm):
    pergunta_ordem = IntegerField('Ordem Sugerida', default=1, validators=[DataRequired(), NumberRange(min=1)])
    pergunta_enunciado = TextAreaField('Enunciado da Pergunta', validators=[DataRequired()])
    pergunta_imagem_url = StringField('URL da Imagem Ilustrativa (Opcional)', validators=[Optional(), Length(max=500)])
    tempo_limite_segundos = IntegerField('Tempo Limite (segundos)', default=20, validators=[DataRequired(), NumberRange(min=5, max=300)])
    pontos_base = IntegerField('Pontos Base (Kahoot)', default=1000, validators=[DataRequired(), NumberRange(min=100, max=5000)])
    temas = SelectMultipleField('Temas de Interesse Relacionados', coerce=int, validators=[Optional()])

    # 4 Alternativas
    alt_a_texto = StringField('Alternativa A (💎 Diamante)', validators=[DataRequired(), Length(max=100, message="Máximo de 100 caracteres")])
    alt_b_texto = StringField('Alternativa B (⭐ Estrela)', validators=[DataRequired(), Length(max=100, message="Máximo de 100 caracteres")])
    alt_c_texto = StringField('Alternativa C (⚡ Raio)', validators=[DataRequired(), Length(max=100, message="Máximo de 100 caracteres")])
    alt_d_texto = StringField('Alternativa D (🍀 Trevo)', validators=[DataRequired(), Length(max=100, message="Máximo de 100 caracteres")])
    
    correta = RadioField(
        'Alternativa Correta',
        choices=[('A', '💎 Alternativa A'), ('B', '⭐ Alternativa B'), ('C', '⚡ Alternativa C'), ('D', '🍀 Alternativa D')],
        default='A',
        validators=[DataRequired()]
    )
    
    submit = SubmitField('Salvar Pergunta')

class AplicacaoQuizForm(FlaskForm):
    quiz_id = QuerySelectField('Quiz', query_factory=get_quizes, allow_blank=False, get_label='quiz_titulo', validators=[DataRequired()])
    uc_id = QuerySelectField('Unidade Curricular (UC)', query_factory=get_ucs, allow_blank=False, get_label=lambda u: f"{u.uc_nome} ({u.uc_ano_semestre or 'Semestre N/A'})", validators=[DataRequired()])
    data_hora_prevista = DateTimeLocalField('Data e Hora de Aplicação', format='%Y-%m-%dT%H:%M', default=datetime.now, validators=[DataRequired()])
    discord_channel_id = StringField('ID do Canal Discord (Opcional - usa o da UC se vazio)', validators=[Optional(), Length(max=25)])

    # Pontos Top 10
    pontos_1_lugar = DecimalField('1º Lugar (pts)', default=1.00, places=2, validators=[DataRequired()])
    pontos_2_lugar = DecimalField('2º Lugar (pts)', default=1.00, places=2, validators=[DataRequired()])
    pontos_3_lugar = DecimalField('3º Lugar (pts)', default=1.00, places=2, validators=[DataRequired()])
    pontos_4_lugar = DecimalField('4º Lugar (pts)', default=0.80, places=2, validators=[DataRequired()])
    pontos_5_lugar = DecimalField('5º Lugar (pts)', default=0.80, places=2, validators=[DataRequired()])
    pontos_6_lugar = DecimalField('6º Lugar (pts)', default=0.80, places=2, validators=[DataRequired()])
    pontos_7_lugar = DecimalField('7º Lugar (pts)', default=0.50, places=2, validators=[DataRequired()])
    pontos_8_lugar = DecimalField('8º Lugar (pts)', default=0.50, places=2, validators=[DataRequired()])
    pontos_9_lugar = DecimalField('9º Lugar (pts)', default=0.50, places=2, validators=[DataRequired()])
    pontos_10_lugar = DecimalField('10º Lugar (pts)', default=0.50, places=2, validators=[DataRequired()])

    submit = SubmitField('Agendar Aplicação')
