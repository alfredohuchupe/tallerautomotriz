"""Capa de datos.

- Sin DATABASE_URL: SQLite (archivo local o volumen Docker /data).
- Con DATABASE_URL=postgresql://...: PostgreSQL (por ejemplo Neon en la nube).
El resto de la aplicación usa la misma interfaz (execute, executemany, commit)
con marcadores '?', que aquí se traducen a '%s' para PostgreSQL.
"""
import sqlite3

from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS citas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    telefono TEXT,
    correo TEXT,
    placa TEXT,
    modelo TEXT NOT NULL,
    servicio TEXT NOT NULL,
    fecha_hora TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Agendada',
    avance INTEGER NOT NULL DEFAULT 0,
    origen TEXT NOT NULL DEFAULT 'web',
    creado TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    placa TEXT NOT NULL,
    correo TEXT,
    telefono TEXT,
    fecha_mantenimiento TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'Pendiente'
);

CREATE TABLE IF NOT EXISTS repuestos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pieza TEXT NOT NULL,
    clave TEXT NOT NULL,
    precio REAL NOT NULL,
    stock INTEGER NOT NULL
);
"""

# Mismo esquema adaptado a PostgreSQL
SCHEMA_PG = (
    SCHEMA.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    .replace("REAL NOT NULL", "DOUBLE PRECISION NOT NULL")
    .replace("(datetime('now', 'localtime'))",
             "(to_char(now() AT TIME ZONE 'America/Lima', 'YYYY-MM-DD HH24:MI:SS'))")
)

CITAS_DEMO = [
    ("ALT-1001", "Carlos Ramírez", "987654321", "carlos@correo.com", "ABC-123",
     "Toyota Corolla 2019", "Mantenimiento preventivo", "2026-11-26 09:00",
     "Inspección de mantenimiento", 60, "demo"),
    ("ALT-1002", "María López", "912345678", "maria@correo.com", "XYZ-789",
     "Hyundai Tucson 2021", "Cambio de frenos", "2026-11-26 11:00",
     "Listo para entrega", 100, "demo"),
    ("ALT-1003", "Jorge Quispe", "923456789", "jorge@correo.com", "BCD-456",
     "Kia Rio 2018", "Diagnóstico electrónico", "2026-11-27 15:00",
     "Agendada", 0, "demo"),
]

CLIENTES_DEMO = [
    ("Ana Torres", "AAA-111", "ana.torres@correo.com", "987111222", "2026-12-01", "Pendiente"),
    ("Luis Mendoza", "BBB-222", "luis.mendoza@correo.com", "987333444", "2026-12-02", "Pendiente"),
    ("Rosa Huamán", "CCC-333", "correo-invalido", "987555666", "2026-12-03", "Pendiente"),
    ("Pedro Salas", "DDD-444", "pedro.salas@correo.com", "98765", "2026-12-04", "Pendiente"),
    ("Lucía Vargas", "EEE-555", "lucia.vargas@correo.com", "987777888", "2026-11-20", "Enviado"),
]

REPUESTOS_DEMO = [
    ("Pastillas de freno", "freno pastilla", 85.0, 12),
    ("Filtro de aceite", "filtro aceite", 18.0, 40),
    ("Filtro de aire", "filtro aire", 22.0, 25),
    ("Batería 12V", "bateria", 120.0, 6),
    ("Bujías (juego x4)", "bujia", 35.0, 20),
    ("Amortiguador", "amortiguador suspension", 95.0, 8),
    ("Aceite sintético 5W-30 (galón)", "aceite lubricante", 45.0, 30),
    ("Kit de embrague", "embrague clutch", 260.0, 3),
    ("Llanta aro 15", "llanta neumatico", 110.0, 0),
]


def es_postgres(url):
    return bool(url) and url.startswith(("postgres://", "postgresql://"))


class PostgresDB:
    """Adaptador mínimo de psycopg con la misma interfaz que sqlite3."""

    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row

        self.conn = psycopg.connect(url, row_factory=dict_row)

    @staticmethod
    def _sql(sql):
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        return self.conn.execute(self._sql(sql), params)

    def executemany(self, sql, filas):
        with self.conn.cursor() as cur:
            cur.executemany(self._sql(sql), filas)

    def executescript(self, script):
        for sentencia in script.split(";"):
            if sentencia.strip():
                self.conn.execute(sentencia)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_db():
    if "db" not in g:
        url = current_app.config.get("DATABASE_URL")
        if es_postgres(url):
            g.db = PostgresDB(url)
        else:
            g.db = sqlite3.connect(current_app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_e=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def motor():
    return "postgresql" if es_postgres(current_app.config.get("DATABASE_URL")) else "sqlite"


def _vacia(conn, tabla):
    return conn.execute(f"SELECT COUNT(*) AS n FROM {tabla}").fetchone()["n"] == 0


def init_db():
    conn = get_db()
    if motor() == "postgresql":
        # gunicorn arranca varios procesos a la vez: este candado hace que solo uno
        # cree las tablas y cargue los datos; los demás esperan al commit.
        conn.execute("SELECT pg_advisory_xact_lock(4242)")
        conn.executescript(SCHEMA_PG)
    else:
        conn.executescript(SCHEMA)
    if _vacia(conn, "citas"):
        conn.executemany(
            "INSERT INTO citas (codigo, nombre, telefono, correo, placa, modelo, "
            "servicio, fecha_hora, estado, avance, origen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            CITAS_DEMO,
        )
    if _vacia(conn, "clientes"):
        conn.executemany(
            "INSERT INTO clientes (nombre, placa, correo, telefono, "
            "fecha_mantenimiento, estado) VALUES (?,?,?,?,?,?)",
            CLIENTES_DEMO,
        )
    if _vacia(conn, "repuestos"):
        conn.executemany(
            "INSERT INTO repuestos (pieza, clave, precio, stock) VALUES (?,?,?,?)",
            REPUESTOS_DEMO,
        )
    conn.commit()


def borrar_tablas():
    """Solo para pruebas: deja la base vacía."""
    conn = get_db()
    for tabla in ("citas", "clientes", "repuestos"):
        conn.execute(f"DROP TABLE IF EXISTS {tabla}")
    conn.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
