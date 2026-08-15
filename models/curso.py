from extensions import db
from datetime import datetime

class Curso(db.Model):
    __tablename__ = 'curso'

    curso_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curso_parceira = db.Column(db.Enum('Red Hat', 'Google', 'AWS', 'Cisco', 'Microsoft', 'Oracle', name='curso_parceira_enum'), nullable=False)
    curso_nome = db.Column(db.String(120), nullable=False)
    curso_descricao = db.Column(db.Text, nullable=True)
    curso_dt_inicio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    curso_dt_fim = db.Column(db.DateTime, nullable=False)
    curso_agente = db.Column(db.String(60), nullable=False)
    curso_role = db.Column(db.String(22), nullable=True)
    curso_param = db.Column(db.String(100), nullable=True)
    curso_sinonimos = db.Column(db.Text, nullable=True)
    curso_carga_horaria = db.Column(db.Integer, nullable=True)
    curso_idioma = db.Column(db.String(20), default='pt-br', nullable=True)
    curso_prerequisito_id = db.Column(db.Integer, db.ForeignKey('curso.curso_id', ondelete='SET NULL'), nullable=True)
    curso_url_inscricao = db.Column(db.String(255), nullable=True)

    # Relationships
    inscricoes = db.relationship('UsuarioCurso', backref='curso', lazy=True)
    prerequisito = db.relationship('Curso', remote_side=[curso_id], backref='cursos_dependentes', lazy=True)

    @property
    def idioma_label(self):
        if self.curso_idioma == 'en-us':
            return '🇺🇸 Inglês (en-us)'
        return '🇧🇷 Português do Brasil (pt-br)'

    def to_dict(self):
        return {
            'curso_id': self.curso_id,
            'curso_parceira': self.curso_parceira,
            'curso_nome': self.curso_nome,
            'curso_descricao': self.curso_descricao,
            'curso_dt_inicio': self.curso_dt_inicio.isoformat() if self.curso_dt_inicio else None,
            'curso_dt_fim': self.curso_dt_fim.isoformat() if self.curso_dt_fim else None,
            'curso_agente': self.curso_agente,
            'curso_role': self.curso_role,
            'curso_param': self.curso_param,
            'curso_sinonimos': self.curso_sinonimos,
            'curso_carga_horaria': self.curso_carga_horaria,
            'curso_idioma': self.curso_idioma,
            'curso_idioma_label': self.idioma_label,
            'curso_prerequisito_id': self.curso_prerequisito_id,
            'curso_prerequisito_nome': self.prerequisito.curso_nome if self.prerequisito else None,
            'curso_url_inscricao': self.curso_url_inscricao
        }
