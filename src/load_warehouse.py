"""Load validated CSV datasets into the local DuckDB warehouse."""

import subprocess
import sys

import duckdb

from sec_client import PROJECT_ROOT


def main():
    # Stop loading if the existing financial quality checks fail.
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "src" / "check_financial_measures.py"),
        ],
        check=True,
    )

    database_path = PROJECT_ROOT / "data" / "warehouse" / "sec_edgar.duckdb"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    datasets = {
        "annual_filings": (
            PROJECT_ROOT / "data" / "cleaned" / "annual_filings.csv"
        ),
        "financial_measures": (
            PROJECT_ROOT / "data" / "cleaned" / "financial_measures.csv"
        ),
    }

    connection = duckdb.connect(str(database_path))

    try:
        connection.execute("BEGIN TRANSACTION").fetchall()
        connection.execute("CREATE SCHEMA IF NOT EXISTS landing").fetchall()

        for table, path in datasets.items():
            # Load every CSV field as text to preserve source formatting,
            # including leading zeros in CIK identifiers.
            relation = connection.read_csv(
                str(path),
                header=True,
                all_varchar=True,
            )
            connection.register("incoming_csv", relation)

            connection.execute(
                f"""
                CREATE OR REPLACE TABLE landing.{table} AS
                SELECT * FROM incoming_csv
                """
            ).fetchall()
            connection.unregister("incoming_csv")

            count = connection.execute(
                f"SELECT COUNT(*) FROM landing.{table}"
            ).fetchall()[0][0]

            print(f"LOADED: landing.{table} | rows={count}")

        filings_count = connection.execute(
            "SELECT COUNT(*) FROM landing.annual_filings"
        ).fetchall()[0][0]

        measures_count = connection.execute(
            "SELECT COUNT(*) FROM landing.financial_measures"
        ).fetchall()[0][0]

        if filings_count != 15 or measures_count != 90:
            raise ValueError("Unexpected warehouse row counts.")

        connection.execute("COMMIT")

    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()

    print(f"Database: {database_path}")
    print("SUCCESS: Local warehouse loaded.")


if __name__ == "__main__":
    main()