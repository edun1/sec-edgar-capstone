"""Verify annual reporting coverage and export data for Power BI."""

import csv
from collections import Counter

import duckdb

from sec_client import PROJECT_ROOT


def main():
    database = PROJECT_ROOT / "data" / "warehouse" / "sec_edgar.duckdb"
    output_dir = PROJECT_ROOT / "data" / "reporting"
    output_dir.mkdir(parents=True, exist_ok=True)

    with (
        PROJECT_ROOT / "data" / "cleaned" / "annual_filings.csv"
    ).open(newline="", encoding="utf-8") as handle:
        filings = list(csv.DictReader(handle))

    expected_keys = {
        (row["cik"], row["period_end"]) for row in filings
    }

    connection = duckdb.connect(str(database), read_only=True)

    try:
        cursor = connection.execute("""
            SELECT *
            FROM analytics.annual_financials
            ORDER BY ticker, period_end
        """)
        columns = [description[0] for description in cursor.description]
        records = [
            dict(zip(columns, values))
            for values in cursor.fetchall()
        ]

        actual_keys = [
            (row["cik"], row["period_end"].isoformat())
            for row in records
        ]

        if len(actual_keys) != len(set(actual_keys)):
            raise ValueError("Duplicate company/period reporting rows.")

        if set(actual_keys) != expected_keys:
            raise ValueError("Reporting periods differ from selected filings.")

        counts = Counter(row["ticker"] for row in records)
        for ticker, count in sorted(counts.items()):
            print(f"PASS: {ticker} | annual reporting rows={count}")

        for ticker in counts:
            company_rows = [
                row for row in records if row["ticker"] == ticker
            ]
            earliest = min(company_rows, key=lambda row: row["period_end"])

            for row in company_rows:
                growth = row["revenue_growth_pct"]
                if row is earliest:
                    if growth is not None:
                        raise ValueError(
                            f"{ticker}: earliest period should have blank growth."
                        )
                elif growth is None:
                    raise ValueError(
                        f"{ticker}: unexpected missing revenue growth."
                    )

        output_path = output_dir / "annual_financials.csv"

        # Write to a temporary file before replacing the published export.
        temporary_path = output_dir / "annual_financials.csv.tmp"
        with temporary_path.open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)

        temporary_path.replace(output_path)

        print(f"\nSUCCESS: Exported {len(records)} reporting rows.")
        print(f"Output: {output_path.relative_to(PROJECT_ROOT)}")
        print("Amounts are in USD; percentage columns use a 0-100 scale.")

    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, duckdb.Error) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)