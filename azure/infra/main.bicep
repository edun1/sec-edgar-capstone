targetScope = 'resourceGroup'

@description('Region supporting Functions Flex Consumption and Azure SQL. Verify subscription availability first.')
param location string = resourceGroup().location
@minLength(3)
@maxLength(7)
param prefix string = 'edgar'
@description('Name of the GitHub repository, owner/repo, used by the deployment identity federation.')
param githubRepository string = 'edun1/sec-edgar-capstone'
@description('Object ID of the human or group that will bootstrap Azure SQL access.')
param sqlAdminObjectId string
param sqlAdminLogin string
param secUserAgent string
@description('Subscription-specific availability must be checked before deployment. Basic has ongoing charges.')
param sqlDatabaseName string = 'edgar'

var suffix = uniqueString(resourceGroup().id)
var tags = { project: 'sec-edgar-capstone'
 environment: 'mentorship' }
var blobOwnerRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var blobContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var queueContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
var blobReaderRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')

resource host 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${prefix}host${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2'
 supportsHttpsTrafficOnly: true
 allowBlobPublicAccess: false
 allowSharedKeyAccess: false }
}
resource hostBlobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = { parent: host
 name: 'default' }
resource packages 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: hostBlobs
  name: 'deployment-packages'
  properties: { publicAccess: 'None' }
}
resource queues 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = { parent: host
 name: 'default' }
resource requests 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = { parent: queues
 name: 'ingestion-requests' }
resource lake 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${prefix}lake${suffix}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { isHnsEnabled: true
 minimumTlsVersion: 'TLS1_2'
 supportsHttpsTrafficOnly: true
 allowBlobPublicAccess: false
 allowSharedKeyAccess: false }
}
resource lakeBlobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = { parent: lake
 name: 'default' }
resource lakeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: lakeBlobs
  name: 'edgar'
  properties: { publicAccess: 'None' }
}
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-logs-${suffix}'
  location: location
  tags: tags
  properties: { retentionInDays: 30
 sku: { name: 'PerGB2018' } }
}
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-insights-${suffix}'
  location: location
  kind: 'web'
  tags: tags
  properties: { Application_Type: 'web'
 WorkspaceResourceId: workspace.id }
}
resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${prefix}-flex-${suffix}'
  location: location
  tags: tags
  sku: { name: 'FC1'
 tier: 'FlexConsumption' }
  properties: { reserved: true }
}
resource function 'Microsoft.Web/sites@2024-04-01' = {
  name: '${prefix}-ingest-${suffix}'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    functionAppConfig: {
      runtime: { name: 'python'
 version: '3.12' }
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${host.properties.primaryEndpoints.blob}${packages.name}'
          authentication: { type: 'SystemAssignedIdentity' }
        }
      }
      scaleAndConcurrency: { maximumInstanceCount: 40
 instanceMemoryMB: 2048 }
    }
    siteConfig: {
      appSettings: [
        { name: 'AzureWebJobsStorage__credential'
 value: 'managedidentity' }
        { name: 'AzureWebJobsStorage__blobServiceUri'
 value: host.properties.primaryEndpoints.blob }
        { name: 'AzureWebJobsStorage__queueServiceUri'
 value: host.properties.primaryEndpoints.queue }
        { name: 'AzureWebJobsStorage__tableServiceUri'
 value: host.properties.primaryEndpoints.table }
        { name: 'SEC_USER_AGENT'
 value: secUserAgent }
        { name: 'EDGAR_LAKE_URL'
 value: lake.properties.primaryEndpoints.blob }
        { name: 'EDGAR_CONTAINER'
 value: lakeContainer.name }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
 value: insights.properties.ConnectionString }
      ]
    }
  }
}
resource functionHostBlob 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(host.id, function.id, blobOwnerRole)
  scope: host
  properties: { principalId: function.identity.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: blobOwnerRole }
}
resource functionHostQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(host.id, function.id, queueContributorRole)
  scope: host
  properties: { principalId: function.identity.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: queueContributorRole }
}
resource functionLake 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(lake.id, function.id, blobContributorRole)
  scope: lake
  properties: { principalId: function.identity.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: blobContributorRole }
}
resource pipeline 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-github-${suffix}'
  location: location
  tags: tags
}
resource federation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: pipeline
  name: 'github-azure-environment'
  properties: { issuer: 'https://token.actions.githubusercontent.com'
 subject: 'repo:${githubRepository}:environment:azure'
 audiences: ['api://AzureADTokenExchange'] }
}
resource pipelineQueue 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(host.id, pipeline.id, queueContributorRole)
  scope: host
  properties: { principalId: pipeline.properties.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: queueContributorRole }
}
resource pipelineLake 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(lake.id, pipeline.id, blobReaderRole)
  scope: lake
  properties: { principalId: pipeline.properties.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: blobReaderRole }
}
// Demo identity can publish function code and temporarily edit SQL firewall in this resource group.
resource pipelineContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, pipeline.id, 'contributor')
  properties: { principalId: pipeline.properties.principalId
 principalType: 'ServicePrincipal'
 roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') }
}
resource sql 'Microsoft.Sql/servers@2023-08-01' = {
  name: '${prefix}-sql-${suffix}'
  location: location
  tags: tags
  properties: {
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    administrators: { administratorType: 'ActiveDirectory'
 principalType: 'User'
 login: sqlAdminLogin
 sid: sqlAdminObjectId
 tenantId: tenant().tenantId
 azureADOnlyAuthentication: true }
  }
}
resource database 'Microsoft.Sql/servers/databases@2023-08-01' = {
  parent: sql
  name: sqlDatabaseName
  location: location
  tags: tags
  sku: { name: 'Basic'
 tier: 'Basic'
 capacity: 5 }
  properties: { maxSizeBytes: 2147483648 }
}
output functionName string = function.name
output hostStorage string = host.name
output lakeStorage string = lake.name
output sqlServer string = sql.name
output sqlHost string = sql.properties.fullyQualifiedDomainName
output sqlDatabase string = database.name
output pipelineClientId string = pipeline.properties.clientId
output pipelineObjectId string = pipeline.properties.principalId
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
