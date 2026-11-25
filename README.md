# 🔧 AutoTaller Pro: Taller Automotriz

[![CI-CD Taller Automotriz](https://github.com/alfredohuchupe/tallerautomotriz/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/alfredohuchupe/tallerautomotriz/actions/workflows/ci-cd.yml)

Aplicación web de un taller automotriz que une, en un solo sistema, los dos trabajos previos del curso:

| Origen | Qué era | Qué es ahora en la web |
|---|---|---|
| `chatAutomotriz.py` (Streamlit + Groq) | Chatbot con *Function Calling* para citas, estado y repuestos | **Asistente virtual** (página y widget flotante) con las mismas 3 funciones, ahora conectadas a una base de datos real |
| `Flujo-RPA` (Power Automate Desktop) | Lee Excel, valida correo/teléfono, envía Outlook + WhatsApp y marca "Enviado" | **Módulo de recordatorios** que ejecuta el mismo flujo desde la web |

Todo se compila, se prueba y se despliega en un contenedor **Docker** de forma automática con **GitHub Actions**.

![Inicio](docs/img/01-inicio.jpg)

## Funcionalidades

- **Inicio**: servicios con precios referenciales, horario y contacto.
- **Agendar cita**: formulario con validación (teléfono de 9 dígitos, correo) que devuelve un código `#ALT-XXXX`.
- **Estado del vehículo**: búsqueda por placa (`ABC-123`) o ticket (`ALT-1001`) con barra de avance.
- **Repuestos**: catálogo con stock y cotización.
- **Asistente virtual**:
  - Con `GROQ_API_KEY`: IA `openai/gpt-oss-20b` con *Function Calling* (igual que el chatbot original).
  - Sin clave: motor local por reglas que ejecuta las mismas funciones. También es el que usan las pruebas del pipeline.
  - Entrada por voz con la Web Speech API del navegador.
- **Panel del taller**: lista de citas (web, API y chatbot) y actualización del estado y el avance.
- **Recordatorios (RPA)**: valida con las mismas expresiones regulares del flujo RPA y genera el correo y el enlace `wa.me/51…`.
- **API REST**: `/api/health`, `/api/servicios`, `/api/citas`, `/api/estado/<placa>`, `/api/repuestos/cotizar`, `/api/chat`, `/api/recordatorios/ejecutar`.

## Ejecutar en local

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements-dev.txt
python wsgi.py                    # http://localhost:8000
pytest --cov=app                  # pruebas
```

### Con Docker

```bash
docker compose up -d --build      # http://localhost:8080
```

o usando la imagen que publica el pipeline:

```bash
docker run -d -p 8080:8000 -v taller_data:/data ghcr.io/alfredohuchupe/tallerautomotriz:latest
```

Para activar la IA, copia `.env.example` como `.env` y coloca tu `GROQ_API_KEY`. **Nunca subas la clave al repositorio.**

## Pipeline CI/CD

![Pipeline](docs/img/pipeline-cicd.png)

```mermaid
flowchart LR
    A[git push / PR a main] --> B[1. Compilación<br/>pip install · flake8 · compileall]
    B --> C[2. Pruebas<br/>pytest · cobertura ≥ 80%]
    C --> D[3. Docker<br/>build · smoke test · push GHCR]
    D -->|solo main| E[4. Despliegue<br/>docker pull · docker run · health check]
    E --> F[(Contenedor tallerautomotriz :8080)]
```

Archivo: [`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)

| Job | Qué hace | Falla si… |
|---|---|---|
| 1. Compilación | Instala dependencias, ejecuta `flake8`, compila con `compileall` y verifica que la app arranca | hay errores de sintaxis o estilo |
| 2. Pruebas | Ejecuta `pytest` (44 pruebas) con cobertura y publica `junit.xml` y `coverage.xml` | falla alguna prueba o la cobertura baja del 80 % |
| 3. Imagen Docker | Construye la imagen multi-etapa, la arranca, prueba `/api/health`, `/` y `/api/chat` y la publica en GHCR | el contenedor no responde |
| 4. Despliegue | Descarga la imagen exacta del commit, reemplaza el contenedor, monta el volumen y hace el health check | el contenedor no queda saludable |

### Secretos y variables (Settings → Secrets and variables → Actions)

| Nombre | Tipo | Uso |
|---|---|---|
| `GROQ_API_KEY` | Secret (opcional) | Activa la IA en el contenedor desplegado |
| `SECRET_KEY` | Secret (opcional) | Clave de sesión de Flask |
| `DEPLOY_RUNNER` | Variable (opcional) | `self-hosted` para desplegar en un servidor propio con Docker (despliegue persistente) |

## Estructura

```
app/
  __init__.py        # create_app (fábrica Flask)
  db.py              # SQLite + datos de demostración
  services.py        # agendar_cita, consultar_estado_vehiculo, cotizar_repuesto
  chatbot.py         # Function Calling (Groq) + motor local
  recordatorios.py   # flujo RPA en versión web
  routes.py / api.py # páginas HTML y API REST
  templates/ static/
tests/               # pytest
Dockerfile · docker-compose.yml · .github/workflows/ci-cd.yml
docs/                # documento del trabajo e imágenes
```
