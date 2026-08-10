from extensions import db
from datetime import datetime

class Pontuacao(db.Model):
    __tablename__ = 'pontuacao'

    pontuacao_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    uc_id = db.Column(db.Integer, db.ForeignKey('anima_uc.uc_id'), nullable=False)
    pontuacao = db.Column(db.Numeric(5, 2), nullable=False)
    data_pontuacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pontuacao_descricao = db.Column(db.String(255), nullable=True)

    # Relationships
    usuario = db.relationship('Usuario', backref='pontuacoes', lazy=True)
    uc = db.relationship('Uc', backref='pontuacoes', lazy=True)

    # Properties for backwards compatibility
    @property
    def ponto_id(self):
        return self.pontuacao_id

    @property
    def dt_ponto(self):
        return self.data_pontuacao

    @property
    def num_ponto(self):
        return float(self.pontuacao) if self.pontuacao is not None else 0.0

    @property
    def comentario_ponto(self):
        return self.pontuacao_descricao

    @property
    def tipo_ponto(self):
        return 'Pontuação'

    def to_dict(self):
        return {
            'pontuacao_id': self.pontuacao_id,
            'usuario_id': self.usuario_id,
            'uc_id': self.uc_id,
            'pontuacao': float(self.pontuacao) if self.pontuacao is not None else 0.0,
            'data_pontuacao': self.data_pontuacao.isoformat() if self.data_pontuacao else None,
            'pontuacao_descricao': self.pontuacao_descricao
        }

# Alias for backwards compatibility
Ponto = Pontuacao
