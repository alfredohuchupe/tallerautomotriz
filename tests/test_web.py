import pytest


@pytest.mark.parametrize("ruta", ["/", "/citas", "/estado", "/repuestos", "/asistente",
                                  "/panel", "/recordatorios", "/estado?q=ABC-123",
                                  "/repuestos?pieza=bateria&modelo=Kia"])
def test_paginas_responden(client, ruta):
    r = client.get(ruta)
    assert r.status_code == 200
    assert "AutoTaller" in r.get_data(as_text=True)


def test_health(client):
    data = client.get("/api/health").get_json()
    assert data["status"] == "ok" and data["motor_chat"] == "local"


def test_formulario_de_cita(client):
    r = client.post("/citas", data={
        "nombre": "Lucas", "telefono": "987654321", "correo": "lucas@correo.com",
        "placa": "LUC-321", "modelo": "Mazda 3", "servicio": "Cambio de frenos",
        "fecha": "2026-12-05", "hora": "09:30"})
    html = r.get_data(as_text=True)
    assert "Cita confirmada" in html and "#ALT-" in html
    assert "LUC-321" in client.get("/panel").get_data(as_text=True)


def test_formulario_de_cita_con_errores(client):
    r = client.post("/citas", data={"nombre": "Lucas", "modelo": "", "servicio": ""})
    assert "Falta información" in r.get_data(as_text=True)


def test_api_citas(client):
    r = client.post("/api/citas", json={"nombre_cliente": "Eva", "modelo_auto": "VW Gol",
                                        "servicio": "Suspensión", "fecha_hora": "2026-12-10 08:00"})
    assert r.status_code == 201
    codigo = r.get_json()["codigo"]
    assert client.get(f"/api/estado/{codigo}").status_code == 200
    assert client.get("/api/estado/NOP-000").status_code == 404
    assert client.post("/api/citas", json={}).status_code == 400


def test_api_cotizar_y_servicios(client):
    assert client.get("/api/repuestos/cotizar?pieza=bateria&modelo=Kia").status_code == 200
    assert client.get("/api/repuestos/cotizar?pieza=bateria").status_code == 400
    assert len(client.get("/api/servicios").get_json()["servicios"]) >= 5


def test_panel_actualiza_estado(client):
    client.post("/panel/cita/ALT-1003", data={"estado": "En reparación", "avance": "70"})
    assert client.get("/api/estado/ALT-1003").get_json()["cita"]["avance"] == 70


def test_recordatorios_web(client):
    html = client.post("/recordatorios/ejecutar").get_data(as_text=True)
    assert "Resultado de la ejecución" in html and "wa.me/51" in html
    client.post("/recordatorios/cliente", data={
        "nombre": "Nuevo", "placa": "NEW-001", "correo": "n@correo.com",
        "telefono": "999888777", "fecha_mantenimiento": "2026-12-20"})
    assert "NEW-001" in client.get("/recordatorios").get_data(as_text=True)
    assert client.post("/api/recordatorios/ejecutar").get_json()["enviados"][0]["placa"] == "NEW-001"


def test_pagina_unica_con_todas_las_secciones(client):
    html = client.get("/").get_data(as_text=True)
    for seccion in ('id="ofertas"', 'id="servicios"', 'id="cita"', 'id="estado"',
                    'id="repuestos"', 'id="nosotros"', 'id="contacto"', 'id="chatWidget"'):
        assert seccion in html
    # El servicio en oferta muestra precio regular y precio de oferta
    assert "S/ 190" in html and "S/ 150" in html


def test_rutas_antiguas_llevan_a_su_seccion(client):
    assert 'data-seccion-inicial="estado"' in client.get("/estado").get_data(as_text=True)
    assert 'data-seccion-inicial="repuestos"' in client.get("/repuestos").get_data(as_text=True)
    assert "data-open" in client.get("/asistente").get_data(as_text=True)
