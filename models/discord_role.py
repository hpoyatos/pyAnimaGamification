from extensions import db
from datetime import datetime

class AnimaUsuarioDiscordRole(db.Model):
    __tablename__ = 'anima_usuario_discord_role'

    discord_user_id = db.Column(db.String(25), db.ForeignKey('anima_usuario_discord.discord_user_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    role_id = db.Column(db.String(20), db.ForeignKey('anima_discord_role.role_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    data_associacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    usuario_discord = db.relationship('UsuarioDiscord', backref=db.backref('cargos_associados', lazy=True), foreign_keys=[discord_user_id], lazy='joined')

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
    usuarios_associados = db.relationship('AnimaUsuarioDiscordRole', backref='role_obj', lazy=True, cascade="all, delete-orphan")

    @property
    def total_usuarios(self):
        try:
            return len(self.usuarios_associados) if self.usuarios_associados else 0
        except Exception:
            return 0

    @property
    def total_temas(self):
        try:
            if hasattr(self, 'temas_interesse') and self.temas_interesse is not None:
                return self.temas_interesse.count()
        except Exception:
            pass
        return 0

    @property
    def total_cursos(self):
        try:
            return len(self.cursos) if self.cursos else 0
        except Exception:
            return 0

    @property
    def total_ucs(self):
        try:
            return len(self.ucs) if self.ucs else 0
        except Exception:
            return 0

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_descricao': self.role_descricao,
            'role_ativo': self.role_ativo,
            'total_usuarios': self.total_usuarios,
            'total_temas': self.total_temas,
            'total_cursos': self.total_cursos,
            'total_ucs': self.total_ucs,
            'role_created_at': self.role_created_at.isoformat() if self.role_created_at else None
        }

    def __repr__(self):
        return f"<AnimaDiscordRole {self.role_id} - {self.role_descricao} (Ativo: {self.role_ativo})>"
