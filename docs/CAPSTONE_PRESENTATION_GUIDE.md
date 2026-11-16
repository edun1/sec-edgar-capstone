# SEC EDGAR capstone: presentation and demonstration guide

Status recorded 16 November 2026 from the project owner's terminal outputs and screenshots. Programme: WES Online / 3MTT / DSN Nigeria mentorship. Repository: edun1/sec-edgar-capstone.

## Opening narration (about one minute)

Our project addresses the difficulty of extracting comparable annual financial figures from public company filings. We built a pipeline for Apple, Microsoft and Alphabet using SEC EDGAR submissions and company facts. Python retrieves source responses, preserves snapshots and selects six financial measures from five original annual filings per company. Azure Functions runs ingestion, Azure Data Lake Storage preserves run files, and GitHub Actions coordinates loading and dbt transformations in Azure SQL. Power BI Desktop imports the reporting table for financial trends, company-period analysis and filing traceability. We began with a working local DuckDB implementation, then deployed and tested the cloud path. The demonstrated cloud run completed successfully, including quality tests and publication of the reporting table.

## Business question and bounded scope

How do revenue, profitability, operating cash flow and financial position change across selected annual reporting periods for three public companies?

- Companies: AAPL, MSFT and GOOGL, identified by ten-digit CIKs.
- Five selected annual periods per company: 15 company-period rows.
- Six measures per period: revenue, net income, assets, liabilities, equity and operating cash flow, giving 90 selected financial observations.
- Demonstrated coverage: Apple and Microsoft period ends in 2022–2026; Alphabet in 2021–2025.
- USD only. Quarterly analysis, currency conversion, valuation and investment recommendations are outside this scope.
- Fiscal year ends differ. Matching calendar-year labels does not mean matching financial start/end dates.

## Explain each pipeline stage

| Stage | What it does | Why it matters |
| --- | --- | --- |
| Company configuration | Stores tickers and SEC CIKs | Avoids relying on company names alone |
| SEC submissions | Supplies filing accession, form, report date and filing date | Identifies the original annual filing |
| SEC company facts | Supplies tagged financial observations with units and dates | Provides structured XBRL-derived figures |
| Historical submissions | Extends Alphabet's recent filing coverage | Recent submissions alone did not cover five years |
| Raw preservation | Keeps response bytes, retrieval metadata and SHA-256 hashes | Supports reproducibility and change detection |
| Python selection | Matches accession, end date, filing date, unit and annual duration | Prevents selecting a quarter merely because it appears in a 10-K |
| Cloud publication | Uploads files under a request-specific run prefix; writes complete manifest last | Avoids treating partial uploads as finished datasets |
| SQL staging | Loads cleaned CSV rows into a separate run schema | Keeps each build separate from the stable report |
| dbt | Casts types, pivots six measures, calculates ratios and growth, runs tests | Produces reusable SQL transformations and checks |
| Reporting publication | Replaces analytics.annual_financials only after checks pass | Keeps failed builds from becoming the current report |
| Power BI | Imports the stable Azure SQL table | Presents the verified output and source identifiers |

## Architecture and execution ownership

GitHub Actions authenticates to Azure using OIDC and a user-assigned managed identity; no client secret is stored for that connection. It sends a request ID to Azure Queue Storage. A queue-triggered Python 3.12 Function runs the ingestion and cleaning scripts in an isolated temporary workspace. Its own system-assigned identity writes the run to the lake. GitHub waits for the exact request's complete manifest, verifies the downloaded cleaned files, loads Azure SQL and invokes dbt. A temporary SQL firewall rule permits the runner IP and is removed afterwards.

Python performs substantial extraction and financial selection; dbt performs typed SQL modeling and analytical transformations. Do not describe all cleaning as dbt work. The analytical loader and dbt execute on the GitHub-hosted runner; the SEC ingestion executes in Azure Functions.

