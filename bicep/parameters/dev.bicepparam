using 'main.bicep'

param environment   = 'dev'
param location      = 'westeurope'
param projectName   = 'lanyards-aigen'

param tags = {
  Environment: 'Development'
  CostCenter: 'Engineering'
  Owner: 'alejandro@azurebrains.com'
  Project: 'lanyards-ai-generator'
  ManagedBy: 'Bicep-IaC'
}

// Imágenes Docker — el pipeline sobreescribe estos valores con el digest del build
param backendImage  = 'acrazurebrainschat.azurecr.io/lanyards/backend-app:latest'
param frontendImage = 'acrazurebrainschat.azurecr.io/lanyards/frontend-app:latest'

param acrLoginServer  = 'acrazurebrainschat.azurecr.io'
param openAiEndpoint  = 'https://oai-azurebrains-blog.openai.azure.com/'
param openAiDeployment = 'gpt-4o'

// Los parámetros @secure() (acrUsername, acrPassword, openAiApiKey, chainlitAuthSecret)
// se inyectan en tiempo de ejecución desde el AKV por el workflow deploy.yml.
// No se declaran aquí para evitar valores vacíos o placeholders en el repo.
