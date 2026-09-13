from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, DateTimeLocalField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class AvisoForm(FlaskForm):
    aviso_titulo = StringField('Título do Aviso', validators=[
        DataRequired(message='O título do aviso é obrigatório.'),
        Length(max=150, message='O título deve ter no máximo 150 caracteres.')
    ])

    aviso_conteudo = TextAreaField('Conteúdo do Aviso (Markdown Discord)', validators=[
        DataRequired(message='O conteúdo do aviso é obrigatório.')
    ])

    aviso_canal_id = StringField('ID do Canal Discord', default='1020488574732357632', validators=[
        DataRequired(message='O ID do canal do Discord é obrigatório.'),
        Length(max=30)
    ])

    aviso_tipo = SelectField('Tipo de Agendamento', choices=[
        ('unico', '📌 Envio Único (Uma vez)'),
        ('recorrente', '🔄 Recorrente (Periódico)')
    ], default='unico', validators=[DataRequired()])

    aviso_recorrencia_tipo = SelectField('Frequência da Recorrência', choices=[
        ('nenhum', 'Nenhum (Apenas envio único)'),
        ('intervalo_horas', '⏱️ A cada X Horas'),
        ('diario', '📅 Diariamente (A cada X Dias)'),
        ('semanal', '🗓️ Semanalmente (A cada X Semanas)')
    ], default='nenhum', validators=[Optional()])

    aviso_recorrencia_valor = IntegerField('Intervalo Numérico (Horas/Dias/Semanas)', default=1, validators=[
        Optional(),
        NumberRange(min=1, max=365, message='O intervalo deve ser entre 1 e 365.')
    ])

    aviso_dt_proximo_envio = DateTimeLocalField('Data/Hora de Disparo (Inicial ou Próximo)', format='%Y-%m-%dT%H:%M', validators=[
        Optional()
    ])

    aviso_usar_ia = BooleanField('Habilitar IA (LLaMA Local) para variações dinâmicas de texto')

    aviso_ia_prompt = StringField('Instruções adicionais para a IA (Opcional)', validators=[
        Optional(),
        Length(max=255, message='Instrução da IA deve ter no máximo 255 caracteres.')
    ])

    aviso_ativo = BooleanField('Aviso Ativo', default=True)

    submit = SubmitField('Salvar Aviso')
