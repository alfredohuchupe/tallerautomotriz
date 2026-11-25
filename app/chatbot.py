"""Asistente virtual del taller.

Dos motores:
- IA (Groq, modelo openai/gpt-oss-20b) con Function Calling, igual que el
  chatbot original en Streamlit. Se activa si existe GROQ_API_KEY.
- Motor local por reglas (sin dependencias externas), usado cuando no hay
  API Key y en las pruebas automatizadas del pipeline CI/CD.
Ambos ejecutan las mismas funciones de negocio de services.py.
"""
import json

import requests
from flask import current_app

from . import services
from .services import ValidacionError, normalizar

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = (
    "[ROL Y OBJETIVO]\nEres el asistente virtual oficial de un Taller Automotriz. "
    "Brindas información sobre servicios, agendamiento de citas, mantenimiento "
    "preventivo, reparaciones y repuestos.\n\n"
    "[ALCANCE]\nAtiendes únicamente consultas sobre servicios mecánicos, horarios ("
    + services.HORARIO + "), costos estimados, estado de vehículos en taller y citas.\n\n"
    "[TONO]\nProfesional, educado, empático y conciso.\n\n"
    "[REGLAS]\n1. No des diagnósticos definitivos ni presupuestos finales sin revisión.\n"
    "2. Los precios siempre son referenciales y sujetos a inspección.\n"
    "3. Para agendar una cita solicita: nombre, modelo del auto, servicio y fecha/hora.\n\n"
    "[FUNCTION CALLING]\n1. Nunca inventes ni supongas datos requeridos por una función.\n"
    "2. consultar_estado_vehiculo requiere placa o ticket dado por el usuario.\n"
    "3. cotizar_repuesto requiere pieza y modelo del vehículo.\n"
    "4. agendar_cita requiere nombre, modelo, servicio y fecha/hora.\n"
    "5. Nunca uses '?' ni valores vacíos como argumento.\n\n"
    "[FUERA DE ALCANCE]\nResponde: 'Lo siento, solo puedo ayudarte con consultas, citas "
    "y servicios de nuestro Taller Automotriz. ¿Tienes alguna pregunta sobre tu vehículo?'"
)

TOOLS = [
    {"type": "function", "function": {
        "name": "agendar_cita",
        "description": "Agenda una cita. Usar solo cuando el cliente dio nombre, "
                       "modelo del vehículo, servicio y fecha/hora.",
        "parameters": {"type": "object", "properties": {
            "nombre_cliente": {"type": "string", "description": "Nombre del cliente."},
            "modelo_auto": {"type": "string", "description": "Marca y modelo."},
            "servicio": {"type": "string", "description": "Servicio solicitado."},
            "fecha_hora": {"type": "string", "description": "Fecha y hora."}},
            "required": ["nombre_cliente", "modelo_auto", "servicio", "fecha_hora"]}}},
    {"type": "function", "function": {
        "name": "consultar_estado_vehiculo",
        "description": "Consulta el estado de un vehículo en el taller por placa o ticket.",
        "parameters": {"type": "object", "properties": {
            "placa_o_ticket": {"type": "string", "description": "Placa o número de ticket."}},
            "required": ["placa_o_ticket"]}}},
    {"type": "function", "function": {
        "name": "cotizar_repuesto",
        "description": "Consulta disponibilidad y precio referencial de un repuesto.",
        "parameters": {"type": "object", "properties": {
            "pieza": {"type": "string", "description": "Nombre del repuesto."},
            "modelo_auto": {"type": "string", "description": "Marca y modelo."}},
            "required": ["pieza", "modelo_auto"]}}},
]

FUERA_DE_ALCANCE = (
    "Lo siento, solo puedo ayudarte con consultas, citas y servicios de nuestro "
    "Taller Automotriz. ¿Tienes alguna pregunta sobre tu vehículo?"
)
BIENVENIDA = "¡Hola! Bienvenido al servicio de atención del taller. ¿En qué puedo ayudarte hoy?"


