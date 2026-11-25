"""Funciones de negocio del taller.

Son las mismas funciones que usaba el chatbot original (agendar_cita,
consultar_estado_vehiculo, cotizar_repuesto), ahora conectadas a una base
de datos real y reutilizadas por la web, la API REST y el asistente.
"""
import random
import re
import unicodedata

from .db import get_db

SERVICIOS = [
    {"nombre": "Mantenimiento preventivo", "precio": 150, "icono": "🛠️",
     "detalle": "Cambio de aceite, filtros y revisión de 30 puntos."},
    {"nombre": "Cambio de aceite", "precio": 60, "icono": "🛢️",
     "detalle": "Aceite sintético o semisintético y filtro."},
    {"nombre": "Cambio de frenos", "precio": 120, "icono": "🛑",
     "detalle": "Pastillas, discos y purga del sistema."},
    {"nombre": "Diagnóstico electrónico", "precio": 80, "icono": "💻",
     "detalle": "Escaneo computarizado OBD-II y reporte."},
    {"nombre": "Alineamiento y balanceo", "precio": 70, "icono": "🎯",
     "detalle": "Alineación por computadora y balanceo de 4 llantas."},
    {"nombre": "Suspensión", "precio": 180, "icono": "🚙",
     "detalle": "Revisión y cambio de amortiguadores y rótulas."},
    {"nombre": "Afinamiento de motor", "precio": 200, "icono": "⚙️",
     "detalle": "Bujías, inyectores, limpieza de cuerpo de aceleración."},
    {"nombre": "Aire acondicionado", "precio": 110, "icono": "❄️",
     "detalle": "Carga de gas, revisión de compresor y fugas."},
]

HORARIO = "Lunes a viernes 8:00 a. m. – 6:00 p. m. | Sábados 8:00 a. m. – 1:00 p. m."

RE_EMAIL = re.compile(r"^[\w\-.]+@([\w-]+\.)+[\w-]{2,4}$")
RE_TELEFONO = re.compile(r"^\d{9}$")
RE_PLACA = re.compile(r"\b([A-Za-z0-9]{3})-?(\d{3})\b")
RE_CODIGO = re.compile(r"\bALT-?(\d{3,5})\b", re.IGNORECASE)


class ValidacionError(ValueError):
    """Error de validación de datos de entrada."""


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto or "")
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.lower().strip()


def valor_valido(valor) -> bool:
    """Mismas reglas del chatbot: nada vacío, nulo ni '?'."""
    return valor is not None and str(valor).strip() not in ("", "?")


def normalizar_placa(placa: str) -> str:
    placa = (placa or "").strip().upper().replace(" ", "")
    m = RE_PLACA.fullmatch(placa) or RE_PLACA.fullmatch(placa.replace("-", ""))
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return placa


def _nuevo_codigo(conn) -> str:
    while True:
        codigo = f"ALT-{random.randint(1000, 9999)}"
        if not conn.execute("SELECT 1 FROM citas WHERE codigo=?", (codigo,)).fetchone():
            return codigo


# ------------------------------------------------------------------
# AGENDAR CITA
# ------------------------------------------------------------------
def agendar_cita(nombre_cliente, modelo_auto, servicio, fecha_hora,
                 telefono=None, correo=None, placa=None, origen="web"):
    datos = {
        "nombre_cliente": nombre_cliente,
        "modelo_auto": modelo_auto,
        "servicio": servicio,
        "fecha_hora": fecha_hora,
    }
    for campo, valor in datos.items():
        if not valor_valido(valor):
            raise ValidacionError(f"Falta información para agendar la cita: {campo}.")
    if correo and not RE_EMAIL.match(correo.strip()):
        raise ValidacionError("El correo electrónico no tiene un formato válido.")
    if telefono and not RE_TELEFONO.match(telefono.strip()):
        raise ValidacionError("El teléfono debe tener 9 dígitos.")

    conn = get_db()
    codigo = _nuevo_codigo(conn)
    conn.execute(
        "INSERT INTO citas (codigo, nombre, telefono, correo, placa, modelo, "
        "servicio, fecha_hora, origen) VALUES (?,?,?,?,?,?,?,?,?)",
        (codigo, nombre_cliente.strip(), (telefono or "").strip(),
         (correo or "").strip(), normalizar_placa(placa) if placa else "",
         modelo_auto.strip(), servicio.strip(), fecha_hora.strip(), origen),
    )
    conn.commit()
    return {
        "codigo": codigo,
        "mensaje": (
            f"Cita confirmada exitosamente para {nombre_cliente.strip()}. "
            f"Vehículo: {modelo_auto.strip()}. Servicio: {servicio.strip()}. "
            f"Fecha/Hora: {fecha_hora.strip()}. Código de reserva: #{codigo}"
        ),
    }


