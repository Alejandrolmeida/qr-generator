// =============================================================================
// Módulo: Azure Blob Storage (privado, con 3 contenedores)
// =============================================================================

param prefix string
param location string
param tags object

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

// ── Outputs ───────────────────────────────────────────────────────────────────
output storageAccountName string = storage.name
output storageAccountId   string = storage.id
// connectionString eliminado: el acceso se realiza via Managed Identity
// (Storage Blob Data Contributor asignado en main.bicep sobre la UAMI)
