from extensions import db

class Uc(db.Model):
    __tablename__ = 'anima_uc'

    uc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uc_nome = db.Column(db.String(100), nullable=False)
    uc_ano_semestre = db.Column(db.String(10), nullable=True)
    uc_discord_role = db.Column(db.String(25), nullable=True)
    uc_dia_semana = db.Column(db.Integer, nullable=True)
    uc_channel_id = db.Column(db.String(25), nullable=True)

    # Relationships
    @property
    def pontos(self):
        return self.pontuacoes

    def to_dict(self):
        return {
            'uc_id': self.uc_id,
            'uc_nome': self.uc_nome,
            'uc_ano_semestre': self.uc_ano_semestre,
            'uc_discord_role': self.uc_discord_role,
            'uc_dia_semana': self.uc_dia_semana,
            'uc_channel_id': self.uc_channel_id
        }
