# Azure deployment checkpoint

Recorded: 13 November 2026 (Nigeria time).

## Current state

The local SEC EDGAR pipeline and Power BI report are committed. Azure deployment code is saved on `feature/azure-deployment` and proposed in draft pull request #2. No pull request has been merged as part of this checkpoint.

The project is paused for a group discussion about financing and shared responsibilities. The proposed total spending budget is NGN 5,000; it is not an enforced Azure spending cap.

## Verified on the project owner's PC

- Azure CLI 2.92.0 installed and signed in.
- The `data engineering mentorship` subscription is Enabled and selected as default.
- Bicep CLI 0.49.2 installed.
- `azure/infra/main.bicep` compiled without reported errors.
- Local checkout switched to `feature/azure-deployment`.
- Empty resource group `rg-sec-edgar-capstone` created in `eastus`.
- Azure deployment group what-if completed successfully, reporting **22 resources to create**. This was a preview, not a deployment.

Only the empty resource group was created in these steps. The proposed Function app, storage, SQL database, identities and monitoring resources have not been deployed by this procedure. A preview does not prove runtime functionality or guarantee quota availability.

## Proposed deployment

- Azure Functions Flex Consumption, Python 3.12.
- Separate host storage and ADLS Gen2 storage, Standard LRS.
- Azure SQL Database Basic, 2 GB.
- Application Insights and Log Analytics.
- Managed identities, role assignments and GitHub OIDC federation.

SQL Basic incurs continuing charges while provisioned. Storage, transactions and logs can also incur charges. No complete account-specific estimate has been approved. No budget alert was configured during this session; alerts do not automatically stop spending.

## Resume after the group discussion

1. Agree funding, deployment duration, resource ownership, cleanup responsibility and tasks for each member.
2. Review current Azure prices, billing currency and a total estimate against the NGN 5,000 budget. Set budget alerts and agree a cleanup date before provisioning.
3. Run `git pull --ff-only` on `feature/azure-deployment` to obtain this checkpoint. Preserve existing untracked Power BI project files.
4. Run `az login` if needed and verify the selected subscription. Recreate PowerShell variables after reopening the terminal; they are session-local.
5. Repeat the what-if preview using the commands below and review the result before actual deployment.
6. Deploy only after financing is agreed. Then configure GitHub's `azure` environment and OIDC variables, SQL access, Function code publishing, and a manual end-to-end run, following `azure/README.md`.
7. Validate source-to-report results and reconnect Power BI to Azure SQL. Keep scheduled execution disabled until the team approves it.

## Repeat the preview in PowerShell

From the repository root:

```powershell
$subscriptionId = az account show --query id --output tsv
$sqlAdminObjectId = az ad signed-in-user show --query id --output tsv
$sqlAdminLogin = az ad signed-in-user show --query userPrincipalName --output tsv

az deployment group what-if `
  --resource-group rg-sec-edgar-capstone `
  --template-file .\azure\infra\main.bicep `
  --parameters `
    location=eastus `
    sqlAdminObjectId="$sqlAdminObjectId" `
    sqlAdminLogin="$sqlAdminLogin" `
    secUserAgent="Blessing Edun SEC EDGAR Capstone apostledun@gmail.com"
```

PowerShell blocked `deploy.ps1` under the machine's execution policy. The direct Azure CLI command above completed the preview without changing that policy.

## Evidence and limitations

The successful preview output was reviewed in the project discussion. No credentials, access tokens or local `.env` files belong in Git. The full terminal output is not committed here.

Cloud deployment, live SEC ingestion from Azure, Azure SQL dbt execution, GitHub OIDC access and Power BI refresh against Azure remain unverified. Existing local quality checks establish internal consistency, not independent reconciliation to original SEC filings.
