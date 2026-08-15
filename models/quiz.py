from extensions import db
from datetime import datetime

# Association Table for Quiz <-> Temas de Interesse
quiz_tema_association = db.Table(
    'anima_quiz_tema',
    db.Column('quiz_id', db.Integer, db.ForeignKey('anima_quiz.quiz_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('temas_interesse_id', db.Integer, db.ForeignKey('anima_temas_interesse.temas_interesse_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
)

# Association Table for Pergunta <-> Temas de Interesse
pergunta_tema_association = db.Table(
    'anima_pergunta_tema',
    db.Column('pergunta_id', db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('temas_interesse_id', db.Integer, db.ForeignKey('anima_temas_interesse.temas_interesse_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
)

# Association Table for Quiz <-> Perguntas (Question Bank reuse)
quiz_pergunta_association = db.Table(
    'anima_quiz_pergunta_assoc',
    db.Column('quiz_id', db.Integer, db.ForeignKey('anima_quiz.quiz_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('pergunta_id', db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('ordem', db.Integer, default=1)
)

class TemaInteresse(db.Model):
    __tablename__ = 'anima_temas_interesse'

    temas_interesse_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    temas_interesse_nome = db.Column(db.String(120), nullable=False)
    temas_interesse_tag = db.Column(db.String(30), nullable=True)
    temas_interesse_descricao = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'temas_interesse_id': self.temas_interesse_id,
            'temas_interesse_nome': self.temas_interesse_nome,
            'temas_interesse_tag': self.temas_interesse_tag,
            'temas_interesse_descricao': self.temas_interesse_descricao
        }

class Quiz(db.Model):
    __tablename__ = 'anima_quiz'

    quiz_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_titulo = db.Column(db.String(150), nullable=False)
    quiz_descricao = db.Column(db.Text, nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    temas = db.relationship('TemaInteresse', secondary=quiz_tema_association, backref=db.backref('quizes', lazy='dynamic'))
    perguntas = db.relationship('QuizPergunta', secondary=quiz_pergunta_association, backref=db.backref('quizes', lazy='dynamic'), order_by='QuizPergunta.pergunta_ordem')
    aplicacoes = db.relationship('QuizAplicacao', backref='quiz', lazy=True)

    @property
    def total_perguntas(self):
        return len(self.perguntas)

    def to_dict(self):
        return {
            'quiz_id': self.quiz_id,
            'quiz_titulo': self.quiz_titulo,
            'quiz_descricao': self.quiz_descricao,
            'total_perguntas': self.total_perguntas,
            'temas': [t.to_dict() for t in self.temas],
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None
        }

class QuizPergunta(db.Model):
    __tablename__ = 'anima_quiz_pergunta'

    pergunta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, nullable=True) # Mantido para compatibilidade legado, mas agora desacoplado
    pergunta_ordem = db.Column(db.Integer, nullable=False, default=1)
    pergunta_enunciado = db.Column(db.Text, nullable=False)
    pergunta_imagem_url = db.Column(db.String(500), nullable=True)
    tempo_limite_segundos = db.Column(db.Integer, nullable=False, default=20)
    pontos_base = db.Column(db.Integer, nullable=False, default=1000)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    temas = db.relationship('TemaInteresse', secondary=pergunta_tema_association, backref=db.backref('perguntas', lazy='dynamic'))
    alternativas = db.relationship('QuizAlternativa', backref='pergunta', lazy=True, cascade='all, delete-orphan', order_by='QuizAlternativa.alternativa_letra')

    @property
    def alternativa_correta(self):
        for alt in self.alternativas:
            if alt.is_correta:
                return alt
        return None

    def to_dict(self):
        return {
            'pergunta_id': self.pergunta_id,
            'pergunta_ordem': self.pergunta_ordem,
            'pergunta_enunciado': self.pergunta_enunciado,
            'pergunta_imagem_url': self.pergunta_imagem_url,
            'tempo_limite_segundos': self.tempo_limite_segundos,
            'pontos_base': self.pontos_base,
            'temas': [t.to_dict() for t in self.temas],
            'alternativas': [alt.to_dict() for alt in self.alternativas]
        }

class QuizAlternativa(db.Model):
    __tablename__ = 'anima_quiz_alternativa'

    alternativa_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    alternativa_letra = db.Column(db.String(1), nullable=False) # 'A', 'B', 'C', 'D'
    alternativa_texto = db.Column(db.String(100), nullable=False)
    is_correta = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'alternativa_id': self.alternativa_id,
            'pergunta_id': self.pergunta_id,
            'alternativa_letra': self.alternativa_letra,
            'alternativa_texto': self.alternativa_texto,
            'is_correta': self.is_correta
        }

class QuizAplicacao(db.Model):
    __tablename__ = 'anima_quiz_aplicacao'

    aplicacao_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('anima_quiz.quiz_id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    uc_id = db.Column(db.Integer, db.ForeignKey('anima_uc.uc_id', ondelete='RESTRICT', onupdate='CASCADE'), nullable=False)
    data_hora_prevista = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('Agendado', 'Em Andamento', 'Concluido', 'Cancelado'), nullable=False, default='Agendado')
    discord_channel_id = db.Column(db.String(25), nullable=True)
    data_hora_inicio = db.Column(db.DateTime, nullable=True)
    data_hora_fim = db.Column(db.DateTime, nullable=True)

    # Point scale parameters for top 10 positions
    pontos_1_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=1.00)
    pontos_2_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=1.00)
    pontos_3_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=1.00)
    pontos_4_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.80)
    pontos_5_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.80)
    pontos_6_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.80)
    pontos_7_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.50)
    pontos_8_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.50)
    pontos_9_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.50)
    pontos_10_lugar = db.Column(db.Numeric(5, 2), nullable=False, default=0.50)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    uc = db.relationship('Uc', backref='quizes_aplicados', lazy=True)
    respostas = db.relationship('QuizResposta', backref='aplicacao', lazy=True, cascade='all, delete-orphan')
    participantes = db.relationship('QuizParticipante', backref='aplicacao', lazy=True, cascade='all, delete-orphan', order_by='QuizParticipante.posicao_final')

    def get_pontos_por_posicao(self, posicao: int):
        pos_map = {
            1: self.pontos_1_lugar,
            2: self.pontos_2_lugar,
            3: self.pontos_3_lugar,
            4: self.pontos_4_lugar,
            5: self.pontos_5_lugar,
            6: self.pontos_6_lugar,
            7: self.pontos_7_lugar,
            8: self.pontos_8_lugar,
            9: self.pontos_9_lugar,
            10: self.pontos_10_lugar,
        }
        val = pos_map.get(posicao, 0.0)
        return float(val) if val is not None else 0.0

    def to_dict(self):
        return {
            'aplicacao_id': self.aplicacao_id,
            'quiz_id': self.quiz_id,
            'quiz_titulo': self.quiz.quiz_titulo if self.quiz else None,
            'uc_id': self.uc_id,
            'uc_nome': self.uc.uc_nome if self.uc else None,
            'data_hora_prevista': self.data_hora_prevista.isoformat() if self.data_hora_prevista else None,
            'status': self.status,
            'discord_channel_id': self.discord_channel_id,
            'total_participantes': len(self.participantes)
        }

class QuizResposta(db.Model):
    __tablename__ = 'anima_quiz_resposta'

    resposta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    alternativa_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_alternativa.alternativa_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    data_hora_resposta = db.Column(db.DateTime, nullable=False)
    tempo_gasto_ms = db.Column(db.Integer, nullable=False)
    is_correta = db.Column(db.Boolean, nullable=False, default=False)
    pontos_ganhos = db.Column(db.Integer, nullable=False, default=0)

    # Relationships
    pergunta = db.relationship('QuizPergunta', lazy=True)
    alternativa = db.relationship('QuizAlternativa', lazy=True)
    usuario_discord = db.relationship('UsuarioDiscord', lazy=True)

class QuizParticipante(db.Model):
    __tablename__ = 'anima_quiz_participante'

    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    pontuacao_total = db.Column(db.Integer, nullable=False, default=0)
    acertos = db.Column(db.Integer, nullable=False, default=0)
    tempo_total_ms = db.Column(db.Integer, nullable=False, default=0)
    posicao_final = db.Column(db.Integer, nullable=True)
    pontos_atribuidos = db.Column(db.Numeric(5, 2), nullable=True)

    # Relationships
    usuario_discord = db.relationship('UsuarioDiscord', lazy=True)
