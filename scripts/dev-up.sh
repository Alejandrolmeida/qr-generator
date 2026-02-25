#!/usr/bin/env bash
# =============================================================================
# dev-up.sh — Levantar el entorno de desarrollo leyendo secretos desde AKV
#
# NUNCA se usa .env con secretos. Todos los valores se obtienen en runtime
# desde Azure Key Vault y se inyectan en un fichero temporal fuera del repo.
#
# Prerrequisitos:
#   • az login  (tu cuenta debe tener Key Vault Secrets User sobre el AKV)
#   • docker (en ejecución)
#
# Uso:
#   chmod +x scripts/dev-up.sh
#   ./scripts/dev-up.sh                  # levanta en primer plano
#   ./scripts/dev-up.sh -d               # levanta en segundo plano (detached)
#   ./scripts/dev-up.sh --build          # rebuild de imágenes
#   ./scripts/dev-up.sh down             # apaga el stack
#
# Puedes pasar cualquier argumento extra de docker compose:
#   ./scripts/dev-up.sh up --build -d
# =============================================================================

set -euo pipefail

PROJECT_NAME="lanyards-aigen"
ENVIRONMENT="${LANYARDS_ENV:-dev}"
KV_NAME="${AKV_NAME:-kv-${PROJECT_NAME:0:18}-${ENVIRONMENT}}"

# Truncar al límite de 24 chars de AKV
KV_NAME="${KV_NAME:0:24}"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Lanyards — Dev Up (secretos desde AKV)                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Key Vault : $KV_NAME"
echo "  Entorno   : $ENVIRONMENT"
echo ""

# ── Verificar dependencias ────────────────────────────────────────────────────
for cmd in az docker; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ '$cmd' no encontrado. Instálalo antes de continuar."
    exit 1
  fi
done

if ! az account show >/dev/null 2>&1; then
  echo "❌ No estás autenticado en Azure. Ejecuta: az login"
  exit 1
fi

if ! az keyvault show --name "$KV_NAME" >/dev/null 2>&1; then
  echo "❌ Key Vault '$KV_NAME' no encontrado o sin permisos."
  echo "   Verifica que existe y que tu cuenta tiene 'Key Vault Secrets User'."
  echo "   Si el nombre no es correcto, exporta: AKV_NAME=<nombre-real>"
  exit 1
fi

# ── Crear fichero temporal fuera del repositorio ──────────────────────────────
# Se escribe en /tmp (nunca en el directorio del repo) y se borra al salir.
TMPENV=$(mktemp /tmp/qrgen-dev-XXXXXX.env)
chmod 600 "$TMPENV"

cleanup() {
  rm -f "$TMPENV"
  echo ""
  echo "🗑️  Fichero temporal de secretos eliminado."
}
trap cleanup EXIT INT TERM

# ── Función: leer secreto de AKV ─────────────────────────────────────────────
akv_get() {
  local SECRET_NAME="$1"
  local VAR_NAME="$2"
  local DEFAULT="${3:-}"

  VALUE=$(az keyvault secret show \
    --vault-name "$KV_NAME" \
    --name "$SECRET_NAME" \
    --query "value" -o tsv 2>/dev/null || echo "")

  if [ -z "$VALUE" ]; then
    if [ -n "$DEFAULT" ]; then
      VALUE="$DEFAULT"
      echo "  ⚠️  $SECRET_NAME no encontrado → usando valor por defecto"
    else
      echo "  ❌ $SECRET_NAME no encontrado en AKV '$KV_NAME'"
      echo "     Ejecúta scripts/setup-keyvault.sh $ENVIRONMENT para crearlo"
      exit 1
    fi
  else
    echo "  ✅ $SECRET_NAME"
  fi

  # Escribir en el fichero temporal (nunca en pantalla)
  printf '%s=%s\n' "$VAR_NAME" "$VALUE" >> "$TMPENV"
}

echo "⬇️  Cargando secretos desde AKV..."
echo ""

# ── Secretos y configuración de Azure OpenAI ─────────────────────────────────
akv_get "lanyards-openai-endpoint"    "AZURE_OPENAI_ENDPOINT"
akv_get "lanyards-openai-api-key"     "AZURE_OPENAI_API_KEY"
akv_get "lanyards-openai-deployment"  "AZURE_OPENAI_DEPLOYMENT_GPT4O"  "gpt-4o"
akv_get "lanyards-openai-api-version" "AZURE_OPENAI_API_VERSION"       "2024-02-15-preview"

# ── Chainlit ──────────────────────────────────────────────────────────────────
akv_get "lanyards-chainlit-auth-secret" "CHAINLIT_AUTH_SECRET"

# ── Variables no sensibles (valores fijos de entorno local) ──────────────────
# Estas NO son secretos: son configuración de carpetas y modo de ejecución.
cat >> "$TMPENV" << 'EOF'
DEBUG=true
CORS_ORIGINS=["http://localhost:8000"]
FONTS_FOLDER=/app/fonts
OUTPUT_FOLDER=/tmp/qr-output
BACKEND_URL=http://backend:8080
AZURE_OPENAI_API_VERSION=2024-02-15-preview
EOF

echo ""
echo "✅ Secretos cargados en fichero temporal (fuera del repo)"
echo ""

# ── Lanzar docker compose ─────────────────────────────────────────────────────
# Si no se pasan argumentos, se hace "up" por defecto.
COMPOSE_ARGS=("$@")
if [ ${#COMPOSE_ARGS[@]} -eq 0 ]; then
  COMPOSE_ARGS=("up")
fi

echo "🐳 docker compose ${COMPOSE_ARGS[*]}"
echo "────────────────────────────────────────────────────────────────"
echo ""

docker compose \
  --env-file "$TMPENV" \
  "${COMPOSE_ARGS[@]}"
