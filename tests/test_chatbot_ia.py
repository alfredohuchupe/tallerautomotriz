"""Prueba del motor IA (Groq) simulando la API, sin acceso a red."""
import json

from app import create_app


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_function_calling_con_groq_simulado(tmp_path, monkeypatch):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "ia.db"),
                      "GROQ_API_KEY": "clave-falsa"})
    llamadas = []

    def fake_post(url, headers, timeout, json):  # noqa: A002
        llamadas.append(json)
        if json["tool_choice"] == "auto":
            return FakeResp({"choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call_1", "type": "function", "function": {
                    "name": "consultar_estado_vehiculo",
                    "arguments": '{"placa_o_ticket": "ABC-123"}'}}]}}]})
        tool_msg = json["messages"][-1]
        assert tool_msg["role"] == "tool" and "60%" in tool_msg["content"]
        return FakeResp({"choices": [{"message": {"content": "Tu auto va al 60%."}}]})

    monkeypatch.setattr("app.chatbot.requests.post", fake_post)
    r = app.test_client().post("/api/chat", json={"mensaje": "estado ABC-123"})
    data = r.get_json()
    assert data["motor"] == "ia"
    assert data["respuesta"] == "Tu auto va al 60%."
    assert data["funciones"][0]["argumentos"] == {"placa_o_ticket": "ABC-123"}
    assert len(llamadas) == 2


def test_si_groq_falla_usa_motor_local(tmp_path, monkeypatch):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "ia2.db"),
                      "GROQ_API_KEY": "clave-falsa"})

    def falla(*a, **k):
        raise ConnectionError("sin red")

    monkeypatch.setattr("app.chatbot.requests.post", falla)
    data = app.test_client().post("/api/chat", json={"mensaje": "¿horario?"}).get_json()
    assert data["motor"] == "local" and "Lunes" in data["respuesta"]
    assert json.dumps(data)
