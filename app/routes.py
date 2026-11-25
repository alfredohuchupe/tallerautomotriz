"""Rutas de la página web (HTML)."""
from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)

from . import recordatorios, services
from .services import ValidacionError

bp = Blueprint("web", __name__)


def pagina(seccion=None, confirmacion=None, form=None, abrir_chat=False):
    """Toda la web pública es una sola página; las rutas solo indican a qué sección ir."""
    consulta = request.args.get("q", "").strip()
    pieza = request.args.get("pieza", "").strip()
    modelo = request.args.get("modelo", "").strip()
    resultado = services.consultar_estado_vehiculo(consulta) if consulta else None
    cotizacion = None
    if pieza or modelo:
        try:
            cotizacion = services.cotizar_repuesto(pieza, modelo)
        except ValidacionError as e:
            flash(str(e), "error")
    return render_template(
        "index.html", servicios=services.SERVICIOS, ofertas=services.OFERTAS, horario=services.HORARIO,
        repuestos=services.listar_repuestos(), confirmacion=confirmacion, form=form or {},
        consulta=consulta, resultado=resultado, pieza=pieza, modelo=modelo,
        cotizacion=cotizacion, seccion=seccion, abrir_chat=abrir_chat)


@bp.get("/")
def inicio():
    return pagina()


@bp.route("/citas", methods=["GET", "POST"])
def citas():
    """Sin JavaScript el formulario se envía aquí; con JavaScript se usa /api/citas."""
    confirmacion = None
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        fecha_hora = f"{form.get('fecha', '')} {form.get('hora', '')}".strip()
        try:
            confirmacion = services.agendar_cita(
                nombre_cliente=form.get("nombre", ""),
                modelo_auto=form.get("modelo", ""),
                servicio=form.get("servicio", ""),
                fecha_hora=fecha_hora if form.get("fecha") and form.get("hora") else "",
                telefono=form.get("telefono") or None,
                correo=form.get("correo") or None,
                placa=form.get("placa") or None,
            )
        except ValidacionError as e:
            flash(str(e), "error")
    return pagina("cita", confirmacion=confirmacion, form=form)


@bp.get("/estado")
def estado():
    return pagina("estado")


@bp.get("/repuestos")
def repuestos():
    return pagina("repuestos")


@bp.get("/asistente")
def asistente():
    return pagina(abrir_chat=True)


# ---------------------------------------------------------------- panel interno
@bp.get("/panel")
def panel():
    return render_template("panel.html", citas=services.listar_citas())


@bp.post("/panel/cita/<codigo>")
def panel_actualizar(codigo):
    services.actualizar_cita(codigo, request.form.get("estado", "Agendada"),
                             request.form.get("avance", 0) or 0)
    flash(f"Cita {codigo} actualizada.", "ok")
    return redirect(url_for("web.panel"))


@bp.get("/recordatorios")
def recordatorios_view():
    pais = current_app.config["WHATSAPP_PAIS"]
    return render_template("recordatorios.html",
                           clientes=recordatorios.listar_clientes(pais), reporte=None)


@bp.post("/recordatorios/ejecutar")
def recordatorios_ejecutar():
    pais = current_app.config["WHATSAPP_PAIS"]
    reporte = recordatorios.ejecutar_recordatorios(pais)
    return render_template("recordatorios.html",
                           clientes=recordatorios.listar_clientes(pais), reporte=reporte)


@bp.post("/recordatorios/cliente")
def recordatorios_cliente():
    f = request.form
    if all(services.valor_valido(f.get(k)) for k in
           ("nombre", "placa", "fecha_mantenimiento")):
        recordatorios.registrar_cliente(f["nombre"], f["placa"], f.get("correo", ""),
                                        f.get("telefono", ""), f["fecha_mantenimiento"])
        flash("Cliente registrado para recordatorio.", "ok")
    else:
        flash("Nombre, placa y fecha de mantenimiento son obligatorios.", "error")
    return redirect(url_for("web.recordatorios_view"))


@bp.post("/recordatorios/reiniciar")
def recordatorios_reiniciar():
    recordatorios.reiniciar_estados()
    flash("Todos los clientes volvieron a estado 'Pendiente'.", "ok")
    return redirect(url_for("web.recordatorios_view"))
