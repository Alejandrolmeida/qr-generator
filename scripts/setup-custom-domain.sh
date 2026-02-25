#!/usr/bin/env bash
# =============================================================================
# setup-custom-domain.sh
# Configura dominio personalizado + certificado TLS gestionado en Container Apps.
# Los registros DNS en Cloudflare se crean/actualizan AUTOMÁTICAMENTE
# usando las credenciales almacenadas en Azure Key Vault.
#
# Uso:
#   bash scripts/setup-custom-domain.sh [dominio] [app] [rg] [akv-cloudflare]
#
# Ejemplo:
#   bash scripts/setup-custom-domain.sh lanyard.azurebrains.com \
#        ca-lanyards-aigen-dev-frontend rg-lanyards-aigen kv-azrbrnsblog
# =============================================================================
set -euo pipefail

HOSTNAME="${1:-lanyard.azurebrains.com}"
APP_NAME="${2:-ca-lanyards-aigen-dev-frontend}"
RG="${3:-rg-lanyards-aigen}"
CF_AKV="${4:-kv-azrbrnsblog}"            # AKV con secretos de Cloudflare

# ── Colores ───────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RED="\033[0;31m"; CYAN="\033[0;36m"; NC="\033[0m"
info()    { echo -e "${GREEN}✅ $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${NC}"; }
step()    { echo -e "\n${CYAN}─── $* ───────────────────────────────────────${NC}"; }
divider() { echo -e "\n${YELLOW}════════════════════════════════════════════════${NC}"; }

divider
echo "  Dominio personalizado — Lanyards AI Generator"
echo ""
echo "  Hostname   : $HOSTNAME"
echo "  App        : $APP_NAME"
echo "  RG         : $RG"
echo "  CF AKV     : $CF_AKV"
divider

# ── 1. Datos del Container App ────────────────────────────────────────────────
step "1/6 Recopilando datos del Container App"

APP_FQDN=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

VERIFICATION_ID=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query "properties.customDomainVerificationId" -o tsv)

ENV_NAME=$(az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$RG" \
  --query "properties.managedEnvironmentId" -o tsv | awk -F'/' '{print $NF}')

STATIC_IP=$(az containerapp env show \
  --name "$ENV_NAME" \
  --resource-group "$RG" \
  --query "properties.staticIp" -o tsv)

info "App FQDN         : $APP_FQDN"
info "Static IP        : $STATIC_IP"
info "Verification ID  : $VERIFICATION_ID"

SUBDOMAIN="${HOSTNAME%%.*}"                # p.ej. "lanyard"
PARENT_DOMAIN="${HOSTNAME#*.}"             # p.ej. "azurebrains.com"
CNAME_NAME="${SUBDOMAIN}"                  # registro CNAME
TXT_NAME="asuid.${SUBDOMAIN}"              # registro TXT verificación

# ── 2. Credenciales Cloudflare desde AKV ─────────────────────────────────────
step "2/6 Leyendo credenciales de Cloudflare desde AKV '$CF_AKV'"

CF_TOKEN=$(az keyvault secret show \
  --vault-name "$CF_AKV" --name "cloudflare-api-token" \
  --query "value" -o tsv)

CF_ZONE_ID=$(az keyvault secret show \
  --vault-name "$CF_AKV" --name "cloudflare-zone-id" \
  --query "value" -o tsv)

# Verificar que el token es válido
CF_TOKEN_STATUS=$(curl -s "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print(r.get('success','false'))")

if [[ "$CF_TOKEN_STATUS" != "True" && "$CF_TOKEN_STATUS" != "true" ]]; then
  echo ""
  echo -e "${RED}❌ El secreto 'cloudflare-api-token' en AKV '$CF_AKV' es inválido o ha expirado.${NC}"
  echo ""
  echo "  Necesitas crear un nuevo token en Cloudflare con permiso DNS:Edit:"
  echo "    1. https://dash.cloudflare.com/profile/api-tokens"
  echo "    2. 'Create Token' → plantilla 'Edit zone DNS'"
  echo "    3. Zone Resources: Include → Specific zone → azurebrains.com"
  echo "    4. Guarda el token y actualiza el secreto AKV:"
  echo ""
  echo "       az keyvault secret set --vault-name $CF_AKV \\"
  echo "         --name cloudflare-api-token --value '<NUEVO_TOKEN>'"
  echo ""
  exit 1
fi
info "Token Cloudflare verificado y activo"

# ── 3. Crear/actualizar registros DNS en Cloudflare ──────────────────────────
step "3/6 Configurando registros DNS en Cloudflare (zona: $PARENT_DOMAIN)"

# Función upsert: crea el registro si no existe, lo actualiza si ya existe.
cf_upsert() {
  local type="$1" name="$2" content="$3" proxied="$4"
  local fqdn="${name}.${PARENT_DOMAIN}"

  local existing_id
  existing_id=$(curl -s -X GET \
    "https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records?type=${type}&name=${fqdn}" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['result'][0]['id'] if r.get('result') else '')" 2>/dev/null || echo "")

  local payload
  payload=$(python3 -c "import json; print(json.dumps({
    'type':    '${type}',
    'name':    '${fqdn}',
    'content': '${content}',
    'ttl':     1,
    'proxied': True if '${proxied}' == 'true' else False
  }))")

  local method url
  if [[ -n "$existing_id" ]]; then
    method="PUT"
    url="https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records/${existing_id}"
  else
    method="POST"
    url="https://api.cloudflare.com/client/v4/zones/${CF_ZONE_ID}/dns_records"
  fi

  local result success
  result=$(curl -s -X "$method" "$url" \
    -H "Authorization: Bearer ${CF_TOKEN}" \
    -H "Content-Type: application/json" \
    --data "$payload")
  success=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success','false'))")

  if [[ "$success" == "True" || "$success" == "true" ]]; then
    [[ "$method" == "PUT" ]] \
      && info "Actualizado ${type} ${fqdn}" \
      || info "Creado    ${type} ${fqdn}"
  else
    warn "CF API error en ${type} ${fqdn}: $(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('errors','?'))")"
  fi
}

