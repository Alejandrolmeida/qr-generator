using 'main.bicep'

param environment   = 'prod'
param location      = 'westeurope'
param projectName   = 'lanyards-aigen'

param tags = {
  Environment: 'Production'
  CostCenter: 'Operations'
  Owner: 'alejandro@azurebrains.com'
  Project: 'lanyards-ai-generator'
  ManagedBy: 'Bicep-IaC'
  Criticality: 'Medium'
}

// Imágenes Docker — el pipeline sobreescribe estos valores con el tag del build
param backendImage  = 'acrazurebrainschat.azurecr.io/lanyards/backend-app:latest'
param frontendImage = 'acrazurebrainschat.azurecr.io/lanyards/frontend-app:latest'

param acrLoginServer   = 'acrazurebrainschat.azurecr.io'
param openAiEndpoint   = 'https://oai-azurebrains-blog.openai.azure.com/'
param openAiDeployment = 'gpt-4o'

// ─── NO hay @secure() en este fichero ────────────────────────────────────────
// Todos los secretos (openAiApiKey, chainlitAuthSecret) residen en AKV.
// Las Container Apps los leen en runtime vía Managed Identity (UAMI).
// GitHub solo almacena AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID.
