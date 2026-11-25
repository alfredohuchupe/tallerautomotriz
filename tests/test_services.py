import pytest

from app import services
from app.services import ValidacionError


def test_agendar_cita_genera_codigo(app):
    with app.app_context():
        res = services.agendar_cita("Ana", "Kia Rio 2020", "Cambio de aceite",
                                    "2026-12-01 10:00", telefono="987654321",
                                    correo="ana@correo.com", placa="abc 999")
        assert res["codigo"].startswith("ALT-")
        assert "Cita confirmada" in res["mensaje"]
        cita = services.consultar_estado_vehiculo("ABC-999")
        assert cita["encontrado"] and cita["cita"]["nombre"] == "Ana"


@pytest.mark.parametrize("campo", ["nombre_cliente", "modelo_auto", "servicio", "fecha_hora"])
def test_agendar_cita_rechaza_datos_faltantes(app, campo):
    datos = {"nombre_cliente": "Ana", "modelo_auto": "Kia", "servicio": "Frenos",
             "fecha_hora": "mañana 9am"}
    datos[campo] = "?"
    with app.app_context(), pytest.raises(ValidacionError):
        services.agendar_cita(**datos)


def test_agendar_cita_valida_telefono_y_correo(app):
    with app.app_context():
        with pytest.raises(ValidacionError):
            services.agendar_cita("A", "B", "C", "D", telefono="12345")
        with pytest.raises(ValidacionError):
            services.agendar_cita("A", "B", "C", "D", correo="no-es-correo")


@pytest.mark.parametrize("consulta", ["ABC-123", "abc123", "ALT-1001", "#ALT-1001", "1001"])
def test_consultar_estado_por_placa_o_ticket(app, consulta):
    with app.app_context():
        res = services.consultar_estado_vehiculo(consulta)
        assert res["encontrado"]
        assert res["cita"]["codigo"] == "ALT-1001"
        assert "60%" in res["mensaje"]


def test_consultar_estado_no_encontrado(app):
    with app.app_context():
        assert not services.consultar_estado_vehiculo("ZZZ-000")["encontrado"]
        with pytest.raises(ValidacionError):
            services.consultar_estado_vehiculo("")


def test_cotizar_repuesto(app):
    with app.app_context():
        res = services.cotizar_repuesto("pastillas de freno", "Toyota Yaris")
        assert res["disponible"] and "S/ 85.00" in res["mensaje"]
        agotado = services.cotizar_repuesto("llanta", "Kia Rio")
        assert not agotado["disponible"]
        nada = services.cotizar_repuesto("turbo cuántico", "Kia Rio")
        assert "No tenemos" in nada["mensaje"]
        with pytest.raises(ValidacionError):
            services.cotizar_repuesto("filtro", "")


def test_actualizar_cita(app):
    with app.app_context():
        assert services.actualizar_cita("ALT-1003", "En reparación", 150)
        assert services.consultar_estado_vehiculo("ALT-1003")["cita"]["avance"] == 100
