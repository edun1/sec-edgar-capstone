# Group capstone progress and review guide

Status date: 8 November 2026  
Programme: WES Online / 3MTT / DSN Nigeria  
Project: SEC EDGAR Financial Data Pipeline — Public Company Filings Analytics

## Purpose of this review

The local implementation is already committed to `main`. This document gives colleagues one place to understand the work, inspect its code and report, record feedback, and agree on remaining responsibilities. This pull request adds documentation; it does not introduce or re-merge the existing pipeline implementation.

## Business problem and current scope

Public financial filings contain valuable figures, but preparing consistent annual measures across companies and periods takes manual effort. The pipeline collects SEC submissions and company facts, preserves source responses, selects traceable annual observations, validates them, and prepares analysis in Power BI.

| Company | Ticker | CIK | Selected fiscal years in the current downloaded data |
| --- | --- | --- | --- |
| Apple | AAPL | 0000320193 | 2022–2026 |
| Microsoft | MSFT | 0000789019 | 2022–2026 |
| Alphabet | GOOGL | 0001652044 | 2021–2025 |

The current dataset contains 15 original annual filing selections and 90 financial observations: revenue, net income, assets, liabilities, equity, and operating cash flow for each company-period. These periods describe the current snapshot, not an immutable coverage guarantee.

## Work completed

1. **Environment and source control:** Python virtual environment, recorded dependencies, organised project folders, Git history and a public GitHub repository.
2. **SEC ingestion:** configuration-driven collection of submissions and company facts for three companies, with a shared client supporting request spacing, timeouts, selected retries and logging. The reported six-download live run succeeded without retries; retry behaviour was not demonstrated by that successful run.
3. **Raw preservation:** timestamped JSON snapshots with source URLs, UTC retrieval times, response sizes and SHA-256 hashes. The six downloaded snapshots passed recorded integrity checks.
4. **History coverage:** inspection identified insufficient recent Alphabet annual history. Its referenced older submissions file was downloaded and used to complete the selected periods.
5. **Financial selection:** original 10-K accession number, reporting end date, filing date and USD units are matched. Duration measures require 350–380 days and consistent starts. Missing or conflicting suitable observations cause failure.
6. **Python quality checks:** company/period coverage, complete measure sets, duplicate keys, numeric values, units, filing references, dates, durations and balance equations.
7. **Local warehouse:** DuckDB landing tables loaded from selected CSVs, with transactional replacement.
8. **dbt:** a typed staging view and annual reporting table; eight data tests. The reporting model calculates net margin, revenue growth and balance differences.
9. **Power BI:** financial trends, company-period detail and filing traceability pages, with filters and guarded single-period KPI measures.
10. **Repeatable rebuild:** one command verifies saved inputs, rebuilds selections, checks data, loads the warehouse, runs dbt and exports reporting CSV. It logs stages, stops on failure and records a summary.
11. **Publication:** source code and the PBIX have been pushed to this repository.

## Where to review

| Area | Files |
| --- | --- |
| Company configuration | [companies.json](../config/companies.json) |
| SEC downloader and runner | [sec_client.py](../src/sec_client.py), [run_ingestion.py](../src/run_ingestion.py) |
| Snapshot verification | [verify_ingestion.py](../src/verify_ingestion.py) |
| Annual selection | [build_annual_filings.py](../src/build_annual_filings.py), [build_financial_measures.py](../src/build_financial_measures.py) |
| Financial checks | [check_financial_measures.py](../src/check_financial_measures.py) |
| Warehouse loader | [load_warehouse.py](../src/load_warehouse.py) |
| dbt models | [staging model](../dbt/models/staging/stg_financial_measures.sql), [annual reporting model](../dbt/models/marts/annual_financials.sql) |
| dbt tests | [annual validity](../dbt/tests/assert_annual_financials_valid.sql), [unique measures](../dbt/tests/assert_unique_financial_measures.sql) |
| Offline runner and export | [run_pipeline.py](../src/run_pipeline.py), [export_reporting.py](../src/export_reporting.py) |
| Run instructions and test evidence | [RUN_LOCAL_PIPELINE.md](RUN_LOCAL_PIPELINE.md), [VALIDATION.md](VALIDATION.md) |
| Dashboard | [Power BI report.pbix](../powerbi/SEC_EDGAR_PowerBI/Power%20BI%20report.pbix) — download and open in Power BI Desktop |

