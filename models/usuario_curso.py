from extensions import db
from datetime import datetime

class UsuarioCurso(db.Model):
    __tablename__ = 'usuario_curso'

    usuario_curso_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_redhat_id = db.Column(db.String(60), nullable=True)
    usuario_redhat_email = db.Column(db.String(100), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    curso_id = db.Column(db.Integer, db.ForeignKey('curso.curso_id'), nullable=False)
    usuario_curso_dt_solicitacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    usuario_curso_dt_inscricao = db.Column(db.DateTime, nullable=True)
    usuario_curso_situacao = db.Column(db.Enum('Pendente', 'Inscrito', 'Concluído', 'Validado', 'Creditado', name='usuario_curso_situacao_enum'), nullable=False, default='Pendente')
    usuario_curso_certificado = db.Column(db.LargeBinary, nullable=True)
    usuario_curso_obs = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'usuario_curso_id': self.usuario_curso_id,
            'usuario_redhat_id': self.usuario_redhat_id,
            'usuario_redhat_email': self.usuario_redhat_email,
            'usuario_id': self.usuario_id,
            'curso_id': self.curso_id,
            'usuario_curso_dt_solicitacao': self.usuario_curso_dt_solicitacao.isoformat() if self.usuario_curso_dt_solicitacao else None,
            'usuario_curso_dt_inscricao': self.usuario_curso_dt_inscricao.isoformat() if self.usuario_curso_dt_inscricao else None,
            'usuario_curso_situacao': self.usuario_curso_situacao,
            'usuario_curso_obs': self.usuario_curso_obs
        }
