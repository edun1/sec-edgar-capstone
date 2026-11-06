"""Check the selected annual financial measures offline."""

import csv
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from sec_client import PROJECT_ROOT

EXPECTED_MEASURES = {
    "revenue",
    "net_income",
    "assets",
    "liabilities",
    "equity",
    "operating_cash_flow",
}

DURATION_MEASURES = {
    "revenue",
    "net_income",
    "operating_cash_flow",
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    cleaned = PROJECT_ROOT / "data" / "cleaned"
    rows = read_csv(cleaned / "financial_measures.csv")
    filings = read_csv(cleaned / "annual_filings.csv")

    companies = json.loads(
        (PROJECT_ROOT / "config" / "companies.json").read_text(
            encoding="utf-8-sig"
        )
    )
    configured = {company["ticker"]: company["cik"] for company in companies}

    filing_lookup = {}
    for filing in filings:
        key = (filing["ticker"], filing["period_end"])
        if key in filing_lookup:
            raise ValueError(f"Duplicate annual filing: {key}")
        filing_lookup[key] = filing

    if {key[0] for key in filing_lookup} != set(configured):
        raise ValueError("Annual filings do not match configured companies.")

    for ticker in configured:
        count = sum(key[0] == ticker for key in filing_lookup)
        if count != 5:
            raise ValueError(f"{ticker}: expected five annual periods.")

    if len(rows) != len(filings) * len(EXPECTED_MEASURES):
        raise ValueError("Unexpected financial measure row count.")

    grouped = defaultdict(dict)

    for row in rows:
        ticker = row["ticker"]
        period_end = row["period_end"]
        measure = row["measure"]
        key = (ticker, period_end)

        if key not in filing_lookup:
            raise ValueError(f"Unexpected company/period: {key}")
        if measure not in EXPECTED_MEASURES:
            raise ValueError(f"Unexpected measure: {measure}")
        if measure in grouped[key]:
            raise ValueError(f"Duplicate measure: {key} {measure}")

        filing = filing_lookup[key]
        if row["cik"] != configured[ticker]:
            raise ValueError(f"Incorrect CIK: {key}")
        for field in ("accession_number", "filing_date", "form"):
            if row[field] != filing[field]:
                raise ValueError(f"Filing reference mismatch: {key} {field}")

        if row["unit"] != "USD":
            raise ValueError(f"Unexpected unit: {key}")
        if row["selection_policy"] != "original_10k":
            raise ValueError(f"Unexpected selection policy: {key}")
        if not row["source_tag"] or not row["source_run_id"]:
            raise ValueError(f"Missing source traceability: {key}")

        value = Decimal(row["value"])
        if not value.is_finite():
            raise ValueError(f"Non-finite value: {key} {measure}")

        end = date.fromisoformat(period_end)
        filed = date.fromisoformat(row["filing_date"])
        if filed < end:
            raise ValueError(f"Filing date precedes period end: {key}")

        if measure in DURATION_MEASURES:
            start = date.fromisoformat(row["period_start"])
            days = (end - start).days + 1
            if not 350 <= days <= 380:
                raise ValueError(f"Invalid annual duration: {key} {measure}")
            if int(row["duration_days"]) != days:
                raise ValueError(f"Duration field mismatch: {key} {measure}")
        elif row["period_start"] or row["duration_days"]:
            raise ValueError(f"Instant measure has a duration: {key} {measure}")

        grouped[key][measure] = (value, row)

    for key in sorted(filing_lookup):
        measures = grouped[key]
        if set(measures) != EXPECTED_MEASURES:
            raise ValueError(f"Incomplete measure set: {key}")

        starts = {
            measures[measure][1]["period_start"]
            for measure in DURATION_MEASURES
        }
        if len(starts) != 1:
            raise ValueError(f"Inconsistent duration periods: {key}")

        assets = measures["assets"][0]
        liabilities = measures["liabilities"][0]
        equity = measures["equity"][0]
        difference = assets - liabilities - equity

        # Explicit absolute tolerance of one US dollar.
        if abs(difference) > Decimal("1"):
            raise ValueError(
                f"Balance sheet mismatch: {key}; difference={difference}"
            )

        print(
            f"PASS: {key[0]} {key[1]} "
            f"| six measures | balance difference USD {difference}"
        )

    print(f"\nSUCCESS: Quality checks passed for {len(rows)} rows.")
    print("Checks assess internal consistency, not source-filing accuracy.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, InvalidOperation) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)