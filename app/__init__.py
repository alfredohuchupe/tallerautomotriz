"""AutoTaller Pro - Aplicación web del Taller Automotriz.

Módulos:
- Sitio web (servicios, contacto)
- Agendamiento de citas
- Consulta de estado del vehículo
- Cotización de repuestos
- Asistente virtual (chatbot) con Function Calling (Groq) o modo local
- Recordatorios de mantenimiento (versión web del flujo RPA)
"""
import os

from flask import Flask

from . import db

__version__ = "1.0.0"


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-cambiar-en-produccion"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", os.path.join(app.instance_path, "taller.db")
        ),
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        GROQ_API_KEY=os.environ.get("GROQ_API_KEY", ""),
        GROQ_MODEL=os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b"),
        APP_VERSION=os.environ.get("APP_VERSION", __version__),
        WHATSAPP_PAIS=os.environ.get("WHATSAPP_PAIS", "51"),
    )

    if test_config:
        app.config.update(test_config)
    # Render/Heroku a veces entregan "postgres://"; psycopg prefiere "postgresql://"
    if app.config["DATABASE_URL"].startswith("postgres://"):
        app.config["DATABASE_URL"] = "postgresql://" + app.config["DATABASE_URL"][len("postgres://"):]

    os.makedirs(os.path.dirname(app.config["DATABASE"]) or ".", exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.init_db()

    from .routes import bp as web_bp
    from .api import bp as api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_globals():
        return {
            "app_version": app.config["APP_VERSION"],
            "ia_activa": bool(app.config.get("GROQ_API_KEY")),
        }

    return app
