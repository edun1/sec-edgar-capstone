# Azure deployment preparation

**Status: code prepared; not deployed or cloud-verified.** The working local DuckDB pipeline remains separate. No Azure resources are created by cloning this branch, running offline tests or compiling Bicep.

## Architecture

GitHub Actions (manual initially; optional daily schedule) sends an exact request ID to an Azure Storage queue. An Azure Function downloads SEC data, runs the existing financial selection/checks in isolated temporary storage, and uploads raw/cleaned files to an ADLS Gen2 container. It writes a completed manifest last. Actions waits for that exact manifest, verifies hashes, loads a new Azure SQL schema, runs dbt tests, then transactionally publishes `analytics.annual_financials` for Power BI.

Raw and cleaned data reside in Azure. dbt runs on a GitHub-hosted runner against Azure SQL, not inside the Function. This is a cloud-hosted workflow that does not depend on a laptop; it is not an implementation where all compute runs inside Azure.

A shared workflow concurrency group serializes ingestion/build requests and Function publishing. The per-request storage lease and completed marker handle duplicate queue delivery. Retries write into the same request prefix; incomplete prefixes are not ready for downstream use. Requests that repeatedly fail go to `ingestion-requests-poison` after the configured dequeue limit.

## Before spending money

1. Obtain an active subscription and permission to create resources and assign roles (for example Owner on the dedicated capstone resource group). Never share account passwords.
2. Confirm region availability for Flex Consumption Python 3.12 and Azure SQL Basic in that subscription. A Bicep compile does not check quotas, policies, runtime availability or regional capacity.
3. Review current regional Azure prices. **This template is not free:** SQL Basic has ongoing charges; storage, Functions, logs and GitHub Actions can also incur usage charges. Set a budget alert; it is an alert, not a spending cap. SQL Basic was selected for a small, predictable demonstration database, not because it auto-pauses.
4. Use a dedicated resource group. Agree on the subscription owner, spending limit and cleanup date before applying.

## Prerequisites

- Azure CLI with Bicep support and a signed-in account in the correct tenant.
- PowerShell for `deploy.ps1`, Python 3.12 for cloud scripts.
- GitHub repository administration access to configure the `azure` environment and variables.
- ODBC Driver 18 for SQL Server on the machine used for SQL bootstrap.
- The complete repository source; the Function ZIP is generated from `src/` and `config/`.

Use a separate Python environment; do not replace the working local `.venv`:

```powershell
py -3.12 -m venv .venv-azure
.\.venv-azure\Scripts\python.exe -m pip install -r azure\requirements-lock.txt
az login
```

Python 3.12 may need installation on the current Windows PC. Alternatively, run bootstrap from an appropriately configured Cloud Shell/session. The Function remote build and hosted workflow install cloud dependencies separately. The cloud runner lockfile records the Linux/Python 3.12 environment used for dependency, parsing and offline checks. It does not establish Azure runtime compatibility; repeat connection/build tests after deployment. Function remote builds currently use separate bounded requirements, which should also be frozen after successful deployment.

## Infrastructure preview and application

`azure/infra/main.bicep` creates two private-data storage accounts (host plus ADLS Gen2), queue, deployment container, Flex Function App, Application Insights/Log Analytics, Azure SQL Basic database, an Entra SQL administrator, and a user-assigned identity federated to GitHub environment `azure`.

All data access uses Entra identities. Storage endpoints remain publicly reachable but require authorization; no public blob access or shared storage keys are enabled. SQL has no allow-all-Azure firewall rule. This is a small capstone design, not a private-network production topology.

Set these example variables to your own subscription and tenant identity values:

```powershell
$subscriptionId = '<subscription-id>'
$resourceGroup = 'rg-edgar-capstone'
$location = '<supported-region>'
$sqlAdminId = '<your-user-object-id-in-this-tenant>'
$sqlAdminLogin = '<your-Entra-user-sign-in-name>'
$secUserAgent = '<your-name> SEC EDGAR Capstone <contact-email>'
az account set --subscription $subscriptionId
az group create --name $resourceGroup --location $location
```

The current template configures a **User** Entra administrator. For a group administrator, change `principalType` to `Group` and use the group's object ID; do not pass a subscription ID or application/client ID as the administrator SID.

Preview (resource group must already exist):

```powershell
.\azure\scripts\deploy.ps1 -SubscriptionId $subscriptionId -ResourceGroup $resourceGroup -Location $location -SqlAdminObjectId $sqlAdminId -SqlAdminLogin $sqlAdminLogin -SecUserAgent $secUserAgent
```

After reviewing what-if and costs, apply by adding `-Apply` to that command. Outputs are saved in ignored `azure/deployment-outputs.json`. Never commit private local settings. Role assignments can take several minutes to propagate; do not treat an immediate 403 as proof that code is broken.

## Configure GitHub OIDC

