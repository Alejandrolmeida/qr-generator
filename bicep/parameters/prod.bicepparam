using 'main.bicep'

param environment   = 'prod'
param location      = 'westeurope'
param projectName   = 'qrgen'

param tags = {
  Environment: 'Production'
  CostCenter: 'Operations'
  Owner: 'alejandro@azurebrains.com'
  Project: 'qr-accreditation'
  ManagedBy: 'Bicep-IaC'
  Criticality: 'Medium'
}

param backendImage  = 'acrazurebrainschat.azurecr.io/qrgen/backend-app:latest'
param frontendImage = 'acrazurebrainschat.azurecr.io/qrgen/frontend-app:latest'

param acrLoginServer = 'acrazurebrainschat.azurecr.io'

param acrUsername         = ''
param acrPassword         = ''
param openAiEndpoint      = 'https://oai-azurebrains-blog.openai.azure.com/'
param openAiApiKey        = ''
param openAiDeployment    = 'gpt-4o'
param chainlitAuthSecret  = ''
