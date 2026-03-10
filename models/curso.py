from extensions import db
from datetime import datetime

class Curso(db.Model):
    __tablename__ = 'curso'

    curso_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curso_academia = db.Column(db.Enum('Red Hat', 'Google', 'AWS', 'Cisco', 'Microsoft', name='curso_academia_enum'), nullable=False)
    curso_nome = db.Column(db.String(120), nullable=False)
    curso_dt_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    curso_dt_fim = db.Column(db.DateTime, nullable=False)
    curso_agente = db.Column(db.String(60), nullable=False)
    curso_role = db.Column(db.String(22), nullable=True)

    # Relationships
    inscricoes = db.relationship('UsuarioCurso', backref='curso', lazy=True)

    def to_dict(self):
        return {
            'curso_id': self.curso_id,
            'curso_academia': self.curso_academia,
            'curso_nome': self.curso_nome,
            'curso_dt_inicio': self.curso_dt_inicio.isoformat() if self.curso_dt_inicio else None,
            'curso_dt_fim': self.curso_dt_fim.isoformat() if self.curso_dt_fim else None,
            'curso_agente': self.curso_agente,
            'curso_role': self.curso_role
        }
