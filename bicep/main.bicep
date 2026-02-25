// =============================================================================
// QR Accreditation — Bicep principal
// Orquesta todos los módulos de infraestructura.
// =============================================================================

targetScope = 'resourceGroup'

// ── Parámetros ────────────────────────────────────────────────────────────────
@description('Entorno: dev | prod')
param environment string

@description('Región de Azure')
param location string = resourceGroup().location

@description('Nombre corto del proyecto (sin espacios, max 8 chars)')
@maxLength(8)
param projectName string = 'qrgen'

@description('Tags comunes para todos los recursos')
param tags object = {}

@description('SKU del Container Apps environment (Consumption o Dedicated)')
param containerAppsSkuName string = 'Consumption'

@description('Imagen Docker del backend app')
param backendImage string

@description('Imagen Docker del frontend app')
param frontendImage string

@description('Nombre del ACR para autenticarse')
param acrLoginServer string = 'acrazurebrainschat.azurecr.io'

@description('Usuario ACR (para Container Apps pull)')
@secure()
param acrUsername string

@description('Password ACR')
@secure()
param acrPassword string

@description('Azure OpenAI endpoint')
param openAiEndpoint string

@description('Azure OpenAI API key')
@secure()
param openAiApiKey string

@description('Nombre del deployment GPT-4o')
param openAiDeployment string = 'gpt-4o'

@description('Secreto de autenticación de Chainlit')
@secure()
param chainlitAuthSecret string

// ── Variables ─────────────────────────────────────────────────────────────────
var prefix = '${projectName}-${environment}'
var allTags = union(tags, {
  Environment: environment
  Project: projectName
  ManagedBy: 'Bicep-IaC'
})

// ── Módulos ───────────────────────────────────────────────────────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    prefix: prefix
    location: location
    tags: allTags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    prefix: prefix
    location: location
    tags: allTags
  }
}

module containerApps 'modules/container-app.bicep' = {
  name: 'container-apps'
  params: {
    prefix: prefix
    location: location
    tags: allTags
    logAnalyticsWorkspaceId: monitoring.outputs.logAnalyticsWorkspaceId
    logAnalyticsWorkspaceCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsWorkspaceKey: monitoring.outputs.logAnalyticsKey
    acrLoginServer: acrLoginServer
    acrUsername: acrUsername
    acrPassword: acrPassword
    backendImage: backendImage
    frontendImage: frontendImage
    storageConnectionString: storage.outputs.connectionString
    openAiEndpoint: openAiEndpoint
    openAiApiKey: openAiApiKey
    openAiDeployment: openAiDeployment
    chainlitAuthSecret: chainlitAuthSecret
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output frontendUrl string = containerApps.outputs.frontendUrl
output backendUrl string = containerApps.outputs.backendUrl
output storageAccountName string = storage.outputs.storageAccountName