def ejecutar_funcion(nombre, argumentos):
    """Ejecuta una función de negocio validando argumentos (igual que el original)."""
    funciones = {
        "agendar_cita": lambda a: services.agendar_cita(origen="chatbot", **a)["mensaje"],
        "consultar_estado_vehiculo": lambda a: services.consultar_estado_vehiculo(**a)["mensaje"],
        "cotizar_repuesto": lambda a: services.cotizar_repuesto(**a)["mensaje"],
    }
    if nombre not in funciones:
        return f"Error: la función {nombre} no está disponible."
    try:
        return funciones[nombre](argumentos)
    except (ValidacionError, TypeError) as e:
        return f"ERROR: {e}"


# ======================================================================
# MOTOR IA (GROQ + FUNCTION CALLING)
# ======================================================================
def responder_ia(historial, mensaje):
    cfg = current_app.config
    headers = {"Authorization": f"Bearer {cfg['GROQ_API_KEY']}"}
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT}] + historial[-12:] + [
        {"role": "user", "content": mensaje}]
    r = requests.post(GROQ_URL, headers=headers, timeout=30, json={
        "model": cfg["GROQ_MODEL"], "messages": mensajes,
        "tools": TOOLS, "tool_choice": "auto"})
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    llamadas = []
    if msg.get("tool_calls"):
        mensajes.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": msg["tool_calls"]})
        for tc in msg["tool_calls"]:
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            resultado = ejecutar_funcion(tc["function"]["name"], args)
            llamadas.append({"funcion": tc["function"]["name"], "argumentos": args})
            mensajes.append({"role": "tool", "tool_call_id": tc["id"],
                             "name": tc["function"]["name"], "content": resultado})
        r = requests.post(GROQ_URL, headers=headers, timeout=30, json={
            "model": cfg["GROQ_MODEL"], "messages": mensajes,
            "tools": TOOLS, "tool_choice": "none"})
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
    return msg.get("content") or "", llamadas


# ======================================================================
# MOTOR LOCAL POR REGLAS
# ======================================================================
PASOS_CITA = [
    ("nombre_cliente", "¿A nombre de quién registro la cita?"),
    ("modelo_auto", "¿Cuál es la marca y modelo de tu vehículo? (ej. Toyota Yaris 2020)"),
    ("servicio", "¿Qué servicio necesitas? (ej. mantenimiento preventivo, frenos, diagnóstico)"),
    ("fecha_hora", "¿Qué fecha y hora prefieres? (ej. 28/11 a las 10:00)"),
]

PALABRAS_TALLER = (
    "auto carro vehiculo coche camioneta motor freno aceite llanta bateria cita "
    "taller servicio mantenimiento repuesto precio costo cuanto horario placa "
    "ticket estado diagnostico suspension embrague filtro bujia alineamiento "
    "balanceo aire hola buenas gracias"
).split()


def _servicio_en_texto(texto):
    t = normalizar(texto)
    for s in services.SERVICIOS:
        clave = normalizar(s["nombre"]).split()[-1]
        if normalizar(s["nombre"]) in t or (len(clave) > 4 and clave in t):
            return s["nombre"]
    return None


