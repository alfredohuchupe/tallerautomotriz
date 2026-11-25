"""Recordatorios de mantenimiento preventivo.

Versión web del flujo RPA de Power Automate Desktop (Flujo-RPA):
  1. Leer clientes (antes: Excel Datos_Clientes.xlsx, columnas B..H).
  2. Validar correo con regex  ^[\\w-\\.]+@([\\w-]+\\.)+[\\w-]{2,4}$
  3. Validar teléfono con regex ^\\d{9}$
  4. Si Estado = 'Pendiente' y ambos son válidos:
       - Preparar el correo de recordatorio (antes: Outlook).
       - Preparar el mensaje de WhatsApp wa.me/51<teléfono> (antes: Edge).
       - Marcar el registro como 'Enviado' (antes: celda H del Excel).
  5. Los registros con datos inválidos quedan como 'Pendiente' y se reportan.
"""
from urllib.parse import quote

from .db import get_db
from .services import RE_EMAIL, RE_TELEFONO

ASUNTO = "Recordatorio de mantenimiento preventivo - Placa {placa}"
CUERPO = (
    "Hola {nombre},\n\n"
    "Te recordamos que tu vehículo con placa {placa} tiene programado su servicio "
    "de mantenimiento para el día {fecha}.\n\n"
    "Te hemos enviado los detalles a tu WhatsApp. Por favor, respóndenos por ese "
    "medio para coordinar la hora de tu cita.\n\n¡Saludos!"
)
WHATSAPP = (
    "Hola {nombre}, te recordamos que tu vehículo con placa {placa} requiere su "
    "servicio de mantenimiento para el día {fecha}"
)


def validar_cliente(cliente):
    return {
        "correo_ok": bool(RE_EMAIL.match((cliente.get("correo") or "").strip())),
        "telefono_ok": bool(RE_TELEFONO.match((cliente.get("telefono") or "").strip())),
    }


def construir_mensajes(cliente, pais="51"):
    datos = {
        "nombre": cliente["nombre"],
        "placa": cliente["placa"],
        "fecha": cliente["fecha_mantenimiento"],
    }
    texto_wa = WHATSAPP.format(**datos)
    asunto = ASUNTO.format(**datos)
    cuerpo = CUERPO.format(**datos)
    return {
        "asunto": asunto,
        "cuerpo": cuerpo,
        "whatsapp_url": f"https://wa.me/{pais}{cliente['telefono']}?text={quote(texto_wa)}",
        "mailto_url": f"mailto:{cliente['correo']}?subject={quote(asunto)}&body={quote(cuerpo)}",
    }


def listar_clientes(pais="51"):
    filas = [dict(r) for r in get_db().execute(
        "SELECT * FROM clientes ORDER BY id").fetchall()]
    for c in filas:
        c.update(validar_cliente(c))
        c["mensajes"] = construir_mensajes(c, pais)
    return filas


def registrar_cliente(nombre, placa, correo, telefono, fecha_mantenimiento):
    conn = get_db()
    conn.execute(
        "INSERT INTO clientes (nombre, placa, correo, telefono, fecha_mantenimiento) "
        "VALUES (?,?,?,?,?)",
        (nombre.strip(), placa.strip().upper(), correo.strip(),
         telefono.strip(), fecha_mantenimiento.strip()),
    )
    conn.commit()


def ejecutar_recordatorios(pais="51"):
    """Recorre los clientes como el LOOP FOREACH del RPA y devuelve un reporte."""
    conn = get_db()
    reporte = {"enviados": [], "omitidos": [], "ya_enviados": 0}
    for c in listar_clientes(pais):
        if c["estado"] != "Pendiente":
            reporte["ya_enviados"] += 1
            continue
        if c["correo_ok"] and c["telefono_ok"]:
            conn.execute("UPDATE clientes SET estado='Enviado' WHERE id=?", (c["id"],))
            reporte["enviados"].append({
                "nombre": c["nombre"], "placa": c["placa"], **c["mensajes"]})
        else:
            motivos = []
            if not c["correo_ok"]:
                motivos.append("correo inválido")
            if not c["telefono_ok"]:
                motivos.append("teléfono inválido (debe tener 9 dígitos)")
            reporte["omitidos"].append({
                "nombre": c["nombre"], "placa": c["placa"], "motivo": ", ".join(motivos)})
    conn.commit()
    return reporte


def reiniciar_estados():
    conn = get_db()
    conn.execute("UPDATE clientes SET estado='Pendiente'")
    conn.commit()
