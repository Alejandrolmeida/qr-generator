#!/usr/bin/env bash
# =============================================================================
# setup-keyvault.sh — Configuración inicial del Azure Key Vault
#
# Ejecutar UNA VEZ antes del primer deploy o cuando roten los secretos.
# Requiere: az login, permisos Key Vault Secrets Officer sobre el AKV.
#
# Uso:
#   chmod +x scripts/setup-keyvault.sh
#   ./scripts/setup-keyvault.sh [dev|prod]
#
# Ejemplo:
#   ./scripts/setup-keyvault.sh dev
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-dev}"
PROJECT_NAME="lanyards-aigen"
KV_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
# Respetar límite de 24 chars de AKV
KV_NAME="kv-${KV_NAME:0:21}"

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

# ── Verificar que el AKV existe ───────────────────────────────────────────────
if ! az keyvault show --name "$KV_NAME" >/dev/null 2>&1; then
  echo "⚠️  El AKV '$KV_NAME' no existe."
  echo "   Ejecuta primero el workflow deploy.yml o crea el AKV manualmente:"
  echo "   az keyvault create --name '$KV_NAME' --resource-group '<RG>' \\"
  echo "     --location westeurope --enable-rbac-authorization true"
  exit 1
fi

echo "✅ Key Vault encontrado: $KV_NAME"
echo ""

# ─── SECRETOS DE NEGOCIO ──────────────────────────────────────────────────────
#
# Estos son los 2 únicos secretos que deben almacenarse en AKV.
# Las Container Apps los leen en runtime via Managed Identity (UAMI).
# El pipeline de GitHub los sincroniza automáticamente desde GitHub Secrets.
#
# Puedes usarlo también para rotar manualmente sin re-deployar.

# ── 1. Azure OpenAI API Key ───────────────────────────────────────────────────
echo "─── [1/2] lanyards-openai-api-key ──────────────────────────────"
EXISTING=$(az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name "lanyards-openai-api-key" \
  --query "value" -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING" ]; then
  read -rp "  ⚠️  Ya existe. ¿Sobreescribir? [s/N]: " CONFIRM
  [[ ! "$CONFIRM" =~ ^[sS]$ ]] && echo "  ↳ Omitido" || {
    read -rsp "  Nuevo valor de AZURE_OPENAI_API_KEY: " OAI_KEY; echo ""
    az keyvault secret set \
      --vault-name "$KV_NAME" \
      --name "lanyards-openai-api-key" \
      --value "$OAI_KEY" --output none
    echo "  ✅ Actualizado"
  }
else
  read -rsp "  Valor de AZURE_OPENAI_API_KEY: " OAI_KEY; echo ""
  az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "lanyards-openai-api-key" \
    --value "$OAI_KEY" --output none
  echo "  ✅ Guardado"
fi

# ── 2. Chainlit Auth Secret ───────────────────────────────────────────────────
echo ""
echo "─── [2/2] lanyards-chainlit-auth-secret ────────────────────────"
EXISTING=$(az keyvault secret show \
  --vault-name "$KV_NAME" \
  --name "lanyards-chainlit-auth-secret" \
  --query "value" -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING" ]; then
  read -rp "  ⚠️  Ya existe. ¿Sobreescribir? [s/N]: " CONFIRM
  [[ ! "$CONFIRM" =~ ^[sS]$ ]] && echo "  ↳ Omitido" || {
    # Generar automáticamente si el usuario no introduce nada
    echo "  (deja en blanco para autogenerar con openssl)"
    read -rsp "  Nuevo CHAINLIT_AUTH_SECRET: " CL_SEC; echo ""
    if [ -z "$CL_SEC" ]; then
      CL_SEC=$(openssl rand -hex 32)
      echo "  🎲 Autogenerado: ${CL_SEC:0:8}…"
    fi
    az keyvault secret set \
      --vault-name "$KV_NAME" \
      --name "lanyards-chainlit-auth-secret" \
      --value "$CL_SEC" --output none
    echo "  ✅ Actualizado"
  }
else
  echo "  (deja en blanco para autogenerar con openssl)"
  read -rsp "  Valor de CHAINLIT_AUTH_SECRET: " CL_SEC; echo ""
  if [ -z "$CL_SEC" ]; then
    CL_SEC=$(openssl rand -hex 32)
    echo "  🎲 Autogenerado: ${CL_SEC:0:8}…"
  fi
  az keyvault secret set \
    --vault-name "$KV_NAME" \
    --name "lanyards-chainlit-auth-secret" \
    --value "$CL_SEC" --output none
  echo "  ✅ Guardado"
fi

# ── Verificación final ────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────────────────────────"
echo "✅ Secretos en AKV '$KV_NAME':"
az keyvault secret list \
  --vault-name "$KV_NAME" \
  --query "[].{Nombre:name, Actualizado:attributes.updated}" \
  -o table

echo ""
echo "ℹ️  Recuerda también actualizar los GitHub Secrets con los mismos valores:"
echo "   AZURE_OPENAI_API_KEY"
echo "   CHAINLIT_AUTH_SECRET"
echo ""
echo "   Los GitHub Secrets se sincronizan automáticamente a AKV en cada deploy."
echo ""
