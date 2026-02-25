# ─── Imagen app backend: código sobre la imagen base ─────────────────────────
#
# La imagen base ya tiene Python 3.12 + todas las dependencias instaladas.
# Este Dockerfile solo añade el código fuente (~100KB).
#
# Se reconstruye en cada commit a main → deploy en ~15 segundos.
#
# Build local:
#   docker build -t <acr>.azurecr.io/qrgen/backend-app:latest backend/
#   docker push <acr>.azurecr.io/qrgen/backend-app:latest

ARG BASE_IMAGE=qrgen/backend-base:latest
FROM ${BASE_IMAGE}

WORKDIR /app

# Solo el código — las dependencias ya están en la imagen base
COPY app/ app/
COPY fonts/ fonts/

EXPOSE 8080

# Las variables de entorno se inyectan desde Container Apps / docker-compose
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
