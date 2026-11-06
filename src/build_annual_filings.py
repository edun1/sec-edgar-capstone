"""Build a five-period annual filing selection for each company."""

import csv
import hashlib
import json
from pathlib import Path

from inspect_coverage import load_snapshot
from sec_client import PROJECT_ROOT

FIELDS = ["form", "reportDate", "filingDate", "accessionNumber"]


def filing_rows(payload):
    arrays = [payload.get(field) for field in FIELDS]
    if any(not isinstance(values, list) for values in arrays):
        raise ValueError("Missing filing arrays.")
    if len({len(values) for values in arrays}) != 1:
        raise ValueError("Filing arrays have different lengths.")
    return [dict(zip(FIELDS, values)) for values in zip(*arrays)]


def load_history(path):
    metadata = json.loads(
        (path.parent / "metadata.json").read_text(encoding="utf-8")
    )
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise ValueError(f"History integrity check failed: {path}")
    return json.loads(content)


def main():
    summaries = sorted(
        (PROJECT_ROOT / "logs").glob("ingestion_*_summary.json")
    )
    if not summaries:
        raise ValueError("No ingestion summary found.")

    summary = json.loads(summaries[-1].read_text(encoding="utf-8"))
    results = {
        (item["cik"], item["dataset"]): item
        for item in summary["results"]
    }
    companies = json.loads(
        (PROJECT_ROOT / "config" / "companies.json").read_text(
            encoding="utf-8-sig"
        )
    )

    selected = []

    for company in companies:
        cik = company["cik"]
        submissions = load_snapshot(results[(cik, "submissions")])
        rows = filing_rows(submissions["filings"]["recent"])

        history_root = (
            PROJECT_ROOT / "data" / "raw" / "submission_history" / cik
        )

        # Include the latest completed snapshot of each referenced file.
        for history in submissions["filings"].get("files", []):
            history_dir = history_root / Path(history["name"]).stem
            snapshots = sorted(
                path for path in history_dir.glob("*/response.json")
                if (path.parent / "metadata.json").exists()
            )
            if snapshots:
                rows.extend(filing_rows(load_history(snapshots[-1])))

        by_accession = {}
        for row in rows:
            accession = row["accessionNumber"]
            if accession in by_accession and by_accession[accession] != row:
                raise ValueError(f"Conflicting filing metadata: {accession}")
            by_accession[accession] = row

        originals = [
            row for row in by_accession.values()
            if row["form"] == "10-K" and row["reportDate"]
        ]

        by_period = {}
        for row in originals:
            period = row["reportDate"]
            if period in by_period:
                raise ValueError(
                    f"Multiple original 10-Ks for {company['ticker']} {period}"
                )
            by_period[period] = row

        periods = sorted(by_period, reverse=True)[:5]
        if len(periods) != 5:
            raise ValueError(
                f"Insufficient annual history for {company['ticker']}"
            )

        print(f"\n{company['ticker']}:")
        for period in periods:
            row = by_period[period]
            selected.append({
                "ticker": company["ticker"],
                "cik": cik,
                "period_end": period,
                "filing_date": row["filingDate"],
                "form": row["form"],
                "accession_number": row["accessionNumber"],
            })
            print(f"  Period end: {period} | filed: {row['filingDate']}")

    output = PROJECT_ROOT / "data" / "cleaned" / "annual_filings.csv"
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)

    print(f"\nSUCCESS: {len(selected)} annual filing rows saved.")
    print(f"Output: {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)