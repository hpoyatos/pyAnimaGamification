from .base import BaseDAO
from models.curso import Curso

class CursoDAO(BaseDAO):
    model = Curso