All deployed regional services for the successful stack are in South Africa North, in resource group rg-sec-edgar-southafrica. SQL uses Basic, 2 GB. The original incomplete East US resource group was deleted, with `az group exists` returning false.

## Financial selection policy

1. Select five original 10-K reporting periods per company using submissions and cached history.
2. Match facts to the selected filing's accession number, filing date and period end.
3. Select USD facts using explicit candidate-tag priorities; fail on missing or conflicting required observations.
4. For duration measures (revenue, net income, operating cash flow), require an annual duration of 350–380 days to accommodate 52/53-week years.
5. For assets, liabilities and equity, use instant facts at period end.
6. Preserve the tag/source context in cleaned records and the filing/run context in reporting rows.

The current policy is original-filing based; it does not implement a latest-restated historical series. A filing's fy/fp fields alone are insufficient to establish the observation's own period. Prior-year comparative facts and repeated concepts must not be counted as extra fiscal years.

## Reporting measures and interpretation

- Net profit margin = net income / revenue × 100.
- Revenue growth = (revenue / previous selected annual revenue − 1) × 100.
- Balance-sheet difference = assets − liabilities − equity.
- The first included annual period per company has no previous included period, so growth is blank, not zero.
- Warehouse percentage columns use a 0–100 scale. Power BI measures divide by 100 before percentage formatting.
- Amount cards divide USD by one billion. Company-period KPI measures require one ticker and one period end; otherwise they return blank.

For AAPL with fiscal year-end year 2025 selected, screenshots confirmed revenue 416.16, net income 112.01 and operating cash flow 111.48 USD billion, net margin 26.9% and revenue growth 6.4%. These are dashboard consistency checks against the pipeline output, not independent verification against the original filing document.

## Demonstrated evidence

| Check | Observed result |
| --- | --- |
| Local raw snapshot integrity | Six of six snapshots verified |
| Local selected observations | 90 rows; completeness and balance checks passed |
| Local dbt | Two models and eight tests passed |
| Cloud execution | Successful GitHub financial pipeline run, displayed duration 2m49s |
| Cloud sequence | Ingestion, downloaded-record validation, SQL staging, dbt build/tests, publication, firewall cleanup and evidence retention passed |
| SQL coverage query | AAPL 5, GOOGL 5, MSFT 5 |
| Power BI import | 21 columns and 15 rows loaded |
| Confirmed reporting source run | 20261115T205604835696Z |
| Report deliverable | SEC_EDGAR_Azure.pbix pushed on feature/azure-powerbi-report; pull request #3 opened |

Cloud dbt discovery showed two models and nine tests. Use the successful run's detailed dbt log/run_results artifact for the exact pass summary rather than claiming a test count from the workflow's green status alone.

## Quality checks to explain

- Required keys and amounts are non-null.
- Company/period/measure combinations are unique.
- Every selected company-period has all six required measures.
- Source accession references agree with selected annual filings.
- Dates, units, annual duration and growth blanks follow the selection policy.
- Assets reconcile to liabilities plus equity within the implemented tolerance.
- Reporting coverage is 15 rows and five per company.
- Downloaded cleaned files match the exact run manifest's sizes and SHA-256 hashes.

Hashes detect byte differences. They do not prove financial accuracy. Passing the accounting equation does not prove the correct filing or tag was chosen. Manual reconciliation of selected values to original filing documents remains unfinished and should be recorded honestly.

## Dashboard walk-through

1. Financial Overview: explain the revenue and net-income trends. Use a company filter and clear it again. Point out fiscal-period differences and Alphabet's earlier ending coverage.
2. Company & Period Detail: choose AAPL and 2025. Explain each of the five cards. Clear the company filter to demonstrate blank guarded KPIs. Restore a valid selection.
3. Filing Traceability: show ticker, period end, filing date, accession number, original_10k selection policy and source run ID. Explain the difference between reporting period, filing event and ingestion time.

## Five-minute live demonstration

