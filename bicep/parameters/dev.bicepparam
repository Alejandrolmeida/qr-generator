using 'main.bicep'

param environment   = 'dev'
param location      = 'westeurope'
param projectName   = 'qrgen'

param tags = {
  Environment: 'Development'
  CostCenter: 'Engineering'
  Owner: 'alejandro@azurebrains.com'
  Project: 'qr-accreditation'
  ManagedBy: 'Bicep-IaC'
}

// Las imágenes se sobreescriben en el pipeline con el digest exacto del build
param backendImage  = 'acrazurebrainschat.azurecr.io/qrgen/backend-app:latest'
param frontendImage = 'acrazurebrainschat.azurecr.io/qrgen/frontend-app:latest'

param acrLoginServer = 'acrazurebrainschat.azurecr.io'

// Los secretos se inyectan desde GitHub Secrets en el pipeline
// (no se commitean valores reales aquí)
param acrUsername         = ''    // sobreescrito en CI/CD
param acrPassword         = ''
param openAiEndpoint      = 'https://oai-azurebrains-blog.openai.azure.com/'
param openAiApiKey        = ''
param openAiDeployment    = 'gpt-4o'
param chainlitAuthSecret  = ''
