"""Load an isolated SQL build, then publish only after dbt tests pass."""
import argparse
import csv
import json
import os
from pathlib import Path
import re
import struct
import uuid


def run_schema(value):
    if not re.fullmatch(r"run_[a-f0-9]{32}", value):
        raise ValueError("Unexpected run schema")
    return value


def connect():
    import pyodbc
    from azure.identity import AzureCliCredential
    server, database = os.environ["AZURE_SQL_HOST"], os.environ["AZURE_SQL_DATABASE"]
    if not re.fullmatch(r"[a-z0-9-]+\.database\.windows\.net", server):
        raise ValueError("Expected an Azure public-cloud SQL hostname")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", database):
        raise ValueError("Unexpected database name")
    with AzureCliCredential() as credential:
        token = credential.get_token("https://database.windows.net/.default").token.encode("utf-16-le")
    packed = struct.pack(f"<I{len(token)}s", len(token), token)
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER=tcp:{server},1433;"
        f"DATABASE={database};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;",
        attrs_before={1256: packed}, autocommit=False,
    )


def bootstrap(object_id):
    # Run once as the configured Entra SQL administrator. No Graph directory lookup.
    sid = uuid.UUID(object_id).bytes_le.hex()
    with connect() as cn:
        cur = cn.cursor()
        cur.execute("IF SCHEMA_ID('analytics') IS NULL EXEC('CREATE SCHEMA analytics')")
        cur.execute(f"IF USER_ID('edgar_pipeline') IS NULL CREATE USER [edgar_pipeline] WITH SID = 0x{sid}, TYPE = E")
        cur.execute("GRANT CREATE SCHEMA, CREATE TABLE, CREATE VIEW TO [edgar_pipeline]")
        cur.execute("GRANT ALTER, SELECT, INSERT, UPDATE, DELETE ON SCHEMA::analytics TO [edgar_pipeline]")
        cn.commit()
    print("Pipeline database principal provisioned")


def load():
    schema = run_schema(os.environ["EDGAR_RUN_SCHEMA"])
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(f"CREATE SCHEMA [{schema}]")
        for filename, table, expected in [("annual_filings.csv", "raw_annual_filings", 15),
                                          ("financial_measures.csv", "raw_financial_measures", 90)]:
            with (Path("data/cleaned") / filename).open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                columns, rows = reader.fieldnames, list(reader)
            if len(rows) != expected or not columns:
                raise ValueError("Unexpected cleaned dataset shape")
            if any(not re.fullmatch(r"[a-z_]+", col) for col in columns):
                raise ValueError("Invalid CSV column name")
            definitions = ', '.join(f'[{col}] nvarchar(256) NULL' for col in columns)
            cur.execute(f"CREATE TABLE [{schema}].[{table}] ({definitions})")
            placeholders = ','.join('?' for _ in columns)
            cur.executemany(f"INSERT INTO [{schema}].[{table}] VALUES ({placeholders})",
                            [tuple(row[col] or None for col in columns) for row in rows])
        cn.commit()
    print(f"Loaded isolated SQL staging tables in {schema}")


def publish():
    schema = run_schema(os.environ["EDGAR_RUN_SCHEMA"])
    manifest = json.loads(Path("data/cloud_manifest.json").read_text())
    if schema != f"run_{manifest['request_id']}" or manifest.get("status") != "complete":
        raise ValueError("SQL build does not match the ingestion manifest")
    with connect() as cn:
        cur = cn.cursor()
        cur.execute(f"SELECT COUNT(*), COUNT(DISTINCT cik) FROM [{schema}].[annual_financials]")
        if tuple(cur.fetchone()) != (15, 3):
            raise ValueError("Unexpected reporting coverage")
        cur.execute(f"SELECT DISTINCT source_run_id FROM [{schema}].[annual_financials]")
        if [row[0] for row in cur.fetchall()] != [manifest['ingestion_run_id']]:
            raise ValueError("Reporting run reference does not match source manifest")
        # Stage and replace in the same transaction. Readers keep the prior successful
        # table until publication commits; dbt itself never targets analytics.
        temporary = 'publish_' + manifest['request_id']
        cur.execute(f"SELECT * INTO analytics.[{temporary}] FROM [{schema}].[annual_financials]")
        cur.execute("DROP TABLE IF EXISTS analytics.annual_financials")
        cur.execute(f"EXEC sp_rename N'analytics.{temporary}', N'annual_financials', N'OBJECT'")
        cn.commit()
    print("Published tested analytics.annual_financials for Power BI")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["bootstrap", "load", "publish"])
    parser.add_argument("--principal-object-id")
    args = parser.parse_args()
    if args.action == "bootstrap":
        if not args.principal_object_id:
            parser.error("bootstrap needs --principal-object-id")
        bootstrap(args.principal_object_id)
    elif args.action == "load":
        load()
    else:
        publish()
