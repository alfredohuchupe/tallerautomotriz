from app import chatbot


def conversar(client, *mensajes):
    ultima = None
    for m in mensajes:
        r = client.post("/api/chat", json={"mensaje": m})
        assert r.status_code == 200
        ultima = r.get_json()
    return ultima


def test_flujo_completo_de_cita(client):
    res = conversar(client, "Hola, quiero agendar una cita", "Pedro Díaz",
                    "Nissan Sentra 2019", "Cambio de aceite", "28/11 a las 10:00")
    assert "Cita confirmada" in res["respuesta"]
    assert res["funciones"][0]["funcion"] == "agendar_cita"
    assert res["motor"] == "local"
    citas = client.get("/api/citas").get_json()["citas"]
    assert any(c["nombre"] == "Pedro Díaz" and c["origen"] == "chatbot" for c in citas)


def test_estado_pide_placa_si_falta(client):
    res = conversar(client, "¿Cuál es el estado de mi vehículo?")
    assert res["funciones"] == [] and "placa" in res["respuesta"].lower()
    res = conversar(client, "XYZ-789")
    assert res["funciones"][0]["funcion"] == "consultar_estado_vehiculo"
    assert "Listo para entrega" in res["respuesta"]


def test_estado_con_placa_directa(client):
    res = conversar(client, "estado de mi auto ABC-123")
    assert "60%" in res["respuesta"]


def test_cotizar_repuesto(client):
    res = conversar(client, "Quiero cotizar pastillas de freno", "Toyota Corolla")
    assert res["funciones"][0]["funcion"] == "cotizar_repuesto"
    assert "Precio referencial" in res["respuesta"]


def test_fuera_de_alcance_y_horario(client):
    assert conversar(client, "¿Me das una receta de ceviche?")["respuesta"] == chatbot.FUERA_DE_ALCANCE
    assert "Lunes a viernes" in conversar(client, "¿Cuál es su horario?")["respuesta"]


def test_cancelar_y_reiniciar(client):
    conversar(client, "agendar cita")
    assert "cancelé" in conversar(client, "cancelar")["respuesta"]
    r = client.post("/api/chat/reiniciar")
    assert r.status_code == 200


def test_mensaje_vacio(client):
    assert client.post("/api/chat", json={"mensaje": "  "}).status_code == 400


def test_ejecutar_funcion_desconocida(app):
    with app.app_context():
        assert "no está disponible" in chatbot.ejecutar_funcion("borrar_todo", {})
        assert chatbot.ejecutar_funcion("agendar_cita", {"nombre_cliente": "?"}).startswith("ERROR")


def test_cita_con_servicio_en_primer_mensaje(client):
    res = conversar(client, "Quiero una cita para cambio de frenos", "Rosa", "Kia Picanto",
                    "lunes 9am")
    assert res["funciones"][0]["argumentos"]["servicio"] == "Cambio de frenos"
    assert "Cita confirmada" in res["respuesta"]
