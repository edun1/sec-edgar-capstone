# Run the complete local rebuild

From the existing sec-edgar-capstone project root in PowerShell:

```powershell
.\run_pipeline.cmd
```

The runner uses the project .venv; it sets SEC_EDGAR_DB_PATH itself. It makes no SEC requests. Keep the existing data/raw snapshots and logs/ingestion_*_summary.json files: those are inputs, not disposable logs.

Stages: verify the latest six-download ingestion run -> select annual filings (including cached Alphabet history) -> select financial observations -> check quality -> load DuckDB -> dbt debug -> dbt build and tests -> reporting CSV export.

A failure stops later stages and returns a nonzero exit code. Full output and a UTC run summary are saved under logs/pipeline_*. The success summary records the final CSV hash. Existing older output can remain after a failed run; only a success summary certifies a new completed export. The warehouse load is transactional, but the complete multi-stage pipeline is not a single database transaction.

A lock prevents concurrent uses of this runner. If the PC loses power, first confirm no runner is active, then remove the empty logs/.pipeline.lock directory before retrying. Do not run the older standalone scripts concurrently with the runner.

For a rebuild from already cleaned CSVs only:

```powershell
.\run_pipeline.cmd --from-cleaned
```

This explicitly skips raw integrity verification and selection; it is not the same evidence as a full snapshot rebuild.

## Refreshing live SEC data

The new runner does not download. For fresh data, run your existing src/run_ingestion.py, check six successes, and run src/ingest_submission_history.py for the currently configured Alphabet history. Then run the offline runner. The history script currently handles Alphabet only, with one request attempt per history file. General history ingestion and retry consolidation remain future improvements. If any download fails, resolve it before rebuilding.

## Power BI

After SUCCESS, open the report and click Home > Refresh. The runner does not refresh or publish Power BI. The delivered report query uses the original Windows CSV path and has an embedded CSV fallback: on another PC an unavailable path can silently load that old snapshot. Before claiming a fresh dashboard, check the Power Query source and the source_run_id in the filing traceability page against the successful pipeline run's ingestion input. Remove the fallback or set the source path explicitly for final submission.

## Remaining capstone work

- Independently reconcile selected values against original filings.
- Test live retry/failure handling; the current verification covers saved snapshots.
- Improve shared history downloading and record all source snapshot paths explicitly.
- Document cross-company fiscal calendars and original-filing/restatement limitations.
- Add a scheduled execution mechanism and final slides/demo rehearsal.
- Azure deployment remains deferred; do not claim cloud resources were deployed.
