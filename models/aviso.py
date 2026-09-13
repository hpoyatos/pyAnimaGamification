from extensions import db
from datetime import datetime, timedelta

class AnimaAviso(db.Model):
    __tablename__ = 'anima_avisos'

    aviso_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aviso_titulo = db.Column(db.String(150), nullable=False)
    aviso_conteudo = db.Column(db.Text, nullable=False)
    aviso_tipo = db.Column(
        db.Enum('unico', 'recorrente', name='aviso_tipo_enum'),
        nullable=False,
        default='unico'
    )
    aviso_recorrencia_tipo = db.Column(
        db.Enum('diario', 'semanal', 'intervalo_horas', 'nenhum', name='aviso_recorrencia_tipo_enum'),
        nullable=False,
        default='nenhum'
    )
    aviso_recorrencia_valor = db.Column(db.Integer, nullable=False, default=1)
    aviso_usar_ia = db.Column(db.Boolean, nullable=False, default=False)
    aviso_ia_prompt = db.Column(db.String(255), nullable=True)
    aviso_ativo = db.Column(db.Boolean, nullable=False, default=True)
    aviso_canal_id = db.Column(db.String(30), nullable=False, default='1020488574732357632')
    aviso_dt_agendamento = db.Column(db.DateTime, nullable=True)
    aviso_dt_ultimo_envio = db.Column(db.DateTime, nullable=True)
    aviso_dt_proximo_envio = db.Column(db.DateTime, nullable=True)
    aviso_dt_criacao = db.Column(db.DateTime, default=datetime.utcnow)

    def calcular_proximo_envio(self, base_time=None):
        """
        Calcula a próxima data de envio com base no tipo de recorrência.
        Retorna datetime ou None (se for envio único concluído).
        """
        if self.aviso_tipo != 'recorrente':
            return None

        agora = base_time or datetime.now()

        if self.aviso_recorrencia_tipo == 'diario':
            return agora + timedelta(days=max(1, self.aviso_recorrencia_valor or 1))
        elif self.aviso_recorrencia_tipo == 'semanal':
            return agora + timedelta(weeks=max(1, self.aviso_recorrencia_valor or 1))
        elif self.aviso_recorrencia_tipo == 'intervalo_horas':
            return agora + timedelta(hours=max(1, self.aviso_recorrencia_valor or 1))

        return None

    @property
    def status_label(self):
        if not self.aviso_ativo:
            return 'Inativo'
        if self.aviso_tipo == 'recorrente':
            return 'Recorrente Ativo'
        if self.aviso_dt_ultimo_envio:
            return 'Enviado'
        return 'Agendado'

    def to_dict(self):
        return {
            'aviso_id': self.aviso_id,
            'aviso_titulo': self.aviso_titulo,
            'aviso_conteudo': self.aviso_conteudo,
            'aviso_tipo': self.aviso_tipo,
            'aviso_recorrencia_tipo': self.aviso_recorrencia_tipo,
            'aviso_recorrencia_valor': self.aviso_recorrencia_valor,
            'aviso_usar_ia': self.aviso_usar_ia,
            'aviso_ia_prompt': self.aviso_ia_prompt,
            'aviso_ativo': self.aviso_ativo,
            'aviso_canal_id': self.aviso_canal_id,
            'aviso_dt_agendamento': self.aviso_dt_agendamento.isoformat() if self.aviso_dt_agendamento else None,
            'aviso_dt_ultimo_envio': self.aviso_dt_ultimo_envio.isoformat() if self.aviso_dt_ultimo_envio else None,
            'aviso_dt_proximo_envio': self.aviso_dt_proximo_envio.isoformat() if self.aviso_dt_proximo_envio else None,
            'aviso_dt_criacao': self.aviso_dt_criacao.isoformat() if self.aviso_dt_criacao else None
        }