## Evidence and its limits

- Reported original downloads: six successes; six snapshots verified.
- Selected data: 15 annual filings and 90 observations; Python checks passed and all 15 balance differences were USD 0.
- Reported dbt build: two models and eight data tests passed.
- Local integration testing used reconstructed SEC-shaped fixtures derived from uploaded reporting data. These fixtures are test inputs, not independent SEC source evidence.
- Three runner failure-handling unit tests passed; a corrupted fixture stopped execution before transformations.
- Blessing subsequently reported a successful full local runner execution on the Windows PC.
- The Power BI report opened in Desktop, and Apple 2025 displayed values were checked against the exported CSV.
- Independent reconciliation against original filing documents remains pending. Internal consistency and matching exported figures do not establish source-filing accuracy.
- No CI run or independent colleague reproduction is claimed by this documentation-only PR.

## Important design decisions

- **Local first:** DuckDB/dbt/Power BI are implemented. Azure subscription access was not established, so cloud deployment is deferred.
- **Original filings:** amendments and restatements are not automatically substituted.
- **Fiscal calendars:** Apple ends in September, Microsoft in June and Alphabet in December. Same-year labels do not mean identical reporting windows.
- **Growth:** the earliest selected period has no previous year in scope, so its growth is blank.
- **KPI cards:** detail measures stay blank unless one company-period row is selected.
- **Execution:** the new runner rebuilds saved snapshots; it does not download data, schedule itself, refresh Power BI or publish a report.
- **Freshness:** the Power BI query includes an embedded fallback snapshot. Review the actual CSV source and ingestion reference before claiming a refreshed dashboard.
- **Inputs:** raw snapshots and ingestion summaries are excluded from Git. A fresh clone cannot run the offline rebuild until these inputs are generated or supplied.

## Colleague review checklist

- [ ] Read the run guide and explain the end-to-end data flow.
- [ ] Inspect the original-filing selection and financial tag priority rules.
- [ ] Review fiscal dates, durations, currency handling and growth definitions.
- [ ] Review validation coverage and propose missing failure cases.
- [ ] Reproduce setup and execution, recording versions and actual results.
- [ ] Reconcile selected figures independently against original filings, recording accession, statement, units and differences.
- [ ] Open the dashboard; check all pages, filters, blank-card behaviour and percentage formatting.
- [ ] Confirm the Power BI source path and remove or clearly disclose the snapshot fallback.
- [ ] Review documentation and agree on presentation roles.

Comment on this PR with the area reviewed, evidence checked, findings, proposed action and whether you can own that action. Owners and deadlines are intentionally unassigned until colleagues agree.

## Remaining submission work

| Task | Current status | Owner |
| --- | --- | --- |
| Original-filing reconciliation | Pending | To agree |
| Independent reproduction and failure review | Pending | To agree |
| Final architecture and source-to-output documentation | Needs completion | To agree |
| Dashboard freshness and final readability verification | Needs completion | To agree |
| Scheduled execution | Not configured | To agree |
| Final report, slides and demo rehearsal | Pending | To agree |
| Azure deployment | Deferred; not a completed deliverable | To agree |

## Milestones already on main

- `72be387`: multi-company ingestion and validated annual financial measures.
- `ada15cb`: local warehouse, dbt and repeatable pipeline.
- `ea0e60f`: Power BI dashboard.

The group should describe both completed behaviour and remaining limitations accurately during the panel presentation.