- 0:00–0:40: business problem and scope.
- 0:40–1:30: explain architecture and where each workload runs.
- 1:30–2:10: show a previously successful GitHub run and its validation/publication steps.
- 2:10–2:40: show SQL counts and the reporting source run ID.
- 2:40–4:20: walk through the three Power BI pages.
- 4:20–5:00: explain design tradeoffs, limitations and next improvements.

Do not depend on a fresh API ingestion during the timed presentation. Use saved run evidence and the report's imported data as a backup. If demonstrating refresh, verify credentials, firewall access and the source beforehand.

## Panel questions and concise answers

**Why SEC EDGAR?** It provides public, structured company filing and financial-fact APIs. Each observation can be related to a filing and reporting period.

**Why three companies?** A bounded scope let us implement traceability, quality checks and a working cloud path within the deadline and budget. Scaling requires broader tag coverage and stronger historical handling.

**Why preserve raw responses?** We can reproduce transformations and inspect source changes without repeatedly downloading everything. Raw data is kept in storage rather than committed to Git.

**Why use both Python and dbt?** Python handles HTTP, files and detailed source selection. dbt handles typed SQL models, derived metrics and SQL data tests.

**Why DuckDB first?** It provided a local development and verification path before cloud access was available. The Azure SQL dbt project is separate because SQL dialects and deployment requirements differ.

**Why queue-triggered Functions?** The workflow can submit a request without waiting on an HTTP ingestion endpoint. The queue supports retries; run IDs, a renewable lease and completion markers manage duplicate or partial delivery.

**Is it real time?** No. This is batch processing of filing data. The cloud run was manually triggered. Daily workflow scheduling is implemented but remains disabled unless explicitly enabled. Power BI Desktop uses Import mode with manual refresh; automatic Power BI Service refresh has not been configured.

**How do you stop publishing bad data?** Selection and quality failures stop the run. Each SQL build uses an isolated schema. The stable reporting table is published only after dbt checks pass.

**How is access controlled?** Managed identities and OIDC connect cloud workloads. The Power BI reader has SELECT on the analytics schema; pipeline permissions allow modeling/publication. SQL uses Entra-only authentication and temporary runner firewall rules. Demo pipeline Azure permissions include resource-group Contributor and need tighter separation for production.

**What did debugging teach you?** Regional availability must be verified against the subscription. Azure OIDC subject matching must be exact. Function subprocesses need deployed package paths. SQL contained users for managed identities use the client ID with the SID method. dbt metadata permissions are required, and columnstore defaults must be disabled for Basic SQL.

**Does it cost nothing?** No. SQL Basic keeps accruing charges while provisioned; storage, operations and monitoring may also cost money. The stated budget is NGN 6,000, not an enforced cap. Budget alerts, if configured, notify rather than stop charges. Measure actual cost and agree teardown timing.

**What remains?** Independent filing reconciliation; evidence/documentation updates; report review/merge; cost monitoring and cleanup; production hardening; and optional scheduled cloud and Power BI Service refresh after account/licensing and budget decisions.

## Before submission

- Capture screenshots of the successful workflow, dbt test summary, SQL coverage and all report pages.
- Download the workflow evidence artifact before its seven-day retention expires.
- Keep the final PBIX and documentation in GitHub; verify PR #3's current review/merge status.
- Record actual team contributions accurately. Do not attribute code, testing, funding or deployment to someone without evidence.
- Check Power BI refresh once using the authorized reader account; do not include passwords or MFA information in screenshots.
- Update stale README sections that still describe Azure as planned or deferred.
- Reconcile representative financial values to original SEC filings and record the comparisons.
- Check accrued Azure cost; keep automated scheduling off unless explicitly approved.
- Agree whether the demonstration needs live Azure resources after assessment; save evidence before any teardown.

## Team narration

Use 'the project' or 'our project' for the shared deliverable, but explain actual contributions truthfully when asked. Separate completed work, peer review, financing and planned tasks. A repository commit records a change, not proof that everyone participated equally.
