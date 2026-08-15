from extensions import db
from datetime import datetime

class UsuarioDiscord(db.Model):
    __tablename__ = 'anima_usuario_discord'

    discord_user_id = db.Column(db.String(25), primary_key=True)
    discord_username = db.Column(db.String(100), nullable=True)
    discord_global_name = db.Column(db.String(100), nullable=True)
    discord_avatar_url = db.Column(db.String(255), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    usuario = db.relationship('Usuario', backref=db.backref('discord_account', uselist=False), lazy=True)

    @property
    def display_name(self):
        return self.discord_global_name or self.discord_username or f"User {self.discord_user_id}"

    def to_dict(self):
        return {
            'discord_user_id': self.discord_user_id,
            'discord_username': self.discord_username,
            'discord_global_name': self.discord_global_name,
            'discord_avatar_url': self.discord_avatar_url,
            'usuario_id': self.usuario_id,
            'display_name': self.display_name,
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None
        }
