from extensions import db

class Uc(db.Model):
    __tablename__ = 'anima_uc'

    uc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uc_nome = db.Column(db.String(100), nullable=False)
    uc_ano_semestre = db.Column(db.String(10), nullable=False)
    uc_discord_role = db.Column(db.String(20), db.ForeignKey('anima_discord_role.role_id'), nullable=False)
    uc_channel_id = db.Column(db.String(20), nullable=True)
    uc_dia_semana = db.Column(db.Integer, nullable=True)

    # Relationships
    role_rel = db.relationship('AnimaDiscordRole', back_populates='ucs', foreign_keys=[uc_discord_role], lazy=True)

    @property
    def role_descricao(self):
        return self.role_rel.role_descricao if self.role_rel else None

    @property
    def dia_semana_nome(self):
        dias = {
            2: 'Segunda-feira',
            3: 'Terça-feira',
            4: 'Quarta-feira',
            5: 'Quinta-feira',
            6: 'Sexta-feira',
            7: 'Sábado'
        }
        return dias.get(self.uc_dia_semana, '-')

    def to_dict(self):
        return {
            'uc_id': self.uc_id,
            'uc_nome': self.uc_nome,
            'uc_ano_semestre': self.uc_ano_semestre,
            'uc_discord_role': self.uc_discord_role,
            'uc_role_descricao': self.role_descricao,
            'uc_channel_id': self.uc_channel_id,
            'uc_dia_semana': self.uc_dia_semana,
            'dia_semana_nome': self.dia_semana_nome
        }

# Alias for backwards compatibility
UC = Uc
