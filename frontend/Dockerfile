# ─── Imagen app frontend: código sobre la imagen base ────────────────────────
#
# La imagen base ya tiene Python 3.12 + chainlit + openai + httpx instalados.
# Este Dockerfile solo añade el código fuente (~30KB).
#
# Se reconstruye en cada commit a main → deploy en ~10 segundos.
#
# Build local:
#   docker build -t <acr>.azurecr.io/qrgen/frontend-app:latest frontend/
#   docker push <acr>.azurecr.io/qrgen/frontend-app:latest

ARG BASE_IMAGE=qrgen/frontend-base:latest
FROM ${BASE_IMAGE}

WORKDIR /app

# Solo el código — las dependencias ya están en la imagen base
COPY app.py .
COPY agent/ agent/
COPY client/ client/
COPY .chainlit/ .chainlit/
COPY public/ public/

EXPOSE 8000

# Las variables de entorno se inyectan desde Container Apps / docker-compose
CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
