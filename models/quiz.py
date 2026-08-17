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

# Association Table for Usuario Discord <-> Temas de Interesse
usuario_discord_tema_association = db.Table(
    'anima_usuario_temas_interesse',
    db.Column('discord_user_id', db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('temas_interesse_id', db.Integer, db.ForeignKey('anima_temas_interesse.temas_interesse_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True),
    db.Column('data_associacao', db.DateTime, default=datetime.utcnow)
)

class TemaInteresse(db.Model):
    __tablename__ = 'anima_temas_interesse'

    temas_interesse_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    temas_interesse_nome = db.Column(db.String(120), nullable=False)
    temas_interesse_tag = db.Column(db.String(30), nullable=True)
    temas_interesse_descricao = db.Column(db.Text, nullable=True)

    # Relationships
    usuarios_discord = db.relationship('UsuarioDiscord', secondary=usuario_discord_tema_association, back_populates='temas_interesse', lazy='dynamic')

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

    # Pontos de Premiação Acadêmica do Quiz (Top 10)
    pontos_1_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_2_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_3_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_4_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_5_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_6_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_7_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_8_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_9_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_10_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)

    # Relationships
    temas = db.relationship('TemaInteresse', secondary=quiz_tema_association, backref=db.backref('quizes', lazy='dynamic'))
    perguntas = db.relationship('QuizPergunta', secondary=quiz_pergunta_association, backref=db.backref('quizes', lazy='dynamic'), order_by='QuizPergunta.pergunta_ordem')
    aplicacoes = db.relationship('QuizAplicacao', backref='quiz', lazy=True)

    @property
    def total_perguntas(self):
        return len(self.perguntas)

    def get_pontos_map(self):
        return {
            1: float(self.pontos_1_lugar if self.pontos_1_lugar is not None else 1.0),
            2: float(self.pontos_2_lugar if self.pontos_2_lugar is not None else 1.0),
            3: float(self.pontos_3_lugar if self.pontos_3_lugar is not None else 1.0),
            4: float(self.pontos_4_lugar if self.pontos_4_lugar is not None else 0.8),
            5: float(self.pontos_5_lugar if self.pontos_5_lugar is not None else 0.8),
            6: float(self.pontos_6_lugar if self.pontos_6_lugar is not None else 0.8),
            7: float(self.pontos_7_lugar if self.pontos_7_lugar is not None else 0.5),
            8: float(self.pontos_8_lugar if self.pontos_8_lugar is not None else 0.5),
            9: float(self.pontos_9_lugar if self.pontos_9_lugar is not None else 0.5),
            10: float(self.pontos_10_lugar if self.pontos_10_lugar is not None else 0.5),
        }

    def to_dict(self):
        return {
            'quiz_id': self.quiz_id,
            'quiz_titulo': self.quiz_titulo,
            'quiz_descricao': self.quiz_descricao,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
            'total_perguntas': self.total_perguntas,
            'pontos_top10': self.get_pontos_map(),
            'temas': [t.to_dict() for t in self.temas]
        }

class QuizPergunta(db.Model):
    __tablename__ = 'anima_quiz_pergunta'

    pergunta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, nullable=True)
    pergunta_ordem = db.Column(db.Integer, default=1)
    pergunta_enunciado = db.Column(db.Text, nullable=False)
    pergunta_imagem_url = db.Column(db.String(500), nullable=True)
    tempo_limite_segundos = db.Column(db.Integer, default=20, nullable=False)
    pontos_base = db.Column(db.Integer, default=1000, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Properties aliases
    @property
    def pergunta_tempo_segundos(self):
        return self.tempo_limite_segundos

    @pergunta_tempo_segundos.setter
    def pergunta_tempo_segundos(self, value):
        self.tempo_limite_segundos = value

    @property
    def pergunta_pontos(self):
        return self.pontos_base

    @pergunta_pontos.setter
    def pergunta_pontos(self, value):
        self.pontos_base = value

    # Relationships
    temas = db.relationship('TemaInteresse', secondary=pergunta_tema_association, backref=db.backref('perguntas', lazy='dynamic'))
    alternativas = db.relationship('QuizAlternativa', backref='pergunta', cascade='all, delete-orphan', lazy=True, order_by='QuizAlternativa.alternativa_letra')

    def to_dict(self):
        return {
            'pergunta_id': self.pergunta_id,
            'quiz_id': self.quiz_id,
            'pergunta_ordem': self.pergunta_ordem,
            'pergunta_enunciado': self.pergunta_enunciado,
            'pergunta_imagem_url': self.pergunta_imagem_url,
            'tempo_limite_segundos': self.tempo_limite_segundos,
            'pontos_base': self.pontos_base,
            'alternativas': [a.to_dict() for a in self.alternativas],
            'temas': [t.to_dict() for t in self.temas]
        }

class QuizAlternativa(db.Model):
    __tablename__ = 'anima_quiz_alternativa'

    alternativa_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    alternativa_letra = db.Column(db.String(1), nullable=False)
    alternativa_texto = db.Column(db.String(100), nullable=False)
    is_correta = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def alternativa_correta(self):
        return self.is_correta

    @alternativa_correta.setter
    def alternativa_correta(self, value):
        self.is_correta = bool(value)

    @property
    def alternativa_ordem(self):
        return ord(self.alternativa_letra.upper()) - ord('A') + 1 if self.alternativa_letra else 1

    def to_dict(self):
        return {
            'alternativa_id': self.alternativa_id,
            'pergunta_id': self.pergunta_id,
            'alternativa_letra': self.alternativa_letra,
            'alternativa_ordem': self.alternativa_ordem,
            'alternativa_texto': self.alternativa_texto,
            'is_correta': self.is_correta,
            'alternativa_correta': self.alternativa_correta
        }

class QuizAplicacao(db.Model):
    __tablename__ = 'anima_quiz_aplicacao'

    aplicacao_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('anima_quiz.quiz_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    uc_id = db.Column(db.Integer, db.ForeignKey('anima_uc.uc_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    data_hora_prevista = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('Agendado', 'Em Andamento', 'Concluido', 'Cancelado', name='quiz_aplicacao_status_enum'), default='Agendado', nullable=False)
    discord_channel_id = db.Column(db.String(25), nullable=True)
    data_hora_inicio = db.Column(db.DateTime, nullable=True)
    data_hora_fim = db.Column(db.DateTime, nullable=True)
    pontos_1_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_2_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_3_lugar = db.Column(db.Numeric(5, 2), default=1.00, nullable=False)
    pontos_4_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_5_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_6_lugar = db.Column(db.Numeric(5, 2), default=0.80, nullable=False)
    pontos_7_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_8_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_9_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    pontos_10_lugar = db.Column(db.Numeric(5, 2), default=0.50, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    uc = db.relationship('Uc', backref='aplicacoes_quiz', lazy=True)
    participantes = db.relationship('QuizParticipante', backref='aplicacao', cascade='all, delete-orphan', lazy=True)
    respostas = db.relationship('QuizResposta', backref='aplicacao', cascade='all, delete-orphan', lazy=True)

    @property
    def total_participantes(self):
        return len(self.participantes)

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
            'data_hora_inicio': self.data_hora_inicio.isoformat() if self.data_hora_inicio else None,
            'data_hora_fim': self.data_hora_fim.isoformat() if self.data_hora_fim else None,
            'total_participantes': self.total_participantes
        }

class QuizParticipante(db.Model):
    __tablename__ = 'anima_quiz_participante'

    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    pontuacao_total = db.Column(db.Integer, default=0, nullable=False)
    acertos = db.Column(db.Integer, default=0, nullable=False)
    tempo_total_ms = db.Column(db.Integer, default=0, nullable=False)
    posicao_final = db.Column(db.Integer, nullable=True)
    pontos_atribuidos = db.Column(db.Numeric(5, 2), nullable=True)

    # Relationships
    usuario_discord = db.relationship('UsuarioDiscord', backref='participacoes_quiz', lazy=True)

    def to_dict(self):
        return {
            'aplicacao_id': self.aplicacao_id,
            'discord_user_id': self.discord_user_id,
            'usuario_nome': self.usuario_discord.display_name if self.usuario_discord else self.discord_user_id,
            'pontuacao_total': self.pontuacao_total,
            'acertos': self.acertos,
            'tempo_total_ms': self.tempo_total_ms,
            'posicao_final': self.posicao_final,
            'pontos_atribuidos': float(self.pontos_atribuidos) if self.pontos_atribuidos else None
        }

class QuizResposta(db.Model):
    __tablename__ = 'anima_quiz_resposta'

    resposta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    alternativa_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_alternativa.alternativa_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    data_hora_resposta = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    tempo_gasto_ms = db.Column(db.Integer, default=0, nullable=False)
    is_correta = db.Column(db.Boolean, default=False, nullable=False)
    pontos_ganhos = db.Column(db.Integer, default=0, nullable=False)

    # Relationships
    pergunta = db.relationship('QuizPergunta', lazy=True)
    alternativa = db.relationship('QuizAlternativa', lazy=True)
    usuario_discord = db.relationship('UsuarioDiscord', lazy=True)

    def to_dict(self):
        return {
            'resposta_id': self.resposta_id,
            'aplicacao_id': self.aplicacao_id,
            'pergunta_id': self.pergunta_id,
            'alternativa_id': self.alternativa_id,
            'discord_user_id': self.discord_user_id,
            'data_hora_resposta': self.data_hora_resposta.isoformat() if self.data_hora_resposta else None,
            'tempo_gasto_ms': self.tempo_gasto_ms,
            'is_correta': self.is_correta,
            'pontos_ganhos': self.pontos_ganhos
        }
