from extensions import db
from datetime import datetime

class AnimaUsuarioDiscordRole(db.Model):
    __tablename__ = 'anima_usuario_discord_role'

    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    role_id = db.Column(db.String(20), db.ForeignKey('anima_discord_role.role_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    data_associacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'discord_user_id': self.discord_user_id,
            'role_id': self.role_id,
            'data_associacao': self.data_associacao.isoformat() if self.data_associacao else None
        }


class AnimaDiscordRole(db.Model):
    __tablename__ = 'anima_discord_role'

    role_id = db.Column(db.String(20), primary_key=True)
    role_descricao = db.Column(db.String(150), nullable=False)
    role_ativo = db.Column(db.Boolean, nullable=False, default=True)
    role_created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    cursos = db.relationship('Curso', back_populates='role_rel', lazy=True)
    ucs = db.relationship('Uc', back_populates='role_rel', lazy=True)
    usuarios_associados = db.relationship('AnimaUsuarioDiscordRole', backref='role_obj', lazy=True)

    @property
    def total_usuarios(self):
        return len(self.usuarios_associados)

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_descricao': self.role_descricao,
            'role_ativo': self.role_ativo,
            'total_usuarios': self.total_usuarios,
            'role_created_at': self.role_created_at.isoformat() if self.role_created_at else None
        }

    def __repr__(self):
        return f"<AnimaDiscordRole {self.role_id} - {self.role_descricao} (Ativo: {self.role_ativo})>"
