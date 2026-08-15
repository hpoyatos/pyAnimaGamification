from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateTimeLocalField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Length, Optional

class CursoForm(FlaskForm):
    curso_nome = StringField('Nome do Curso', validators=[DataRequired(), Length(max=120)])
    
    curso_parceira = SelectField('Parceira', choices=[
        ('Red Hat', 'Red Hat'),
        ('Google', 'Google'),
        ('AWS', 'AWS'),
        ('Cisco', 'Cisco'),
        ('Microsoft', 'Microsoft'),
        ('Oracle', 'Oracle')
    ], validators=[DataRequired()])
    
    curso_descricao = TextAreaField('Descrição do Curso (Conteúdo Programático / Detalhes)', validators=[Optional()])

    curso_dt_inicio = DateTimeLocalField('Data de Início', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    curso_dt_fim = DateTimeLocalField('Data de Fim', format='%Y-%m-%dT%H:%M', validators=[DataRequired()])
    
    curso_agente = StringField('Agente (Professor/Responsável)', validators=[DataRequired(), Length(max=60)])
    
    curso_role = StringField('Role ID Discord (Opcional)', validators=[Optional(), Length(max=25)])
    
    curso_param = StringField('Parâmetro LMS Automático', validators=[Optional(), Length(max=120)])
    
    curso_url_inscricao = StringField('URL de Inscrição Automática (Cisco/Parceiras)', validators=[Optional(), Length(max=255)])
    
    curso_sinonimos = StringField('Nomes Alternativos (Sinônimos para Certificados)', validators=[Optional()])
    
    curso_carga_horaria = IntegerField('Carga Horária (Horas)', validators=[Optional()])
    
    submit = SubmitField('Salvar Curso')
