// =============================================================================
// Módulo: Azure OpenAI
//
// Crea el recurso Cognitive Services (kind=OpenAI) y el deployment GPT-4o
// propiedad exclusiva del proyecto Lanyards AI Generator.
//
// Auth: Cognitive Services OpenAI User asignado a la UAMI del proyecto.
//       La aplicación se autentica via DefaultAzureCredential (keyless).
//       La API key solo se usa en desarrollo local (dev-up.sh la lee del AKV).
// =============================================================================

param prefix   string
param location string
param tags     object

@description('Principal ID de la UAMI que necesita "Cognitive Services OpenAI User"')
param uamiPrincipalId string

@description('Nombre del deployment del modelo')
param deploymentName string = 'gpt-4o'

@description('SKU del deployment (GlobalStandard, DataZoneStandard, Standard)')
param deploymentSku string = 'GlobalStandard'

@description('Versión del modelo')
param modelVersion string = '2024-08-06'

@description('Capacidad en miles de tokens por minuto (TPM)')
param capacityKtpm int = 10

// ── Recurso Azure OpenAI ──────────────────────────────────────────────────────
resource oai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name:     'oai-${prefix}'
  location: location
  tags:     tags
  kind:     'OpenAI'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName:  'oai-${prefix}'   // obligatorio para Entra ID auth
    publicNetworkAccess:  'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false   // false = permite API key en local dev
  }
}

// ── Deployment GPT-4o ─────────────────────────────────────────────────────────
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: oai
  name:   deploymentName
  sku: {
    name:     deploymentSku
    capacity: capacityKtpm
  }
  properties: {
    model: {
      format:  'OpenAI'
      name:    'gpt-4o'
      version: modelVersion
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// ── RBAC: Cognitive Services OpenAI User → UAMI ───────────────────────────────
// 5e0bd9bd-7b93-4f28-af87-19fc36ad61bd = Cognitive Services OpenAI User
var oaiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource roleOaiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(oai.id, uamiPrincipalId, oaiUserRoleId)
  scope: oai
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', oaiUserRoleId)
    principalId:      uamiPrincipalId
    principalType:    'ServicePrincipal'
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output endpoint       string = oai.properties.endpoint
output resourceId     string = oai.id
output deploymentName string = deployment.name
output accountName    string = oai.name
