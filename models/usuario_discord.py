from extensions import db
from datetime import datetime

class UsuarioDiscord(db.Model):
    __tablename__ = 'anima_usuario_discord'

    discord_user_id = db.Column(db.String(25), primary_key=True)
    discord_username = db.Column(db.String(100), nullable=True)
    discord_global_name = db.Column(db.String(100), nullable=True)
    discord_avatar_url = db.Column(db.String(255), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id', ondelete='SET NULL', onupdate='CASCADE'), nullable=True)
    
    # Redes sociais
    linkedin_url = db.Column(db.String(255), nullable=True)
    instagram_user = db.Column(db.String(100), nullable=True)

    # Preferências de privacidade de compartilhamento
    share_nome = db.Column(db.Boolean, nullable=False, default=True)
    share_email_academico = db.Column(db.Boolean, nullable=False, default=False)
    share_email_pessoal = db.Column(db.Boolean, nullable=False, default=False)
    share_linkedin = db.Column(db.Boolean, nullable=False, default=True)
    share_instagram = db.Column(db.Boolean, nullable=False, default=True)
    share_temas = db.Column(db.Boolean, nullable=False, default=True)

    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_atualizacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    usuario = db.relationship('Usuario', backref=db.backref('discord_account', uselist=False), lazy=True)
    temas_interesse = db.relationship('TemaInteresse', secondary='anima_usuario_temas_interesse', back_populates='usuarios_discord', lazy='dynamic')

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
            'linkedin_url': self.linkedin_url,
            'instagram_user': self.instagram_user,
            'share_nome': self.share_nome,
            'share_email_academico': self.share_email_academico,
            'share_email_pessoal': self.share_email_pessoal,
            'share_linkedin': self.share_linkedin,
            'share_instagram': self.share_instagram,
            'share_temas': self.share_temas,
            'temas_interesse': [t.to_dict() for t in self.temas_interesse],
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None
        }
