import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Fuso horário padrão do sistema: São Paulo / Brasília (-03:00)
TIMEZONE_NAME = os.getenv("TIMEZONE", "America/Sao_Paulo")
try:
    LOCAL_TZ = ZoneInfo(TIMEZONE_NAME)
except Exception:
    LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

def get_local_now() -> datetime:
    """
    Retorna a data e hora atual no fuso horário local de São Paulo (UTC-3),
    sem tzinfo (naive) para total compatibilidade com colunas DATETIME do MySQL/MariaDB.
    """
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)

def to_local_datetime(dt: datetime) -> datetime:
    """
    Converte um datetime para o fuso local de São Paulo caso possua tzinfo,
    ou o mantém se for naive.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(LOCAL_TZ).replace(tzinfo=None)
    return dt
