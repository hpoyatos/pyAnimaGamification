from extensions import db

class UsuarioKahoot(db.Model):
    __tablename__ = 'usuario_kahoot'

    usuario_kahoot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    usuario_kahoot_nome = db.Column(db.String(60), nullable=False)

    def to_dict(self):
        return {
            'usuario_kahoot_id': self.usuario_kahoot_id,
            'usuario_id': self.usuario_id,
            'usuario_kahoot_nome': self.usuario_kahoot_nome
        }
