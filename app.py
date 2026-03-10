import os
from flask import Flask
from extensions import db
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

def create_app():
    # Carrega variáveis de ambiente (já deve ser automático via docker-compose env_file, mas por garantia)
    load_dotenv()

    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Configuração do Banco de Dados
    # SQLAlchemy necessita da URI do banco definida. Se não tiver no .env, usará sqlite em memória para evitar quebra no build.
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT', '3306') # Default MySQL port
    db_name = os.getenv('DB_NAME')

    if db_user and db_password and db_host and db_name:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
            'SQLALCHEMY_DATABASE_URI',
            'sqlite:///:memory:'
        )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicializa SQLAlchemy
    db.init_app(app)

    # Importa os models para garantir que as tabelas sejam conhecidas
    import models

    with app.app_context():
        # Cria as tabelas se elas não existirem no banco (idealmente usa-se Alembic/Flask-Migrate)
        pass # TEMP: db.create_all()

    # Registra as rotas
    from routes import usuario_bp, uc_bp, usuario_kahoot_bp, ponto_bp, curso_bp, usuario_curso_bp
    app.register_blueprint(usuario_bp)
    app.register_blueprint(uc_bp)
    app.register_blueprint(usuario_kahoot_bp)
    app.register_blueprint(ponto_bp)
    app.register_blueprint(curso_bp)
    app.register_blueprint(usuario_curso_bp)

    # Registra rotas visuais (UI)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'super-secret-key-gamification')
    from views import home_ui_bp, usuario_ui_bp, uc_ui_bp, ponto_ui_bp, curso_ui_bp, usuario_curso_ui_bp
    app.register_blueprint(home_ui_bp)
    app.register_blueprint(usuario_ui_bp)
    app.register_blueprint(uc_ui_bp)
    app.register_blueprint(ponto_ui_bp)
    app.register_blueprint(curso_ui_bp)
    app.register_blueprint(usuario_curso_ui_bp)

    @app.route('/health')
    def health():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
