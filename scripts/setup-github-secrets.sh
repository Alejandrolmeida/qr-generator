#!/usr/bin/env bash
# =============================================================================
# setup-github-secrets.sh — Configuración inicial de GitHub Secrets + OIDC
#
# Ejecutar UNA SOLA VEZ para preparar el repositorio para CI/CD.
# Prerrequisitos:
#   • az login (con permisos de Contributor en la suscripción + Graph)
#   • gh auth login (GitHub CLI autenticado)
#   • github.com/Alejandrolmeida/qr-generator existente
#
# Uso:
#   chmod +x scripts/setup-github-secrets.sh
#   ./scripts/setup-github-secrets.sh
# =============================================================================

set -euo pipefail

# ─── CONFIGURACIÓN — ajusta estos valores ─────────────────────────────────────
GITHUB_ORG="Alejandrolmeida"
GITHUB_REPO="qr-generator"
SP_NAME="sp-lanyards-github-oidc"
AZURE_LOCATION="westeurope"
PROJECT_NAME="lanyards-aigen"
# Resource Group y ACR — ajusta según tu entorno
AZURE_RG="rg-${PROJECT_NAME}"
ACR_NAME="acrazurebrainschat"
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Lanyards AI Generator — Setup GitHub + OIDC Azure        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  GitHub repo : $GITHUB_ORG/$GITHUB_REPO"
echo "  SP name     : $SP_NAME"
echo "  ACR         : $ACR_NAME"
echo ""

# ── Verificar herramientas ────────────────────────────────────────────────────
for cmd in az gh jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "❌ '$cmd' no encontrado. Instálalo antes de continuar."
    exit 1
  fi
done

if ! az account show >/dev/null 2>&1; then
  echo "❌ No autenticado en Azure. Ejecuta: az login"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "❌ No autenticado en GitHub. Ejecuta: gh auth login"
  exit 1
fi

SUBSCRIPTION_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo "  Suscripción : $SUBSCRIPTION_ID"
echo "  Tenant      : $TENANT_ID"
echo ""

# ── 1. Crear o recuperar App Registration ─────────────────────────────────────
echo "─── [1/6] App Registration ──────────────────────────────────────"
EXISTING_APP=$(az ad app list \
  --display-name "$SP_NAME" \
  --query "[0].appId" -o tsv 2>/dev/null || echo "")

if [ -n "$EXISTING_APP" ]; then
  echo "  ✅ App Registration ya existe: $EXISTING_APP"
  CLIENT_ID="$EXISTING_APP"
else
  CLIENT_ID=$(az ad app create \
    --display-name "$SP_NAME" \
    --query appId -o tsv)
  echo "  ✅ App Registration creada: $CLIENT_ID"
fi

# ── 2. Crear o recuperar Service Principal ────────────────────────────────────
echo ""
echo "─── [2/6] Service Principal ─────────────────────────────────────"
SP_OBJECT_ID=$(az ad sp show --id "$CLIENT_ID" --query id -o tsv 2>/dev/null || echo "")

if [ -n "$SP_OBJECT_ID" ]; then
  echo "  ✅ Service Principal ya existe: $SP_OBJECT_ID"
else
  SP_OBJECT_ID=$(az ad sp create --id "$CLIENT_ID" --query id -o tsv)
  echo "  ✅ Service Principal creado: $SP_OBJECT_ID"
fi

# ── 3. Configurar Federated Credentials (OIDC) ───────────────────────────────
echo ""
echo "─── [3/6] Federated Credentials OIDC ───────────────────────────"

federate() {
  local CRED_NAME="$1"
  local SUBJECT="$2"
  EXISTING=$(az ad app federated-credential list \
    --id "$CLIENT_ID" \
    --query "[?name=='$CRED_NAME'].name" -o tsv 2>/dev/null || echo "")

  if [ -n "$EXISTING" ]; then
    echo "  ↳ $CRED_NAME — ya existe"
  else
    az ad app federated-credential create \
      --id "$CLIENT_ID" \
      --parameters "{
        \"name\": \"$CRED_NAME\",
        \"issuer\": \"https://token.actions.githubusercontent.com\",
        \"subject\": \"$SUBJECT\",
        \"audiences\": [\"api://AzureADTokenExchange\"]
      }" --output none
    echo "  ✅ $CRED_NAME"
  fi
}

# Rama main
federate "github-main" "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main"
# workflow_dispatch (entorno dev y prod)
federate "github-env-dev"  "repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:dev"
federate "github-env-prod" "repo:${GITHUB_ORG}/${GITHUB_REPO}:environment:prod"

# ── 4. Asignar roles Azure ───────────────────────────────────────────────────
echo ""
echo "─── [4/6] Roles Azure ───────────────────────────────────────────"

