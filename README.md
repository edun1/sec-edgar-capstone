# SEC EDGAR Financial Data Pipeline

Data engineering capstone for the WES Online / 3MTT / DSN Nigeria mentorship programme.

## Objective

Build a reproducible pipeline that collects SEC company filings and financial facts, preserves source responses, transforms selected financial measures, and supports analysis in Power BI.

## Current implementation

- Python virtual environment and dependency files
- Apple submissions ingestion
- Apple company facts ingestion
- Timestamped raw snapshots with source metadata
- SHA-256 integrity verification
- Offline inspection of candidate financial concepts

## Planned implementation

- Reusable ingestion for Apple, Microsoft, and Alphabet
- Controlled requests, retries, and execution logging
- Financial period selection and source traceability
- Azure Data Lake Storage and Azure SQL
- dbt transformations and data quality tests
- Power BI reporting
- Automated execution

## Local setup

Run these commands from the project root in PowerShell:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
notepad .env
```

For the project author's local configuration, set the following value in .env:

```dotenv
SEC_USER_AGENT="Blessing Edun SEC EDGAR Capstone apostledun@gmail.com"
```

Other users reproducing this project should use their own name and contact email.

## Run the current scripts

```powershell
.\.venv\Scripts\python.exe src\ingest_sec.py
.\.venv\Scripts\python.exe src\ingest_company_facts.py
.\.venv\Scripts\python.exe src\inspect_company_facts.py
```

The inspection script requires a successful company facts extraction first.
It reads saved data without making another API request.

## Data handling

Raw responses are stored under data/raw and excluded from Git.
Each successful extraction creates a separate timestamped snapshot.

Extraction metadata records:

- Source URL
- Company CIK
- Retrieval time in UTC
- HTTP status
- Content type
- Response size
- SHA-256 integrity hash

The local .env file is excluded from Git.
.env.example documents the required configuration using a placeholder.

## Financial interpretation

Company facts can contain repeated, comparative, quarterly, and revised observations.

Assets, liabilities, and equity describe a financial position at a particular date.
Revenue, net income, and operating cash flow cover a reporting period.

An observation appearing in an annual filing does not automatically represent a full fiscal year.
Financial selection rules are still under development.
Current inspection output is not yet a curated reporting dataset.

## Data source

U.S. Securities and Exchange Commission, SEC EDGAR:

- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- https://data.sec.gov/submissions/CIK0000320193.json
- https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json

## Local warehouse and dbt (implemented)

The project now uses DuckDB and dbt-duckdb locally; Azure deployment remains deferred. Python selects 90 annual financial observations from 15 original 10-K filings. dbt creates a typed staging view and annual reporting table and runs eight data tests. Exported reporting data feeds Power BI Desktop.

### One-command rebuild

```powershell
.\run_pipeline.cmd
```

Uses existing SEC snapshots and ingestion summaries. No downloads occur. See docs/RUN_LOCAL_PIPELINE.md for prerequisites, logs, failure recovery, and Power BI refresh limitations.

### Runner failure-handling tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
