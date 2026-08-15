from extensions import db
from datetime import datetime

class AnimaDiscordRole(db.Model):
    __tablename__ = 'anima_discord_role'

    role_id = db.Column(db.String(20), primary_key=True)
    role_descricao = db.Column(db.String(150), nullable=False)
    role_created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    cursos = db.relationship('Curso', back_populates='role_rel', lazy=True)
    ucs = db.relationship('Uc', back_populates='role_rel', lazy=True)

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_descricao': self.role_descricao,
            'role_created_at': self.role_created_at.isoformat() if self.role_created_at else None
        }

    def __repr__(self):
        return f"<AnimaDiscordRole {self.role_id} - {self.role_descricao}>"
