from app import create_app, db


def test_esquema_postgres_se_adapta():
    assert "SERIAL PRIMARY KEY" in db.SCHEMA_PG
    assert "AUTOINCREMENT" not in db.SCHEMA_PG
    assert "datetime(" not in db.SCHEMA_PG


def test_traduce_marcadores():
    assert db.PostgresDB._sql("SELECT * FROM citas WHERE codigo=? AND placa=?") == \
        "SELECT * FROM citas WHERE codigo=%s AND placa=%s"


def test_detecta_motor(tmp_path):
    assert db.es_postgres("postgresql://u:p@host/db")
    assert db.es_postgres("postgres://u:p@host/db")
    assert not db.es_postgres("")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "x.db"), "DATABASE_URL": ""})
    with app.app_context():
        assert db.motor() == "sqlite"


def test_health_informa_motor(client):
    data = client.get("/api/health").get_json()
    assert data["base_datos"] in ("sqlite", "postgresql")
