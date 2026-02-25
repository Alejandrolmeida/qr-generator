#!/usr/bin/env bash
# =============================================================================
# setup-keyvault.sh — Configuración inicial de Azure Key Vault
#
# Almacena TODOS los secretos y parámetros en AKV.
# AKV es la única fuente de verdad: ni .env, ni GitHub Secrets de negocio,
# ni variables de entorno manuales en ningún momento.
#
# Prerrequisitos:
#   • az login con permisos Key Vault Secrets Officer sobre el AKV
#
# Uso:
#   chmod +x scripts/setup-keyvault.sh
#   ./scripts/setup-keyvault.sh [dev|prod]
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="lanyards-aigen"
# El AKV se desplegó sin sufijo de entorno; se puede sobreescribir con AKV_NAME
KV_NAME="${AKV_NAME:-kv-${PROJECT_NAME}}"
KV_NAME="${KV_NAME:0:24}"   # límite AKV

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Lanyards AI Generator — Setup Key Vault                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Entorno   : $ENVIRONMENT"
echo "  Key Vault : $KV_NAME"
echo ""

# ── Verificar az login ────────────────────────────────────────────────────────
if ! az account show >/dev/null 2>&1; then
  echo "❌ No estás autenticado en Azure. Ejecuta: az login"
  exit 1
fi

# ── Verificar / crear el AKV ──────────────────────────────────────────────────
if ! az keyvault show --name "$KV_NAME" >/dev/null 2>&1; then
  echo "⚠️  El AKV '$KV_NAME' no existe todavía."
  echo ""
  read -rp "  ¿Crear el AKV ahora? (necesitas el Resource Group) [s/N]: " CREATE_KV
  if [[ "$CREATE_KV" =~ ^[sS]$ ]]; then
    read -rp "  Resource Group: " AKV_RG
    read -rp "  Región [westeurope]: " AKV_LOCATION
    AKV_LOCATION="${AKV_LOCATION:-westeurope}"
    az keyvault create \
      --name "$KV_NAME" \
      --resource-group "$AKV_RG" \
      --location "$AKV_LOCATION" \
      --enable-rbac-authorization true \
      --retention-days 7 \
      --output none
    echo "  ✅ Key Vault creado: $KV_NAME"
  else
    echo "  Ejecuta primero el workflow deploy.yml o crea el AKV manualmente."
    exit 1
  fi
fi

echo "✅ Key Vault: $KV_NAME"
echo ""

# ── Función para guardar/actualizar un secreto ────────────────────────────────
# Nunca muestra el valor en pantalla (read -s) ni lo imprime en ningún log.
set_secret() {
  local NAME="$1"
  local PROMPT="$2"
  local DEFAULT="${3:-}"      # valor por defecto visible (no sensible)
  local AUTO_GEN="${4:-}"     # si "auto", genera con openssl si queda vacío

  EXISTING=$(az keyvault secret show \
    --vault-name "$KV_NAME" --name "$NAME" \
    --query "value" -o tsv 2>/dev/null || echo "")

  if [ -n "$EXISTING" ]; then
    read -rp "  ⚠️  '$NAME' ya existe. ¿Sobreescribir? [s/N]: " CONFIRM
    [[ ! "$CONFIRM" =~ ^[sS]$ ]] && { echo "  ↳ Omitido"; return; }
  fi

  if [ -n "$DEFAULT" ]; then
    read -rp "  $PROMPT [${DEFAULT}]: " VALUE
    VALUE="${VALUE:-$DEFAULT}"
  elif [ "$AUTO_GEN" = "auto" ]; then
    echo "  (deja en blanco para autogenerar con openssl)"
    read -rsp "  $PROMPT: " VALUE; echo ""
    if [ -z "$VALUE" ]; then
      VALUE=$(openssl rand -hex 32)
      echo "  🎲 Autogenerado"
    fi
  else
    read -rsp "  $PROMPT: " VALUE; echo ""
  fi

  if [ -z "$VALUE" ]; then
    echo "  ❌ Valor vacío — secreto no guardado."
    return
  fi

  az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "$NAME" \
    --value "$VALUE" \
    --output none
  echo "  ✅ $NAME"
}

# =============================================================================
# AZURE OPENAI  (endpoint y deployment se auto-detectan del recurso propio)
# =============================================================================
echo "─── Azure OpenAI ────────────────────────────────────────────────"
echo ""

# El recurso lo crea main.bicep: oai-lanyards-aigen-<env>
OAI_ACCOUNT="oai-${PROJECT_NAME}-${ENVIRONMENT}"

echo "  Buscando recurso Azure OpenAI: $OAI_ACCOUNT"
OAI_INFO=$(az cognitiveservices account show \
  --name "$OAI_ACCOUNT" \
  --resource-group "rg-${PROJECT_NAME}" \
  --query "{endpoint:properties.endpoint, id:id}" \
  -o json 2>/dev/null || echo "{}")

OAI_ENDPOINT=$(echo "$OAI_INFO" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('endpoint',''))" 2>/dev/null)
OAI_ID=$(echo "$OAI_INFO"       | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))"       2>/dev/null)

if [ -z "$OAI_ENDPOINT" ]; then
  echo ""
  echo "  ⚠️  Recurso '$OAI_ACCOUNT' no encontrado."
  echo "     Despliega primero la infraestructura:"
  echo "     az deployment group create \\"
  echo "       --resource-group rg-${PROJECT_NAME} \\"
  echo "       --template-file bicep/main.bicep \\"
  echo "       --parameters bicep/parameters/${ENVIRONMENT}.bicepparam"
  echo ""
  read -rp "  ¿Introducir endpoint manualmente? [s/N]: " MANUAL
  if [[ "$MANUAL" =~ ^[sS]$ ]]; then
    read -rp "  Endpoint: " OAI_ENDPOINT
  else
    echo "  ↳ Omitiendo secretos de OpenAI — ejecuta este script de nuevo tras el deploy."
    OAI_SKIP=true
  fi
fi

if [ "${OAI_SKIP:-false}" = "false" ]; then
  # Guardar endpoint (no es secreto pero lo centralizamos en AKV para dev-up.sh)
  az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "lanyards-openai-endpoint" \
    --value "$OAI_ENDPOINT" \
    --output none
  echo "  ✅ lanyards-openai-endpoint  ← $OAI_ENDPOINT"

  echo ""
  set_secret \
    "lanyards-openai-api-key" \
    "API Key  (solo para desarrollo local — producción usa UAMI keyless)"

  echo ""
  set_secret \
    "lanyards-openai-deployment" \
    "Nombre del deployment GPT-4o" \
    "gpt-4o"

  echo ""
  set_secret \
    "lanyards-openai-api-version" \
    "API version" \
    "2024-08-01-preview"
fi

echo ""

# =============================================================================
# CHAINLIT
# =============================================================================
echo "─── Chainlit ────────────────────────────────────────────────────"
echo ""

set_secret \
  "lanyards-chainlit-auth-secret" \
  "CHAINLIT_AUTH_SECRET" \
  "" \
  "auto"

echo ""

# ── Resumen ───────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════════"
echo "✅ Secretos en '$KV_NAME':"
echo ""
az keyvault secret list \
  --vault-name "$KV_NAME" \
  --query "sort_by([], &name)[].{Secreto:name, Actualizado:attributes.updated}" \
  -o table

echo ""
echo "  Levantar entorno de desarrollo:"
echo "    ./scripts/dev-up.sh"
echo ""
echo "  ⚠️  NUNCA copies estos valores a ficheros .env del repositorio."
echo ""
