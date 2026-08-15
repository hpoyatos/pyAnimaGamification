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
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
            'total_perguntas': self.total_perguntas,
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
    uc_id = db.Column(db.Integer, db.ForeignKey('anima_uc.uc_id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.curso_id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True)
    
    aplicacao_codigo = db.Column(db.String(20), unique=True, nullable=False)
    aplicacao_status = db.Column(db.Enum('agendado', 'em_andamento', 'finalizado', 'cancelado', name='aplicacao_status_enum'), default='agendado', nullable=False)
    aplicacao_dt_inicio = db.Column(db.DateTime, nullable=True)
    aplicacao_dt_fim = db.Column(db.DateTime, nullable=True)
    aplicacao_canal_discord = db.Column(db.String(25), nullable=True)

    # Relationships
    participantes = db.relationship('QuizParticipante', backref='aplicacao', cascade='all, delete-orphan', lazy=True)
    respostas = db.relationship('QuizResposta', backref='aplicacao', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'aplicacao_id': self.aplicacao_id,
            'quiz_id': self.quiz_id,
            'quiz_titulo': self.quiz.quiz_titulo if self.quiz else None,
            'uc_id': self.uc_id,
            'curso_id': self.curso_id,
            'aplicacao_codigo': self.aplicacao_codigo,
            'aplicacao_status': self.aplicacao_status,
            'aplicacao_dt_inicio': self.aplicacao_dt_inicio.isoformat() if self.aplicacao_dt_inicio else None,
            'aplicacao_dt_fim': self.aplicacao_dt_fim.isoformat() if self.aplicacao_dt_fim else None,
            'aplicacao_canal_discord': self.aplicacao_canal_discord,
            'total_participantes': len(self.participantes)
        }

class QuizParticipante(db.Model):
    __tablename__ = 'anima_quiz_participante'

    participante_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    pontuacao_total = db.Column(db.Integer, default=0, nullable=False)
    posicao_ranking = db.Column(db.Integer, nullable=True)
    data_entrada = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    usuario_discord = db.relationship('UsuarioDiscord', backref='participacoes_quiz', lazy=True)

    def to_dict(self):
        return {
            'participante_id': self.participante_id,
            'aplicacao_id': self.aplicacao_id,
            'discord_user_id': self.discord_user_id,
            'usuario_nome': self.usuario_discord.display_name if self.usuario_discord else self.discord_user_id,
            'pontuacao_total': self.pontuacao_total,
            'posicao_ranking': self.posicao_ranking,
            'data_entrada': self.data_entrada.isoformat() if self.data_entrada else None
        }

class QuizResposta(db.Model):
    __tablename__ = 'anima_quiz_resposta'

    resposta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aplicacao_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_aplicacao.aplicacao_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    pergunta_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_pergunta.pergunta_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    alternativa_id = db.Column(db.Integer, db.ForeignKey('anima_quiz_alternativa.alternativa_id', ondelete='CASCADE', onupdate='CASCADE'), nullable=True)
    resposta_texto = db.Column(db.Text, nullable=True)
    tempo_resposta_segundos = db.Column(db.Numeric(5, 2), nullable=True)
    pontos_obtidos = db.Column(db.Integer, default=0, nullable=False)
    correta = db.Column(db.Boolean, default=False, nullable=False)
    data_resposta = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    pergunta = db.relationship('QuizPergunta', lazy=True)
    alternativa = db.relationship('QuizAlternativa', lazy=True)
    usuario_discord = db.relationship('UsuarioDiscord', lazy=True)

    def to_dict(self):
        return {
            'resposta_id': self.resposta_id,
            'aplicacao_id': self.aplicacao_id,
            'pergunta_id': self.pergunta_id,
            'discord_user_id': self.discord_user_id,
            'alternativa_id': self.alternativa_id,
            'resposta_texto': self.resposta_texto,
            'tempo_resposta_segundos': float(self.tempo_resposta_segundos) if self.tempo_resposta_segundos else None,
            'pontos_obtidos': self.pontos_obtidos,
            'correta': self.correta,
            'data_resposta': self.data_resposta.isoformat() if self.data_resposta else None
        }
