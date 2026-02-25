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
KV_NAME="kv-${PROJECT_NAME:0:18}-${ENVIRONMENT}"
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
# AZURE OPENAI
# =============================================================================
echo "─── Azure OpenAI ────────────────────────────────────────────────"
echo ""
echo "  El endpoint y la API key se leen por dev-up.sh en local."
echo "  En producción (Container Apps) la auth es keyless via UAMI."
echo ""

set_secret \
  "lanyards-openai-endpoint" \
  "Endpoint (ej: https://mi-recurso.openai.azure.com/)"

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
  "2024-02-15-preview"

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
