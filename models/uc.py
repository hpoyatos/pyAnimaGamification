from extensions import db

class Uc(db.Model):
    __tablename__ = 'anima_uc'

    uc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uc_nome = db.Column(db.String(100), nullable=False)
    uc_semestre = db.Column(db.String(20), nullable=True)
    uc_discord_role = db.Column(db.String(20), nullable=True)

    # Relationships
    @property
    def pontos(self):
        return self.pontuacoes

    def to_dict(self):
        return {
            'uc_id': self.uc_id,
            'uc_nome': self.uc_nome,
            'uc_semestre': self.uc_semestre,
            'uc_discord_role': self.uc_discord_role
        }
