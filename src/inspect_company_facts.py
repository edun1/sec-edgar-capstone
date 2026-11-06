"""Inspect the latest saved Apple company facts snapshot offline."""

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = PROJECT_ROOT / "data" / "raw" / "companyfacts" / "0000320193"

CANDIDATES = {
    "Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "Net income": ["NetIncomeLoss"],
    "Assets": ["Assets"],
    "Liabilities": ["Liabilities"],
    "Equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "Operating cash flow": ["NetCashProvidedByUsedInOperatingActivities"],
}


def main():
    snapshots = sorted(RAW_ROOT.glob("*/response.json"))
    if not snapshots:
        raise ValueError("No saved company facts response found.")

    raw_path = snapshots[-1]
    metadata_path = raw_path.parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    raw_bytes = raw_path.read_bytes()

    actual_hash = hashlib.sha256(raw_bytes).hexdigest()
    if actual_hash != metadata["sha256"]:
        raise ValueError("Integrity check failed: saved response has changed.")

    payload = json.loads(raw_bytes)
    facts = payload["facts"]["us-gaap"]

    print(f"Company: {payload['entityName']}")
    print(f"Snapshot: {raw_path.parent.name}")
    print("Integrity check: PASS")

    for measure, tags in CANDIDATES.items():
        print(f"\n{measure}")

        for tag in tags:
            concept = facts.get(tag)
            if concept is None:
                print(f"  NOT PRESENT: {tag}")
                continue

            usd_records = concept.get("units", {}).get("USD", [])
            annual_records = [
                record
                for record in usd_records
                if record.get("form") in {"10-K", "10-K/A"}
            ]

            print(f"  FOUND: {tag}")
            print(f"  USD observations in annual filings: {len(annual_records)}")

            if annual_records:
                sample = max(
                    annual_records,
                    key=lambda record: (
                        record.get("filed", ""),
                        record.get("end", ""),
                        record.get("start", ""),
                        record.get("accn", ""),
                    ),
                )

                print("  Example observation:")
                for field in [
                    "start", "end", "val", "filed",
                    "fy", "fp", "form", "accn", "frame",
                ]:
                    if field in sample:
                        print(f"    {field}: {sample[field]}")

    print("\nInspection complete. No API requests were made.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)