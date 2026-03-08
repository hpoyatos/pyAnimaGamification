from extensions import db

class Uc(db.Model):
    __tablename__ = 'uc'

    uc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uc_nome = db.Column(db.String(100), nullable=False)
    uc_role_id = db.Column(db.String(20), nullable=True)
    uc_ano = db.Column(db.String(4), nullable=True)
    uc_semestre = db.Column(db.String(1), nullable=True)
    uc_dia_semana = db.Column(db.SmallInteger, nullable=True)

    # Relationships
    pontos = db.relationship('Ponto', backref='uc', lazy=True)

    def to_dict(self):
        return {
            'uc_id': self.uc_id,
            'uc_nome': self.uc_nome,
            'uc_role_id': self.uc_role_id,
            'uc_ano': self.uc_ano,
            'uc_semestre': self.uc_semestre,
            'uc_dia_semana': self.uc_dia_semana
        }
