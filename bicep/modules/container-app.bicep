// =============================================================================
// Módulo: Azure Container Apps Environment + Backend + Frontend
// =============================================================================

param prefix string
param location string
param tags object

param logAnalyticsWorkspaceId string
param logAnalyticsWorkspaceCustomerId string
@secure()
param logAnalyticsWorkspaceKey string

param acrLoginServer string
@secure()
param acrUsername string
@secure()
param acrPassword string

param backendImage string
param frontendImage string

@secure()
param storageConnectionString string

param openAiEndpoint string
@secure()
param openAiApiKey string
param openAiDeployment string

@secure()
param chainlitAuthSecret string

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
        sharedKey: logAnalyticsWorkspaceKey
      }
    }
  }
}

// ── Backend Container App ─────────────────────────────────────────────────────
resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${prefix}-backend'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: false           // solo accesible desde el frontend (interno)
        targetPort: 8080
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password';           value: acrPassword }
        { name: 'storage-conn-str';       value: storageConnectionString }
        { name: 'openai-api-key';         value: openAiApiKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'AZURE_STORAGE_CONNECTION_STRING'; secretRef: 'storage-conn-str' }
            { name: 'AZURE_OPENAI_ENDPOINT';           value: openAiEndpoint }
            { name: 'AZURE_OPENAI_API_KEY';            secretRef: 'openai-api-key' }
            { name: 'AZURE_OPENAI_DEPLOYMENT_GPT4O';   value: openAiDeployment }
            { name: 'FONTS_FOLDER';                    value: '/app/fonts' }
            { name: 'OUTPUT_FOLDER';                   value: '/tmp/qr-output' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health'; port: 8080 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0    // escala a 0 cuando no hay uso
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
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true            // accesible desde internet
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        { name: 'acr-password';           value: acrPassword }
        { name: 'openai-api-key';         value: openAiApiKey }
        { name: 'chainlit-auth-secret';   value: chainlitAuthSecret }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'BACKEND_URL';                   value: 'https://${backend.properties.configuration.ingress.fqdn}' }
            { name: 'AZURE_OPENAI_ENDPOINT';         value: openAiEndpoint }
            { name: 'AZURE_OPENAI_API_KEY';          secretRef: 'openai-api-key' }
            { name: 'AZURE_OPENAI_DEPLOYMENT';       value: openAiDeployment }
            { name: 'AZURE_OPENAI_API_VERSION';      value: '2024-02-15-preview' }
            { name: 'CHAINLIT_AUTH_SECRET';          secretRef: 'chainlit-auth-secret' }
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
output backendUrl string  = 'https://${backend.properties.configuration.ingress.fqdn}'
