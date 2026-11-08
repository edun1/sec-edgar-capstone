"""Rebuild local reporting from saved SEC snapshots; no network requests."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_stage(name, command, environment, log, root=PROJECT_ROOT):
    """Stream child output to console and log; stop on a failed stage."""
    print(f"\n=== {name} ===", flush=True)
    log.write(f"\n=== {name} ===\n")
    log.flush()
    with subprocess.Popen(
        command, cwd=root, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
    ) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        code = process.wait()
    if code:
        raise subprocess.CalledProcessError(code, command)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-cleaned", action="store_true",
        help="Start from existing cleaned CSVs; skips raw verification/selection.",
    )
    args = parser.parse_args(argv)
    logs = PROJECT_ROOT / "logs"
    logs.mkdir(exist_ok=True)
    lock = logs / ".pipeline.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        print("FAILED: Another run is active, or a prior run left logs/.pipeline.lock.")
        print("Remove the lock folder only after confirming no pipeline is running.")
        return 1

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    summary_path = logs / f"pipeline_{run_id}_summary.json"
    summary = {
        "run_id": run_id, "started_at_utc": utc_now(),
        "mode": "cleaned_rebuild" if args.from_cleaned else "saved_snapshot_rebuild",
        "network_requests": False, "status": "running", "stages": [],
    }
    environment = os.environ.copy()
    environment["SEC_EDGAR_DB_PATH"] = str(
        PROJECT_ROOT / "data" / "warehouse" / "sec_edgar.duckdb"
    ).replace("\\", "/")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    # Avoid network-dependent dbt telemetry in an offline demonstration.
    environment["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"

    scripts = [] if args.from_cleaned else [
        "verify_ingestion.py", "build_annual_filings.py",
        "build_financial_measures.py",
    ]
    scripts += ["check_financial_measures.py", "load_warehouse.py"]
    stages = [(script, [sys.executable, str(PROJECT_ROOT / "src" / script)])
              for script in scripts]
    dbt_command = [sys.executable, "-m", "dbt.cli.main"]
    dbt_options = ["--project-dir", str(PROJECT_ROOT / "dbt"),
                   "--profiles-dir", str(PROJECT_ROOT / "dbt")]
    stages += [
        ("dbt connection", dbt_command + ["debug"] + dbt_options),
        ("dbt build and tests", dbt_command + ["build"] + dbt_options),
        ("export_reporting.py", [sys.executable,
                                 str(PROJECT_ROOT / "src" / "export_reporting.py")]),
    ]
    code = 1
    try:
        with (logs / f"pipeline_{run_id}.log").open("w", encoding="utf-8") as log:
            for name, command in stages:
                record = {"name": name, "started_at_utc": utc_now()}
                summary["stages"].append(record)
                try:
                    run_stage(name, command, environment, log)
                except Exception:
                    record["status"] = "failed"
                    raise
                else:
                    record["status"] = "success"
                finally:
                    record["completed_at_utc"] = utc_now()

        output = PROJECT_ROOT / "data" / "reporting" / "annual_financials.csv"
        content = output.read_bytes()
        summary["output"] = {
            "path": str(output.relative_to(PROJECT_ROOT)),
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        summary["status"] = "success"
        code = 0
    except (Exception, KeyboardInterrupt) as error:
        summary["status"] = "failed"
        summary["error"] = f"{type(error).__name__}: {error}"
        print(f"\nFAILED: {error}")
        print("Do not treat an older reporting CSV as the output of this failed run.")
    finally:
        summary["completed_at_utc"] = utc_now()
        try:
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        finally:
            lock.rmdir()

    print(f"\nRun summary: {summary_path}")
    if code == 0:
        print("SUCCESS: Local pipeline completed. Refresh Power BI Desktop manually.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