def responder_local(estado, mensaje):
    """Devuelve (respuesta, llamadas_funcion, nuevo_estado)."""
    t = normalizar(mensaje)
    estado = dict(estado or {})
    llamadas = []

    if t in ("cancelar", "salir", "reiniciar"):
        return "Listo, cancelé la operación. ¿En qué más puedo ayudarte?", [], {}

    # --- Flujo guiado en curso ---
    flujo = estado.get("flujo")
    if flujo == "cita":
        datos = estado.setdefault("datos", {})
        pendientes = [p for p in PASOS_CITA if p[0] not in datos]
        if not services.valor_valido(mensaje):
            return pendientes[0][1], [], estado
        datos[pendientes[0][0]] = mensaje.strip()
        if len(pendientes) > 1:
            return pendientes[1][1], [], estado
        llamadas.append({"funcion": "agendar_cita", "argumentos": dict(datos)})
        return ejecutar_funcion("agendar_cita", datos), llamadas, {}
    if flujo == "estado":
        args = {"placa_o_ticket": mensaje.strip()}
        llamadas.append({"funcion": "consultar_estado_vehiculo", "argumentos": args})
        return ejecutar_funcion("consultar_estado_vehiculo", args), llamadas, {}
    if flujo == "repuesto":
        datos = estado.setdefault("datos", {})
        if "pieza" not in datos:
            datos["pieza"] = mensaje.strip()
            return "¿Para qué marca y modelo de vehículo es el repuesto?", [], estado
        datos["modelo_auto"] = mensaje.strip()
        llamadas.append({"funcion": "cotizar_repuesto", "argumentos": dict(datos)})
        return ejecutar_funcion("cotizar_repuesto", datos), llamadas, {}

    # --- Detección de intención ---
    placa = services.RE_PLACA.search(mensaje) or services.RE_CODIGO.search(mensaje)
    if any(p in t for p in ("estado", "como va", "listo mi", "avance", "ticket")):
        if placa:
            args = {"placa_o_ticket": placa.group(0)}
            llamadas.append({"funcion": "consultar_estado_vehiculo", "argumentos": args})
            return ejecutar_funcion("consultar_estado_vehiculo", args), llamadas, {}
        return ("Con gusto. Indícame la placa (ej. ABC-123) o el número de ticket "
                "(ej. ALT-1001)."), [], {"flujo": "estado"}

    if any(p in t for p in ("cita", "agendar", "reservar", "turno", "programar")):
        datos = {}
        servicio = _servicio_en_texto(mensaje)
        nuevo = {"flujo": "cita", "datos": datos}
        intro = "¡Perfecto! Vamos a agendar tu cita. "
        if servicio:
            intro += f"Servicio: {servicio}. "
            datos["servicio"] = servicio
        return intro + PASOS_CITA[0][1], [], nuevo

    if any(p in t for p in ("repuesto", "cotiza", "pieza", "stock")):
        rep = services.buscar_repuesto(mensaje)
        if rep:
            return ("¿Para qué marca y modelo de vehículo necesitas "
                    f"{rep['pieza'].lower()}?"), [], {"flujo": "repuesto",
                                                      "datos": {"pieza": rep["pieza"]}}
        return "¿Qué repuesto necesitas cotizar?", [], {"flujo": "repuesto", "datos": {}}

    if "horario" in t or "atienden" in t or "abren" in t:
        return f"Nuestro horario de atención es: {services.HORARIO}", [], {}

    if any(p in t for p in ("precio", "costo", "cuanto", "servicios", "que hacen")):
        servicio = _servicio_en_texto(mensaje)
        if servicio:
            s = next(x for x in services.SERVICIOS if x["nombre"] == servicio)
            return (f"{s['nombre']}: desde S/ {s['precio']} (monto referencial, sujeto a "
                    f"inspección). {s['detalle']} ¿Deseas agendar una cita?"), [], {}
        lista = ", ".join(s["nombre"] for s in services.SERVICIOS)
        return (f"Ofrecemos: {lista}. ¿Sobre cuál deseas el costo referencial? "
                "Los montos están sujetos a inspección."), [], {}

    if any(p in t for p in ("hola", "buenas", "buenos")):
        return (BIENVENIDA + " Puedo agendar citas, consultar el estado de tu vehículo "
                "o cotizar repuestos."), [], {}
    if "gracias" in t:
        return "¡Con gusto! Si necesitas algo más sobre tu vehículo, aquí estoy. 🚗", [], {}

    if not any(p in t for p in PALABRAS_TALLER):
        return FUERA_DE_ALCANCE, [], {}
    return ("Puedo ayudarte a: 1) agendar una cita, 2) consultar el estado de tu "
            "vehículo, 3) cotizar un repuesto o 4) conocer precios y horarios. "
            "¿Qué necesitas?"), [], {}


def responder(sesion, mensaje):
    """Punto de entrada único. `sesion` es un dict mutable (Flask session)."""
    historial = sesion.get("historial", [])
    llamadas = []
    motor = "local"
    if current_app.config.get("GROQ_API_KEY"):
        try:
            respuesta, llamadas = responder_ia(historial, mensaje)
            motor = "ia"
        except Exception:  # noqa: BLE001 - si la IA falla, seguimos en modo local
            respuesta, llamadas, sesion["estado"] = responder_local(sesion.get("estado"), mensaje)
    else:
        respuesta, llamadas, sesion["estado"] = responder_local(sesion.get("estado"), mensaje)
    historial += [{"role": "user", "content": mensaje},
                  {"role": "assistant", "content": respuesta}]
    sesion["historial"] = historial[-20:]
    return {"respuesta": respuesta, "funciones": llamadas, "motor": motor}
