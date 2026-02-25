// =============================================================================
// Lanyards AI Generator — Bicep principal
//
// Gestión de secretos / identidad:
//   - User-Assigned Managed Identity (UAMI) para todos los Container Apps
//   - UAMI tiene: AcrPull*, Storage Blob Data Contributor, KV Secrets User
//   - Key Vault almacena los 2 secretos de negocio; las CAs los leen en runtime
//   - GitHub solo guarda las 3 credenciales OIDC (ningún secreto de negocio)
//
//   * AcrPull se asigna con setup-github-secrets.sh (ACR es un recurso externo)
// =============================================================================

targetScope = 'resourceGroup'

// ── Parámetros ────────────────────────────────────────────────────────────────
@description('Entorno: dev | prod')
param environment string

@description('Región de Azure')
param location string = resourceGroup().location

@description('Nombre corto del proyecto (sin espacios, max 12 chars)')
@maxLength(12)
param projectName string = 'lanyards-aigen'

@description('Tags comunes para todos los recursos')
param tags object = {}

@description('Imagen Docker del backend app')
param backendImage string

@description('Imagen Docker del frontend app')
param frontendImage string

@description('Login server del ACR, p.ej. acrazurebrainschat.azurecr.io')
param acrLoginServer string = 'acrazurebrainschat.azurecr.io'

@description('Azure OpenAI endpoint (no secreto)')
param openAiEndpoint string

@description('Nombre del deployment GPT-4o')
param openAiDeployment string = 'gpt-4o'

// ── Variables ─────────────────────────────────────────────────────────────────
var prefix  = '${projectName}-${environment}'
var allTags = union(tags, {
  Environment: environment
  Project:     projectName
  ManagedBy:   'Bicep-IaC'
})

// ── User-Assigned Managed Identity ────────────────────────────────────────────
// Una sola UAMI compartida por backend y frontend.
// Roles asignados en este mismo template:
//   • Key Vault Secrets User (sobre el KV creado abajo)
//   • Storage Blob Data Contributor (sobre la storage account creada abajo)
// Rol AcrPull (sobre ACR externo) → asignado vía setup-github-secrets.sh
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name:     'id-${prefix}'
  location: location
  tags:     allTags
}

// ── Módulos ───────────────────────────────────────────────────────────────────

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    prefix:   prefix
    location: location
    tags:     allTags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    prefix:   prefix
    location: location
    tags:     allTags
  }
}

// Storage Blob Data Contributor = la UAMI puede leer/escribir blobs sin connection string
// 2a2b9908-6ea1-4ae2-8e65-a410df84e7d1 = Storage Blob Data Contributor
resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(storage.outputs.storageAccountId, uami.properties.principalId, '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  scope: resourceGroup()   // se aplica a nivel de RG (cubre la cuenta de storage)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
    principalId:      uami.properties.principalId
    principalType:    'ServicePrincipal'
  }
}

module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault'
  params: {
    prefix:   prefix
    location: location
    tags:     allTags
    // La UAMI lee secretos; el SP de deploy escribe (asignado via setup-github-secrets.sh)
    secretsUserPrincipalIds: [uami.properties.principalId]
  }
}

module containerApps 'modules/container-app.bicep' = {
  name: 'container-apps'
  params: {
    prefix:                          prefix
    location:                        location
    tags:                            allTags
    logAnalyticsWorkspaceId:         monitoring.outputs.logAnalyticsWorkspaceId
    logAnalyticsWorkspaceCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsWorkspaceKey:        monitoring.outputs.logAnalyticsKey
    uamiId:                          uami.id
    uamiClientId:                    uami.properties.clientId
    acrLoginServer:                  acrLoginServer
    backendImage:                    backendImage
    frontendImage:                   frontendImage
    storageAccountName:              storage.outputs.storageAccountName
    openAiEndpoint:                  openAiEndpoint
    openAiDeployment:                openAiDeployment
    keyVaultUri:                     keyVault.outputs.keyVaultUri
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output frontendUrl        string = containerApps.outputs.frontendUrl
output backendUrl         string = containerApps.outputs.backendUrl
output storageAccountName string = storage.outputs.storageAccountName
output keyVaultName       string = keyVault.outputs.keyVaultName
output uamiPrincipalId    string = uami.properties.principalId
