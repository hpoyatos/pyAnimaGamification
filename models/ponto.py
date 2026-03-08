from extensions import db
from datetime import datetime

class Ponto(db.Model):
    __tablename__ = 'ponto'

    ponto_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    uc_id = db.Column(db.Integer, db.ForeignKey('uc.uc_id'), nullable=False)
    tipo_ponto = db.Column(db.Enum('Presença', 'Participação', 'Kahoot', 'Curso'), nullable=False)
    dt_ponto = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    num_ponto = db.Column(db.Float, nullable=False)
    comentario_ponto = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            'ponto_id': self.ponto_id,
            'usuario_id': self.usuario_id,
            'uc_id': self.uc_id,
            'tipo_ponto': self.tipo_ponto,
            'dt_ponto': self.dt_ponto.isoformat() if self.dt_ponto else None,
            'num_ponto': self.num_ponto,
            'comentario_ponto': self.comentario_ponto
        }
