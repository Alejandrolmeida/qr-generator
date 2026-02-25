// =============================================================================
// Módulo: Azure Blob Storage (privado, con 3 contenedores)
// =============================================================================

param prefix string
param location string
param tags object

@description('Principal ID de la UAMI para asignar Storage Blob Data Contributor')
param uamiPrincipalId string

// Nombre debe ser único globalmente, sin guiones, max 24 chars
// take() sobre el string completo garantiza el límite independientemente del entorno (dev/prod/staging)
var storageAccountName = take('st${replace(prefix, '-', '')}${uniqueString(resourceGroup().id)}', 24)

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false       // todos los blobs son privados
    publicNetworkAccess: 'Enabled'     // acceso via SAS token desde Container Apps
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// ── Contenedores ──────────────────────────────────────────────────────────────
resource templatesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'templates'
  properties: {
    publicAccess: 'None'
  }
}

resource excelContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'excels'
  properties: {
    publicAccess: 'None'
  }
}

resource outputContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: 'output'
  properties: {
    publicAccess: 'None'
  }
}

// ── RBAC: Storage Blob Data Contributor → UAMI ──────────────────────────────
// Asignado aquí (dentro del módulo) para que el scope sea el propio storage account.
// Motivo: si se asigna en main.bicep con scope: resourceGroup() y alguien ya creó
// un assignment manual con UUID aleatorio para ese principal+rol+RG, ARM devuelve
// RoleAssignmentExists (HTTP 409). Scoping al storage evita ese conflicto.
// ba92f5b4-2d11-453d-a403-e96b0029c9fe = Storage Blob Data Contributor
var storageBlobContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name:  guid(storage.id, uamiPrincipalId, storageBlobContributorRoleId)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobContributorRoleId)
    principalId:      uamiPrincipalId
    principalType:    'ServicePrincipal'
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output storageAccountName string = storage.name
output storageAccountId   string = storage.id
// connectionString eliminado: el acceso se realiza via Managed Identity
// (Storage Blob Data Contributor asignado arriba sobre la UAMI)
