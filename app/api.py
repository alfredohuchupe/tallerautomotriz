"""API REST (JSON) del taller."""
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
