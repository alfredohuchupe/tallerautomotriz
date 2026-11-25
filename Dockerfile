# ---------- Etapa 1: compilación (genera wheels de las dependencias) ----------
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- Etapa 2: imagen final liviana ----------
FROM python:3.12-slim
ARG APP_VERSION=1.0.0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} \
    DATABASE_PATH=/data/taller.db \
    PORT=8000
LABEL org.opencontainers.image.title="AutoTaller Pro" \
      org.opencontainers.image.description="Web del taller automotriz con citas y asistente virtual" \
      org.opencontainers.image.source="https://github.com/alfredohuchupe/tallerautomotriz"

WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels \
 && useradd --create-home --uid 1000 taller \
 && mkdir -p /data && chown taller:taller /data
COPY --chown=taller:taller app ./app
COPY --chown=taller:taller wsgi.py .
RUN python -m compileall -q app

USER taller
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --access-logfile - wsgi:app"]
