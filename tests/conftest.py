"""Configuración de pruebas.

Por defecto cada prueba usa una base SQLite temporal y nueva.
Si existe la variable TEST_DATABASE_URL (en el pipeline, un PostgreSQL de servicio),
las mismas pruebas se ejecutan contra PostgreSQL, vaciando las tablas antes de cada una.
"""
import os

import pytest

from app import create_app, db

PG_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(autouse=True)
def _postgres_limpio(monkeypatch):
    """En modo PostgreSQL, cualquier create_app() de las pruebas usa la base de servicio."""
    if PG_URL:
        monkeypatch.setenv("DATABASE_URL", PG_URL)
        app = create_app({"TESTING": True, "DATABASE_URL": PG_URL})
        with app.app_context():
            db.borrar_tablas()
            db.init_db()
    yield


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path / "test.db"),
        "DATABASE_URL": PG_URL,
        "GROQ_API_KEY": "",  # las pruebas usan el motor local (sin red)
        "SECRET_KEY": "test",
    })
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
