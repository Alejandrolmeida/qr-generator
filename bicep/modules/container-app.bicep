// =============================================================================
// Módulo: Azure Container Apps Environment + Backend + Frontend
//
// Seguridad:
//   - UAMI (user-assigned managed identity) para pull ACR y lectura de AKV
//   - Azure OpenAI accedido SIN API key — UAMI tiene Cognitive Svcs OpenAI User
//   - Storage accedido via Managed Identity (Storage Blob Data Contributor)
//   - Sin credenciales ACR: el registro usa la identidad gestionada
//   - AKV solo contiene: lanyards-chainlit-auth-secret
// =============================================================================

param prefix   string
param location string
param tags     object

// ── Monitoring ────────────────────────────────────────────────────────────────

param logAnalyticsWorkspaceCustomerId string
@secure()
param logAnalyticsWorkspaceKey string

// ── Identidad gestionada (UAMI) ───────────────────────────────────────────────
@description('Resource ID completo de la User-Assigned Managed Identity')
param uamiId string

@description('Client ID de la UAMI (para Container Apps runtime)')
param uamiClientId string

// ── ACR ───────────────────────────────────────────────────────────────────────
param acrLoginServer string

// ── Imágenes ──────────────────────────────────────────────────────────────────
param backendImage  string
param frontendImage string

// ── Storage (Managed Identity — sin connection string) ────────────────────────
@description('Nombre de la cuenta de Azure Storage')
param storageAccountName string

// ── Azure OpenAI (config no secreta) ─────────────────────────────────────────
param openAiEndpoint   string
param openAiDeployment string

// ── Key Vault — URI base (termina en /) ──────────────────────────────────────
@description('URI del AKV, p.ej. https://kv-lanyards-aigen-dev.vault.azure.net/')
param keyVaultUri string

// ── Container Apps Environment ────────────────────────────────────────────────
// ── Container Apps Environment ────────────────────────────────────────────────
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${prefix}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceCustomerId
        sharedKey:  logAnalyticsWorkspaceKey
      }
    }
  }
}

// ── Backend Container App ─────────────────────────────────────────────────────
resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${prefix}-backend'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiId}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external:   false           // solo accesible desde el frontend (interno)
        targetPort: 8080
        transport:  'http'
      }
      // Pull de ACR via Managed Identity — sin usuario ni contraseña
      registries: [
        {
          server:   acrLoginServer
          identity: uamiId
        }
      ]
      // Sin secretos en el backend: OpenAI usa token MI, Storage usa MI
    }
    template: {
      containers: [
        {
          name:  'backend'
          image: backendImage
          resources: {
            cpu:    json('0.5')
            memory: '1Gi'
          }
          env: [
            // Storage via Managed Identity — sin connection string
            { name: 'AZURE_STORAGE_ACCOUNT_NAME',    value: storageAccountName }
            { name: 'AZURE_CLIENT_ID',               value: uamiClientId }
            // Azure OpenAI — keyless via DefaultAzureCredential (UAMI)
            { name: 'AZURE_OPENAI_ENDPOINT',         value: openAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT_GPT4O', value: openAiDeployment }
            { name: 'FONTS_FOLDER',                  value: '/app/fonts' }
            { name: 'OUTPUT_FOLDER',                 value: '/tmp/qr-output' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0    // escala a 0 cuando no hay uso (cost savings)
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '10' } }
          }
        ]
      }
    }
  }
}

// ── Frontend Container App ────────────────────────────────────────────────────
resource frontend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${prefix}-frontend'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uamiId}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external:      true           // accesible desde internet
        targetPort:    8000
        transport:     'http'
        allowInsecure: false
      }
      registries: [
        {
          server:   acrLoginServer
          identity: uamiId
        }
      ]
      // Solo 1 secreto AKV: Chainlit auth (OpenAI ya es keyless via MI)
      secrets: [
        {
          name:        'chainlit-auth-secret'
          keyVaultUrl: '${keyVaultUri}secrets/lanyards-chainlit-auth-secret'
          identity:    uamiId
        }
      ]
    }
    template: {
      containers: [
        {
          name:  'frontend'
          image: frontendImage
          resources: {
            cpu:    json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL',              value: 'https://${backend.properties.configuration.ingress.fqdn}' }
            // Azure OpenAI — keyless via DefaultAzureCredential (UAMI)
            { name: 'AZURE_OPENAI_ENDPOINT',    value: openAiEndpoint }
            { name: 'AZURE_OPENAI_DEPLOYMENT',  value: openAiDeployment }
            { name: 'AZURE_OPENAI_API_VERSION', value: '2024-08-01-preview' }
            { name: 'AZURE_CLIENT_ID',          value: uamiClientId }
            { name: 'CHAINLIT_AUTH_SECRET',     secretRef: 'chainlit-auth-secret' }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '5' } }
          }
        ]
      }
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
output frontendUrl string = 'https://${frontend.properties.configuration.ingress.fqdn}'
output backendUrl  string = 'https://${backend.properties.configuration.ingress.fqdn}'