assign_role() {
  local ROLE="$1"
  local SCOPE="$2"
  local DESC="$3"
  EXISTING=$(az role assignment list \
    --assignee "$SP_OBJECT_ID" --role "$ROLE" --scope "$SCOPE" \
    --query "[0].id" -o tsv 2>/dev/null || echo "")
  if [ -n "$EXISTING" ]; then
    echo "  ↳ $DESC — ya asignado"
  else
    az role assignment create \
      --assignee-object-id "$SP_OBJECT_ID" \
      --assignee-principal-type ServicePrincipal \
      --role "$ROLE" --scope "$SCOPE" --output none
    echo "  ✅ $DESC"
  fi
}

SUB_SCOPE="/subscriptions/${SUBSCRIPTION_ID}"

# Contributor sobre la suscripción (para crear RGs y recursos)
assign_role "Contributor" "$SUB_SCOPE" "Contributor / Suscripción"

# AcrPush sobre el ACR (para subir imágenes en build-push.yml)
ACR_ID=$(az acr show --name "$ACR_NAME" --query id -o tsv 2>/dev/null || echo "")
if [ -n "$ACR_ID" ]; then
  assign_role "AcrPush" "$ACR_ID" "AcrPush / $ACR_NAME"
else
  echo "  ⚠️  ACR '$ACR_NAME' no encontrado. Asigna AcrPush manualmente cuando esté disponible."
fi

# Key Vault Secrets Officer a nivel de suscripción
# (permite escribir secretos en cualquier AKV de la sub, incluyendo el que crea Bicep)
assign_role "Key Vault Secrets Officer" "$SUB_SCOPE" "KV Secrets Officer / Suscripción"

# ── 5. Subir GitHub Secrets (OIDC) ────────────────────────────────────────────
echo ""
echo "─── [5/6] GitHub Secrets ────────────────────────────────────────"
REPO_PATH="${GITHUB_ORG}/${GITHUB_REPO}"

set_gh_secret() {
  local NAME="$1"
  local VALUE="$2"
  printf '%s' "$VALUE" | gh secret set "$NAME" \
    --repo "$REPO_PATH" \
    --body - 2>/dev/null
  echo "  ✅ $NAME"
}

set_gh_secret "AZURE_CLIENT_ID"       "$CLIENT_ID"
set_gh_secret "AZURE_TENANT_ID"       "$TENANT_ID"
set_gh_secret "AZURE_SUBSCRIPTION_ID" "$SUBSCRIPTION_ID"

# Secretos de negocio — se piden interactivamente
echo ""
echo "  Introduce los secretos de negocio (se guardan en GitHub Secrets"
echo "  y se sincronizan a AKV en cada deploy):"
echo ""
read -rsp "  AZURE_OPENAI_API_KEY: " OAI_KEY; echo ""
set_gh_secret "AZURE_OPENAI_API_KEY" "$OAI_KEY"

echo "  (deja en blanco para autogenerar CHAINLIT_AUTH_SECRET)"
read -rsp "  CHAINLIT_AUTH_SECRET: " CL_SEC; echo ""
if [ -z "$CL_SEC" ]; then
  CL_SEC=$(openssl rand -hex 32)
  echo "  🎲 Autogenerado: ${CL_SEC:0:8}…"
fi
set_gh_secret "CHAINLIT_AUTH_SECRET" "$CL_SEC"

# ── 6. Subir GitHub Variables (no sensibles) ──────────────────────────────────
echo ""
echo "─── [6/6] GitHub Variables ──────────────────────────────────────"

set_gh_var() {
  local NAME="$1"
  local VALUE="$2"
  gh variable set "$NAME" \
    --repo "$REPO_PATH" \
    --body "$VALUE" 2>/dev/null
  echo "  ✅ $NAME = $VALUE"
}

set_gh_var "AZURE_RG"  "$AZURE_RG"
set_gh_var "ACR_NAME"  "$ACR_NAME"

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ Setup completado"
echo ""
echo "  GitHub Secrets configurados:"
echo "    AZURE_CLIENT_ID"
echo "    AZURE_TENANT_ID"
echo "    AZURE_SUBSCRIPTION_ID"
echo "    AZURE_OPENAI_API_KEY"
echo "    CHAINLIT_AUTH_SECRET"
echo ""
echo "  GitHub Variables configuradas:"
echo "    AZURE_RG  = $AZURE_RG"
echo "    ACR_NAME  = $ACR_NAME"
echo ""
echo "  Próximo paso: lanza el workflow 'Build & Push' para construir"
echo "  las imágenes y luego 'Deploy' para desplegar la infraestructura."
echo ""
echo "  El workflow deploy.yml sincronizará automáticamente los secretos"
echo "  de GitHub a AKV y las Container Apps los usarán vía UAMI."
echo ""
