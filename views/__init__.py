# views/__init__.py
from .home_view import home_ui_bp
from .usuario_view import usuario_ui_bp
from .uc_view import uc_ui_bp
from .ponto_view import ponto_ui_bp
from .curso_view import curso_ui_bp
from .usuario_curso_view import usuario_curso_ui_bp
from .quiz_view import quiz_ui_bp

__all__ = [
    'home_ui_bp', 'usuario_ui_bp', 'uc_ui_bp',
    'ponto_ui_bp', 'curso_ui_bp', 'usuario_curso_ui_bp', 'quiz_ui_bp'
]
