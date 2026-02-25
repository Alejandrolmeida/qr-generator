# ─── Imagen app frontend: código sobre la imagen base ────────────────────────
#
# La imagen base (qrgen/frontend-base) ya tiene chainlit, openai, httpx, etc.
# Este Dockerfile solo añade el código fuente (~30KB).
#
# Se reconstruye en cada commit a main → deploy en ~10 segundos.
#
# Build local:
#   docker build \
#     --build-arg BASE_IMAGE=acrazurebrainschat.azurecr.io/qrgen/frontend-base:latest \
#     -t acrazurebrainschat.azurecr.io/qrgen/frontend-app:latest \
#     frontend/

ARG BASE_IMAGE=acrazurebrainschat.azurecr.io/qrgen/frontend-base:latest
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
