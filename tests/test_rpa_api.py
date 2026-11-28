from app import create_app

TOKEN = "clave-de-prueba"


def cliente_rpa(tmp_path, token=TOKEN):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "rpa.db"), "RPA_TOKEN": token})
    return app.test_client()


def test_sin_clave_no_entrega_datos(tmp_path):
    c = cliente_rpa(tmp_path)
    assert c.get("/api/rpa/pendientes").status_code == 401
    assert c.get("/api/rpa/pendientes", headers={"X-RPA-Token": "otra"}).status_code == 401
    assert c.post("/api/rpa/enviado/1").status_code == 401


def test_api_desactivada_si_no_hay_token_configurado(tmp_path):
    c = cliente_rpa(tmp_path, token="")
    assert c.get("/api/rpa/pendientes", headers={"X-RPA-Token": ""}).status_code == 401


def test_flujo_power_automate(tmp_path):
    c = cliente_rpa(tmp_path)
    h = {"X-RPA-Token": TOKEN}
    data = c.get("/api/rpa/pendientes", headers=h).get_json()
    assert data["total"] == 4  # 4 pendientes en los datos de ejemplo
    primero = data["clientes"][0]
    assert set(primero) == {"Id", "Nombre", "Placa", "Correo", "Teléfono", "FechaMantenimiento", "Estado"}
    r = c.post(f"/api/rpa/enviado/{primero['Id']}", headers=h)
    assert r.status_code == 200 and r.get_json()["estado"] == "Enviado"
    assert c.get("/api/rpa/pendientes", headers=h).get_json()["total"] == 3
    assert c.post("/api/rpa/enviado/9999", headers=h).status_code == 404
