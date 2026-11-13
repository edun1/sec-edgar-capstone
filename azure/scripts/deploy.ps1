param(
    [Parameter(Mandatory=$true)][string]$SubscriptionId,
    [Parameter(Mandatory=$true)][string]$ResourceGroup,
    [Parameter(Mandatory=$true)][string]$Location,
    [Parameter(Mandatory=$true)][string]$SqlAdminObjectId,
    [Parameter(Mandatory=$true)][string]$SqlAdminLogin,
    [Parameter(Mandatory=$true)][string]$SecUserAgent,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
function Invoke-Az {
    & az @args
    if ($LASTEXITCODE -ne 0) { throw 'Azure CLI command failed' }
}
Invoke-Az account set --subscription $SubscriptionId
# Preview requires an existing resource group. Applying creates it if absent.
if ($Apply) { Invoke-Az group create --name $ResourceGroup --location $Location --output none }
$deploymentArgs = @('--resource-group', $ResourceGroup, '--template-file', "$root/azure/infra/main.bicep", '--parameters', "location=$Location", "sqlAdminObjectId=$SqlAdminObjectId", "sqlAdminLogin=$SqlAdminLogin", "secUserAgent=$SecUserAgent")
if (-not $Apply) {
    Invoke-Az deployment group what-if @deploymentArgs
    Write-Host 'Preview only. No deployment performed. Re-run with -Apply after reviewing costs.'
    exit 0
}
Invoke-Az deployment group create --name edgar-bootstrap @deploymentArgs --output none
Invoke-Az deployment group show --resource-group $ResourceGroup --name edgar-bootstrap --query properties.outputs --output json | Set-Content -Encoding utf8 "$root/azure/deployment-outputs.json"
Write-Host 'Infrastructure deployed. Follow azure/README.md for identity, SQL bootstrap and Function publishing.'