def listar_citas():
    return [dict(r) for r in get_db().execute(
        "SELECT * FROM citas ORDER BY id DESC").fetchall()]


def actualizar_cita(codigo, estado, avance):
    conn = get_db()
    cur = conn.execute(
        "UPDATE citas SET estado=?, avance=? WHERE codigo=?",
        (estado, max(0, min(100, int(avance))), codigo),
    )
    conn.commit()
    return cur.rowcount > 0


# ------------------------------------------------------------------
# CONSULTAR ESTADO
# ------------------------------------------------------------------
def consultar_estado_vehiculo(placa_o_ticket):
    if not valor_valido(placa_o_ticket):
        raise ValidacionError(
            "Para consultar el estado del vehículo necesito la placa o número de ticket.")
    valor = placa_o_ticket.strip().upper().lstrip("#")
    if re.fullmatch(r"\d{3,5}", valor):
        valor = f"ALT-{valor}"
    if re.fullmatch(r"ALT\d{3,5}", valor):
        valor = f"ALT-{valor[3:]}"
    placa = normalizar_placa(valor)
    fila = get_db().execute(
        "SELECT * FROM citas WHERE UPPER(codigo)=? OR UPPER(placa)=? "
        "ORDER BY id DESC LIMIT 1",
        (valor, placa),
    ).fetchone()
    if not fila:
        return {
            "encontrado": False,
            "mensaje": (
                f"No encontramos un vehículo con placa/ticket {placa_o_ticket}. "
                "Verifica el dato o comunícate con el taller."
            ),
        }
    fila = dict(fila)
    return {
        "encontrado": True,
        "cita": fila,
        "mensaje": (
            f"El vehículo {fila['modelo']} (placa {fila['placa'] or '—'}, ticket "
            f"#{fila['codigo']}) se encuentra en la fase '{fila['estado']}'. "
            f"Avance: {fila['avance']}%. Servicio: {fila['servicio']}."
        ),
    }


# ------------------------------------------------------------------
# COTIZAR REPUESTO
# ------------------------------------------------------------------
def buscar_repuesto(pieza):
    texto = normalizar(pieza)
    mejor, puntaje = None, 0
    for fila in get_db().execute("SELECT * FROM repuestos").fetchall():
        claves = normalizar(fila["pieza"] + " " + fila["clave"]).split()
        p = sum(1 for palabra in texto.split()
                if len(palabra) > 3 and any(palabra[:5] in c for c in claves))
        if p > puntaje:
            mejor, puntaje = dict(fila), p
    return mejor


def cotizar_repuesto(pieza, modelo_auto):
    if not valor_valido(pieza) or not valor_valido(modelo_auto):
        raise ValidacionError(
            "Para cotizar el repuesto necesito el nombre de la pieza y el modelo del vehículo.")
    rep = buscar_repuesto(pieza)
    if not rep:
        return {
            "disponible": False,
            "mensaje": (
                f"No tenemos '{pieza}' en catálogo para {modelo_auto}. "
                "Podemos pedirlo bajo encargo; un asesor te contactará."
            ),
        }
    disponible = rep["stock"] > 0
    estado = (f"Disponible en stock ({rep['stock']} unid.)"
              if disponible else "Sin stock (pedido en 48-72 h)")
    return {
        "disponible": disponible,
        "repuesto": rep,
        "mensaje": (
            f"Cotización para {rep['pieza']} ({modelo_auto}): {estado}. "
            f"Precio referencial: S/ {rep['precio']:.2f} "
            "(no incluye mano de obra; sujeto a inspección)."
        ),
    }


def listar_repuestos():
    return [dict(r) for r in get_db().execute(
        "SELECT * FROM repuestos ORDER BY pieza").fetchall()]
