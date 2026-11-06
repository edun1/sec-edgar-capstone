"""Verify snapshots referenced by the latest ingestion summary."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from sec_client import PROJECT_ROOT


def main():
    summaries = sorted(
        (PROJECT_ROOT / "logs").glob("ingestion_*_summary.json")
    )
    if not summaries:
        raise ValueError("No ingestion summary found.")

    summary_path = summaries[-1]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    companies = json.loads(
        (PROJECT_ROOT / "config" / "companies.json").read_text(
            encoding="utf-8-sig"
        )
    )
    expected = {
        (company["cik"], dataset)
        for company in companies
        for dataset in ("submissions", "companyfacts")
    }

    results = summary["results"]
    actual = [(item["cik"], item["dataset"]) for item in results]

    if len(actual) != len(set(actual)):
        raise ValueError("Duplicate company/dataset results in summary.")

    if set(actual) != expected:
        raise ValueError("Run results do not match configured datasets.")

    verified = 0

    for item in results:
        if item["status"] != "success":
            raise ValueError(
                f"Failed extraction: {item['ticker']} {item['dataset']}"
            )

        metadata = item["metadata"]
        retrieved_at = datetime.fromisoformat(
            metadata["retrieved_at_utc"]
        )
        snapshot_id = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")

        snapshot_dir = (
            PROJECT_ROOT / "data" / "raw"
            / item["dataset"] / item["cik"] / snapshot_id
        )

        saved_metadata = json.loads(
            (snapshot_dir / "metadata.json").read_text(encoding="utf-8")
        )
        if saved_metadata != metadata:
            raise ValueError(f"Metadata mismatch: {snapshot_dir}")

        raw_bytes = (snapshot_dir / "response.json").read_bytes()

        if len(raw_bytes) != metadata["size_bytes"]:
            raise ValueError(f"File size mismatch: {snapshot_dir}")

        digest = hashlib.sha256(raw_bytes).hexdigest()
        if digest != metadata["sha256"]:
            raise ValueError(f"Hash mismatch: {snapshot_dir}")

        payload = json.loads(raw_bytes)
        if str(payload.get("cik", "")).zfill(10) != item["cik"]:
            raise ValueError(f"Company identifier mismatch: {snapshot_dir}")

        verified += 1
        print(
            f"PASS: {item['ticker']} {item['dataset']} "
            f"({len(raw_bytes):,} bytes)"
        )

    print(f"\nRun: {summary['run_id']}")
    print(f"SUCCESS: {verified}/{len(expected)} snapshots verified.")
    print("No API requests were made.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)