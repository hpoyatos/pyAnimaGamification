from extensions import db

class Usuario(db.Model):
    __tablename__ = 'usuario'

    usuario_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_discord_id = db.Column(db.String(20), nullable=True)
    usuario_nome = db.Column(db.String(120), nullable=False)
    usuario_email = db.Column(db.String(60), nullable=False)
    usuario_ra = db.Column(db.String(12), nullable=True)
    usuario_discord_name = db.Column(db.String(60), nullable=True)
    usuario_validado_code = db.Column(db.String(6), nullable=True)
    usuario_validado = db.Column(db.Boolean, nullable=False, default=False)
    usuario_validado_data = db.Column(db.DateTime, nullable=True)

    # Relationships
    kahoots = db.relationship('UsuarioKahoot', backref='usuario', lazy=True)
    pontos = db.relationship('Ponto', backref='usuario', lazy=True)
    inscricoes = db.relationship('UsuarioCurso', backref='usuario', lazy=True)

    def to_dict(self):
        return {
            'usuario_id': self.usuario_id,
            'usuario_discord_id': self.usuario_discord_id,
            'usuario_nome': self.usuario_nome,
            'usuario_email': self.usuario_email,
            'usuario_ra': self.usuario_ra,
            'usuario_discord_name': self.usuario_discord_name,
            'usuario_validado_code': self.usuario_validado_code,
            'usuario_validado': self.usuario_validado,
            'usuario_validado_data': self.usuario_validado_data.isoformat() if self.usuario_validado_data else None
        }
