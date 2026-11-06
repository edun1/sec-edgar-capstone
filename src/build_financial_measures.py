"""Select annual financial measures from original 10-K filings."""

import csv
import json
from datetime import date

from inspect_coverage import load_snapshot
from sec_client import PROJECT_ROOT

MEASURES = {
    "revenue": {
        "type": "duration",
        "tags": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ],
    },
    "net_income": {
        "type": "duration",
        "tags": ["NetIncomeLoss"],
    },
    "assets": {
        "type": "instant",
        "tags": ["Assets"],
    },
    "liabilities": {
        "type": "instant",
        "tags": ["Liabilities"],
    },
    "equity": {
        "type": "instant",
        "tags": ["StockholdersEquity"],
    },
    "operating_cash_flow": {
        "type": "duration",
        "tags": ["NetCashProvidedByUsedInOperatingActivities"],
    },
}


def select_observation(facts, filing, definition):
    # Tags are checked in the explicit priority order above.
    for tag in definition["tags"]:
        observations = facts.get(tag, {}).get("units", {}).get("USD", [])
        matches = []

        for observation in observations:
            if (
                observation.get("accn") != filing["accession_number"]
                or observation.get("end") != filing["period_end"]
                or observation.get("form") != "10-K"
                or observation.get("filed") != filing["filing_date"]
            ):
                continue

            if definition["type"] == "duration":
                start = observation.get("start")
                if not start:
                    continue

                duration_days = (
                    date.fromisoformat(observation["end"])
                    - date.fromisoformat(start)
                ).days + 1

                if not 350 <= duration_days <= 380:
                    continue
            else:
                if observation.get("start"):
                    continue
                duration_days = None

            matches.append((observation, duration_days))

        if not matches:
            continue

        # Identical repeated observations are acceptable; conflicts are not.
        signatures = {
            (
                observation.get("start"),
                observation["end"],
                observation["val"],
            )
            for observation, _ in matches
        }
        if len(signatures) != 1:
            raise ValueError(
                f"Conflicting observations: {filing['ticker']} "
                f"{filing['period_end']} {tag}"
            )

        observation, duration_days = matches[0]
        return tag, observation, duration_days

    raise ValueError(
        f"No suitable observation: {filing['ticker']} "
        f"{filing['period_end']} {definition['tags']}"
    )


def main():
    filing_path = PROJECT_ROOT / "data" / "cleaned" / "annual_filings.csv"
    with filing_path.open(newline="", encoding="utf-8") as handle:
        filings = list(csv.DictReader(handle))

    if not filings:
        raise ValueError("Annual filing selection is empty.")

    summaries = sorted(
        (PROJECT_ROOT / "logs").glob("ingestion_*_summary.json")
    )
    if not summaries:
        raise ValueError("No ingestion summary found.")

    summary = json.loads(summaries[-1].read_text(encoding="utf-8"))
    facts_by_cik = {}

    for result in summary["results"]:
        if result["dataset"] == "companyfacts":
            payload = load_snapshot(result)
            facts_by_cik[result["cik"]] = payload["facts"]["us-gaap"]

    rows = []

    for filing in filings:
        facts = facts_by_cik[filing["cik"]]
        period_rows = []

        for measure, definition in MEASURES.items():
            tag, observation, duration_days = select_observation(
                facts, filing, definition
            )

            period_rows.append({
                "ticker": filing["ticker"],
                "cik": filing["cik"],
                "period_end": filing["period_end"],
                "period_start": observation.get("start", ""),
                "duration_days": duration_days or "",
                "measure": measure,
                "value": observation["val"],
                "unit": "USD",
                "source_tag": tag,
                "filing_date": filing["filing_date"],
                "accession_number": filing["accession_number"],
                "form": filing["form"],
                "selection_policy": "original_10k",
                "source_run_id": summary["run_id"],
            })

        duration_starts = {
            row["period_start"]
            for row in period_rows
            if row["period_start"]
        }
        if len(duration_starts) != 1:
            raise ValueError(
                f"Duration measures have different starts: "
                f"{filing['ticker']} {filing['period_end']}"
            )

        rows.extend(period_rows)
        print(
            f"PASS: {filing['ticker']} {filing['period_end']} "
            f"| {len(period_rows)} measures"
        )

    output = PROJECT_ROOT / "data" / "cleaned" / "financial_measures.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSUCCESS: {len(rows)} financial measure rows saved.")
    print(f"Output: {output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)