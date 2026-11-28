"""API REST (JSON) del taller."""
import hmac

from flask import Blueprint, current_app, jsonify, request, session

from . import chatbot, recordatorios, services
from .db import get_db, motor
from .services import ValidacionError

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    get_db().execute("SELECT 1").fetchone()
    return jsonify(status="ok", version=current_app.config["APP_VERSION"], base_datos=motor(),
                   motor_chat="ia" if current_app.config.get("GROQ_API_KEY") else "local")


@bp.get("/servicios")
def servicios():
    return jsonify(servicios=services.SERVICIOS, horario=services.HORARIO)


@bp.get("/citas")
def citas_listar():
    return jsonify(citas=services.listar_citas())


@bp.post("/citas")
def citas_crear():
    d = request.get_json(silent=True) or {}
    try:
        res = services.agendar_cita(
            nombre_cliente=d.get("nombre_cliente"), modelo_auto=d.get("modelo_auto"),
            servicio=d.get("servicio"), fecha_hora=d.get("fecha_hora"),
            telefono=d.get("telefono"), correo=d.get("correo"), placa=d.get("placa"),
            origen="api")
    except ValidacionError as e:
        return jsonify(error=str(e)), 400
    return jsonify(res), 201


@bp.get("/estado/<path:placa_o_ticket>")
def estado(placa_o_ticket):
    res = services.consultar_estado_vehiculo(placa_o_ticket)
    return jsonify(res), (200 if res["encontrado"] else 404)


@bp.get("/repuestos/cotizar")
def cotizar():
    try:
        res = services.cotizar_repuesto(request.args.get("pieza"), request.args.get("modelo"))
    except ValidacionError as e:
        return jsonify(error=str(e)), 400
    return jsonify(res)


@bp.post("/chat")
def chat():
    d = request.get_json(silent=True) or {}
    mensaje = (d.get("mensaje") or "").strip()
    if not mensaje:
        return jsonify(error="El mensaje está vacío."), 400
    if len(mensaje) > 1000:
        return jsonify(error="El mensaje es demasiado largo."), 400
    datos = {"historial": session.get("historial", []), "estado": session.get("estado", {})}
    res = chatbot.responder(datos, mensaje)
    session["historial"] = datos["historial"]
    session["estado"] = datos.get("estado", {})
    return jsonify(res)


@bp.post("/chat/reiniciar")
def chat_reiniciar():
    session.pop("historial", None)
    session.pop("estado", None)
    return jsonify(respuesta=chatbot.BIENVENIDA)


@bp.post("/recordatorios/ejecutar")
def recordatorios_ejecutar():
    return jsonify(recordatorios.ejecutar_recordatorios(current_app.config["WHATSAPP_PAIS"]))


# ----------------------------------------------------------------------
# Integración con Power Automate Desktop (RPA)
# El flujo pide los clientes pendientes, envía el correo (Outlook) y el
# WhatsApp desde la PC, y luego marca cada cliente como "Enviado".
# Protegido con la cabecera X-RPA-Token porque devuelve datos personales.
# ----------------------------------------------------------------------
def _rpa_autorizado():
    token = current_app.config.get("RPA_TOKEN", "")
    enviado = request.headers.get("X-RPA-Token", "")
    return bool(token) and hmac.compare_digest(token, enviado)


@bp.get("/rpa/pendientes")
def rpa_pendientes():
    if not _rpa_autorizado():
        return jsonify(error="No autorizado"), 401
    clientes = [
        {
            "Id": c["id"],
            "Nombre": c["nombre"],
            "Placa": c["placa"],
            "Correo": c["correo"] or "",
            "Teléfono": c["telefono"] or "",
            "FechaMantenimiento": c["fecha_mantenimiento"],
            "Estado": c["estado"],
        }
        for c in recordatorios.listar_clientes(current_app.config["WHATSAPP_PAIS"])
        if c["estado"] == "Pendiente"
    ]
    return jsonify(total=len(clientes), clientes=clientes)


@bp.post("/rpa/enviado/<int:cliente_id>")
def rpa_marcar_enviado(cliente_id):
    if not _rpa_autorizado():
        return jsonify(error="No autorizado"), 401
    if not recordatorios.marcar_enviado(cliente_id):
        return jsonify(error="Cliente no encontrado"), 404
    return jsonify(ok=True, id=cliente_id, estado="Enviado")
