"""Inspect annual filing coverage and financial tags offline."""

import hashlib
import json
from datetime import datetime

from sec_client import PROJECT_ROOT

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
    "Operating cash flow": [
        "NetCashProvidedByUsedInOperatingActivities"
    ],
}


def load_snapshot(result):
    if result["status"] != "success":
        raise ValueError("The selected run contains a failed extraction.")

    metadata = result["metadata"]
    timestamp = datetime.fromisoformat(metadata["retrieved_at_utc"])
    snapshot_id = timestamp.strftime("%Y%m%dT%H%M%S%fZ")

    path = (
        PROJECT_ROOT / "data" / "raw"
        / result["dataset"] / result["cik"]
        / snapshot_id / "response.json"
    )
    content = path.read_bytes()

    if hashlib.sha256(content).hexdigest() != metadata["sha256"]:
        raise ValueError(f"Integrity check failed: {path}")

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

    for company in companies:
        cik = company["cik"]
        submissions = load_snapshot(results[(cik, "submissions")])
        companyfacts = load_snapshot(results[(cik, "companyfacts")])

        print(f"\n=== {company['ticker']} | {submissions['name']} ===")
        recent = submissions["filings"]["recent"]
        fields = ["form", "reportDate", "filingDate", "accessionNumber"]

        lengths = [len(recent[field]) for field in fields]
        if len(set(lengths)) != 1:
            raise ValueError("Filing metadata arrays have different lengths.")

        annual_filings = [
            dict(zip(fields, values))
            for values in zip(*(recent[field] for field in fields))
            if values[0] in {"10-K", "10-K/A"}
        ]
        annual_filings.sort(
            key=lambda row: (row["reportDate"], row["filingDate"]),
            reverse=True,
        )

        print("Annual filings in the recent submissions response:")
        for row in annual_filings[:7]:
            print(
                f"  {row['form']} | period end={row['reportDate']} "
                f"| filed={row['filingDate']} "
                f"| accession={row['accessionNumber']}"
            )

        history_files = submissions["filings"].get("files", [])
        print(f"Additional submissions history files: {len(history_files)}")

        facts = companyfacts["facts"]["us-gaap"]
        print("Available candidate tags:")
        for measure, tags in CANDIDATES.items():
            available = [
                tag for tag in tags
                if facts.get(tag, {}).get("units", {}).get("USD")
            ]
            print(f"  {measure}: {', '.join(available) or 'MISSING'}")

    print("\nSUCCESS: Coverage inspection completed offline.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)