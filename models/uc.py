from extensions import db

class Uc(db.Model):
    __tablename__ = 'anima_uc'

    uc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uc_nome = db.Column(db.String(150), nullable=False)
    uc_ano_semestre = db.Column(db.String(10), nullable=False)
    uc_discord_role = db.Column(db.String(25), nullable=False)
    uc_dia_semana = db.Column(db.Integer, nullable=True)
    uc_channel_id = db.Column(db.String(25), nullable=True)

    @property
    def dia_semana_nome(self):
        dias = {
            0: "Domingo",
            1: "Segunda-feira",
            2: "Terça-feira",
            3: "Quarta-feira",
            4: "Quinta-feira",
            5: "Sexta-feira",
            6: "Sábado",
            7: "Domingo"
        }
        return dias.get(self.uc_dia_semana, '-') if self.uc_dia_semana is not None else '-'

    def to_dict(self):
        return {
            'uc_id': self.uc_id,
            'uc_nome': self.uc_nome,
            'uc_ano_semestre': self.uc_ano_semestre,
            'uc_discord_role': self.uc_discord_role,
            'uc_dia_semana': self.uc_dia_semana,
            'uc_dia_semana_nome': self.dia_semana_nome,
            'uc_channel_id': self.uc_channel_id
        }
