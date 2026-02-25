// =============================================================================
// Módulo: Azure Key Vault (RBAC mode)
//
// Almacena los secretos de negocio de Lanyards AI Generator.
// El acceso se controla 100% via RBAC (enableRbacAuthorization = true).
//
// Secretos que debe contener el AKV (se crean con setup-keyvault.sh):
//   lanyards-openai-api-key        → clave API Azure OpenAI
//   lanyards-chainlit-auth-secret  → secreto Chainlit
// =============================================================================

param prefix string
param location string
param tags object

@description('Nombre exacto del KV. Si se indica sobreescribe el calculado (útil para reconciliar recursos ya existentes)')
param kvNameOverride string = ''

@description('Principal IDs que necesitan "Key Vault Secrets User" (solo lectura)')
param secretsUserPrincipalIds array = []

@description('Principal IDs que necesitan "Key Vault Secrets Officer" (lectura + escritura)')
param secretsOfficerPrincipalIds array = []

// KV name: max 24 chars, solo alfanumerico y guiones, debe empezar por letra
var kvName = empty(kvNameOverride) ? take('kv-${prefix}', 24) : kvNameOverride

// ── Key Vault ─────────────────────────────────────────────────────────────────
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name:   'standard'
    }
    tenantId:                  tenant().tenantId
    enableRbacAuthorization:   true   // sin access policies, todo via RBAC
    enableSoftDelete:          true
    softDeleteRetentionInDays: 7
    enabledForDeployment:      false
    enabledForTemplateDeployment: false  // no se necesita para Container Apps
    publicNetworkAccess: 'Enabled'       // Container Apps acceden desde internet interno Azure
    networkAcls: {
      defaultAction: 'Allow'
      bypass:        'AzureServices'
    }
  }
}

// ─── Roles ────────────────────────────────────────────────────────────────────

// 4633458b-17de-408a-b874-0445c86b69e6 = Key Vault Secrets User (lectura)
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

@batchSize(1)
resource roleSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (principalId, i) in secretsUserPrincipalIds: {
    // guid() garantiza unicidad; el índice 'i' diferencia asignaciones al mismo rol
    name:  guid(kv.id, principalId, kvSecretsUserRoleId, string(i))
    scope: kv
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
      principalId:      principalId
      principalType:    'ServicePrincipal'
    }
  }
]

// b86a8fe4-44ce-4948-aee5-eccb2c155cd7 = Key Vault Secrets Officer (leer + escribir)
var kvSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

@batchSize(1)
resource roleSecretsOfficer 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for (principalId, i) in secretsOfficerPrincipalIds: {
    name:  guid(kv.id, principalId, kvSecretsOfficerRoleId, string(i))
    scope: kv
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsOfficerRoleId)
      principalId:      principalId
      principalType:    'ServicePrincipal'
    }
  }
]

// ── Outputs ───────────────────────────────────────────────────────────────────
output keyVaultId   string = kv.id
output keyVaultName string = kv.name
output keyVaultUri  string = kv.properties.vaultUri