# CNAME con proxy DESACTIVADO (Azure necesita resolver directamente para el cert)
cf_upsert "CNAME" "$CNAME_NAME" "$APP_FQDN"         "false"
# TXT de verificación de propiedad del dominio
cf_upsert "TXT"   "$TXT_NAME"   "$VERIFICATION_ID"  "false"

# ── 4. Verificar propagación DNS ─────────────────────────────────────────────
step "4/6 Esperando propagación DNS"

CNAME_VAL=""; TXT_VAL=""
for i in $(seq 1 18); do
  CNAME_VAL=$(dig +short CNAME "${CNAME_NAME}.${PARENT_DOMAIN}" 2>/dev/null | head -1 || echo "")
  TXT_VAL=$(dig +short TXT   "${TXT_NAME}.${PARENT_DOMAIN}"   2>/dev/null | tr -d '"' | head -1 || echo "")
  if [[ -n "$CNAME_VAL" && -n "$TXT_VAL" ]]; then
    info "CNAME propagado → $CNAME_VAL"
    info "TXT   propagado → ${TXT_VAL:0:40}..."
    break
  fi
  echo "  Esperando propagación... ($i/18) — CNAME: ${CNAME_VAL:-pendiente} | TXT: ${TXT_VAL:-pendiente}"
  sleep 10
done

if [[ -z "$CNAME_VAL" || -z "$TXT_VAL" ]]; then
  warn "DNS aún no propagado tras 3 min. El binding puede fallar; si ocurre, espera y re-ejecuta desde el paso 5."
fi

# ── 5. Añadir hostname al Container App ──────────────────────────────────────
step "5/6 Registrando hostname en el Container App"

az containerapp hostname add \
  --hostname "$HOSTNAME" \
  --name     "$APP_NAME" \
  --resource-group "$RG" \
  --output none 2>&1 || warn "Hostname posiblemente ya registrado, continuando..."
info "Hostname '$HOSTNAME' registrado"

# ── 6. Certificado TLS gestionado Azure ──────────────────────────────────────
step "6/6 Emitiendo certificado TLS gestionado por Azure (gratuito, auto-renovable)"

CERT_NAME="managed-$(echo $HOSTNAME | tr '.' '-')"

# Paso 6a: Crear el managed certificate en el entorno
echo "  Creando managed certificate en el entorno '$ENV_NAME'..."
az containerapp env certificate create \
  --name              "$ENV_NAME" \
  --resource-group    "$RG" \
  --hostname          "$HOSTNAME" \
  --validation-method CNAME \
  --certificate-name  "$CERT_NAME" \
  --output none 2>&1 || warn "Certificate posiblemente ya existe, continuando..."

info "Managed certificate '$CERT_NAME' iniciado — Azure validará el CNAME (3-10 min)"

# Esperar a que el cert pase a estado Approved antes del bind
echo ""
echo "  Esperando que el certificado sea emitido..."
for i in $(seq 1 20); do
  CERT_STATUS=$(az containerapp env certificate list \
    --name "$ENV_NAME" --resource-group "$RG" \
    --query "[?name=='$CERT_NAME'].properties.provisioningState" -o tsv 2>/dev/null || echo "Unknown")
  echo "  [$i/20] Estado del certificado: ${CERT_STATUS:-Pending}"
  [[ "$CERT_STATUS" == "Succeeded" || "$CERT_STATUS" == "Approved" ]] && break
  sleep 30
done

# Paso 6b: Bind del cert al Container App
echo "  Vinculando certificado al app..."
az containerapp hostname bind \
  --hostname       "$HOSTNAME" \
  --name           "$APP_NAME" \
  --resource-group "$RG" \
  --certificate    "$CERT_NAME" \
  --environment    "$ENV_NAME" \
  --output none

info "Certificado TLS vinculado al app '$APP_NAME'"

echo ""
echo "  Esperando validación del certificado..."
for i in $(seq 1 20); do
  CERT_STATUS=$(az containerapp show \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --query "properties.configuration.ingress.customDomains[?name=='$HOSTNAME'].certificateBindingStatus" \
    -o tsv 2>/dev/null || echo "Unknown")

  echo "  [$i/20] Estado del certificado: ${CERT_STATUS:-Pending}"
  [[ "$CERT_STATUS" == "Approved" ]] && break
  sleep 30
done

# ── Resultado final ───────────────────────────────────────────────────────────
divider
echo ""
info "¡Dominio personalizado configurado!"
echo ""
echo -e "  ${CYAN}🌐 URL de acceso: https://$HOSTNAME${NC}"
echo ""
echo "  ℹ️  Si el cert sigue en Pending, espera ~5 min y comprueba:"
echo "     az containerapp hostname list --name $APP_NAME --resource-group $RG -o table"
echo ""
echo "  ℹ️  Proxy Cloudflare: puedes activarlo (nube naranja) una vez el cert"
echo "     esté 'Approved' — Cloudflare WAF/CDN funcionará como frontal."
echo ""
divider