The template trusts only `repo:edun1/sec-edgar-capstone:environment:azure`. For a fork, change `githubRepository` before deployment.

Create the GitHub environment **azure**. Configure its deployment branch policy and reviewers deliberately: this environment uses a resource-group Contributor identity. Protect workflow changes and do not let untrusted branches use the identity. For production, separate deployment and runtime identities and use narrower custom roles/private networking.

Add the following **environment variables** from deployment outputs:

| GitHub variable | Output/value |
| --- | --- |
| AZURE_CLIENT_ID | pipelineClientId |
| AZURE_TENANT_ID | tenantId |
| AZURE_SUBSCRIPTION_ID | subscriptionId |
| AZURE_FUNCTION_NAME | functionName |
| AZURE_HOST_STORAGE | hostStorage |
| AZURE_LAKE_STORAGE | lakeStorage |
| AZURE_SQL_SERVER | sqlServer |
| AZURE_SQL_HOST | sqlHost |
| AZURE_SQL_DATABASE | sqlDatabase |
| AZURE_RESOURCE_GROUP | resource group name |

No client secret, SQL password or storage account key is needed. Set **repository** variable `ENABLE_AZURE_SCHEDULE=false` initially; this must be a repository variable because the job-level guard is evaluated before environment variables are loaded.

## Bootstrap SQL permissions once

Sign in as the Entra SQL administrator. Temporarily add only your current public IP in the SQL server firewall using the Azure portal or `az sql server firewall-rule create`. Remove it after bootstrap. Do not enable the broad 'Allow Azure services' rule.

```powershell
$env:AZURE_SQL_HOST = '<sqlHost-output>'
$env:AZURE_SQL_DATABASE = 'edgar'
.\.venv-azure\Scripts\python.exe azure\scripts\sql_warehouse.py bootstrap --principal-object-id '<pipelineObjectId-output>'
```

Use the identity's **object/principal ID**, not client ID. The script creates a contained Entra application user using its SID, avoiding a Microsoft Graph name lookup. It grants schema/table/view creation and access to the publishing schema. The identity owns its isolated run schemas. Re-running bootstrap assumes an existing `edgar_pipeline` principal refers to the same identity; inspect and recreate it as admin if the identity was replaced.

## Publish and run

After this branch is reviewed/merged (do not merge the separate group-review PR automatically):

1. Run **Publish Azure ingestion function** manually in Actions. It builds `azure/function.zip` from the shared source and publishes through a remote Flex build.
2. Run **Azure financial pipeline** manually. The workflow sends a request, waits up to 30 minutes, validates downloaded files, permits only the runner IP temporarily in SQL, loads a new run schema, builds/tests dbt, publishes, then removes the firewall rule.
3. Verify a complete lake manifest, hashes, Functions logs, SQL row counts and dbt results. Confirm original-filing reconciliation independently.
4. Repeat the run and test a deliberate failure before enabling scheduling. A failed build must leave the last published reporting table intact.
5. Set repository variable `ENABLE_AZURE_SCHEDULE=true` only after verification. The proposed daily schedule is 06:00 UTC / 07:00 Nigeria time. GitHub scheduled workflows can be delayed; this is not a precise-time SLA.

Hard cancellation, loss of runner connectivity or platform failure can prevent an `always()` cleanup step. Check for leftover `gha-*` firewall rules and remove them manually. Keep the last successful report visible, but show freshness and distinguish it from a failed new run.

## Connect Power BI to Azure SQL

Use Get data > Azure SQL Database/SQL Server, enter the SQL hostname and `edgar`, then choose `analytics.annual_financials`. Keep its field names; retain existing measures. Use a read-only Entra database user with SELECT on schema `analytics`; an administrator must create/grant that user. Do not use the deployment identity as a shared report login.

Remove the local CSV/embedded-data fallback before describing the dashboard as live. Validate the source_run_id and filing dates in the report. Power BI Desktop refresh is manual. Automatic report refresh requires publication to Power BI Service, configured credentials and an appropriate licence/capacity; it is not configured by these workflows.

## Cleanup and limits

Every successful attempt creates a `run_<request-id>` SQL schema. Basic has a 2 GB database limit; review/drop old run schemas after confirming published output and recording evidence. This initial code intentionally does not auto-delete historical builds. Raw lake snapshots and logs also accumulate: define a retention policy after team review.

Disable the schedule, preserve required evidence, then delete the dedicated resource group when agreed. Never delete a shared resource group. Deleting resources ends their future charges but does not erase charges already incurred.

## Local verification (no subscription)

```powershell
python -m unittest discover -s azure/tests -v
python -m compileall -q src azure
az bicep build --file azure/infra/main.bicep --outfile azure/infra/main.local.json
```

See `azure/VALIDATION.md` for actual checks performed and unverified areas. Infrastructure compilation is not an Azure deployment test.
