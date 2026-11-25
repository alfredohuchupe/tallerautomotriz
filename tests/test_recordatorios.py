from app import recordatorios


def test_validaciones_regex_del_rpa():
    ok = recordatorios.validar_cliente({"correo": "a.b-c@dominio.com.pe", "telefono": "987654321"})
    assert ok == {"correo_ok": True, "telefono_ok": True}
    mal = recordatorios.validar_cliente({"correo": "correo-invalido", "telefono": "98765"})
    assert mal == {"correo_ok": False, "telefono_ok": False}


def test_mensajes_whatsapp_y_correo():
    c = {"nombre": "Ana", "placa": "AAA-111", "fecha_mantenimiento": "2026-12-01",
         "telefono": "987111222", "correo": "ana@correo.com"}
    m = recordatorios.construir_mensajes(c, "51")
    assert m["whatsapp_url"].startswith("https://wa.me/51987111222?text=")
    assert m["asunto"] == "Recordatorio de mantenimiento preventivo - Placa AAA-111"
    assert "2026-12-01" in m["cuerpo"]


def test_ejecutar_flujo_marca_enviados_y_omite_invalidos(app):
    with app.app_context():
        rep = recordatorios.ejecutar_recordatorios()
        assert len(rep["enviados"]) == 2          # Ana y Luis
        assert len(rep["omitidos"]) == 2          # correo inválido / teléfono inválido
        assert rep["ya_enviados"] == 1            # Lucía
        estados = {c["nombre"]: c["estado"] for c in recordatorios.listar_clientes()}
        assert estados["Ana Torres"] == "Enviado"
        assert estados["Rosa Huamán"] == "Pendiente"
        # Segunda ejecución: no reenvía
        rep2 = recordatorios.ejecutar_recordatorios()
        assert rep2["enviados"] == [] and rep2["ya_enviados"] == 3
        recordatorios.reiniciar_estados()
        assert all(c["estado"] == "Pendiente" for c in recordatorios.listar_clientes())
