"""Download Alphabet's additional SEC submissions history."""

import hashlib
import json
import logging
import re
from datetime import datetime, timezone

import requests

from inspect_coverage import load_snapshot
from sec_client import PROJECT_ROOT, SECClient


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    summaries = sorted(
        (PROJECT_ROOT / "logs").glob("ingestion_*_summary.json")
    )
    if not summaries:
        raise ValueError("No ingestion summary found.")

    summary = json.loads(summaries[-1].read_text(encoding="utf-8"))
    cik = "0001652044"

    matches = [
        item for item in summary["results"]
        if item["cik"] == cik and item["dataset"] == "submissions"
    ]
    if len(matches) != 1:
        raise ValueError("Expected one Alphabet submissions result.")

    submissions = load_snapshot(matches[0])
    history_files = submissions["filings"].get("files", [])

    if not history_files:
        raise ValueError("No additional history files were referenced.")

    client = SECClient()
    downloaded = 0

    try:
        for history in history_files:
            filename = history["name"]

            if not re.fullmatch(
                rf"CIK{cik}-submissions-\d+\.json", filename
            ):
                raise ValueError(f"Unexpected filename: {filename}")

            url = f"https://data.sec.gov/submissions/{filename}"

            # One attempt per file, using the client's request spacing.
            client._wait_before_request()
            logging.info("Downloading %s", filename)

            with client.session.get(url, timeout=(10, 120)) as response:
                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, dict):
                    raise ValueError("Expected a history JSON object.")

                fields = [
                    "form",
                    "reportDate",
                    "filingDate",
                    "accessionNumber",
                ]
                if any(
                    not isinstance(payload.get(field), list)
                    for field in fields
                ):
                    raise ValueError("Unexpected history structure.")

                if len({len(payload[field]) for field in fields}) != 1:
                    raise ValueError("History arrays have different lengths.")

                retrieved_at = datetime.now(timezone.utc)
                snapshot_id = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")

                output_dir = (
                    PROJECT_ROOT
                    / "data"
                    / "raw"
                    / "submission_history"
                    / cik
                    / filename.removesuffix(".json")
                    / snapshot_id
                )
                output_dir.mkdir(parents=True, exist_ok=False)

                content = response.content
                (output_dir / "response.json").write_bytes(content)

                metadata = {
                    "source_url": url,
                    "cik": cik,
                    "dataset": "submission_history",
                    "history_filename": filename,
                    "retrieved_at_utc": retrieved_at.isoformat(),
                    "http_status": response.status_code,
                    "content_type": response.headers.get("Content-Type"),
                    "size_bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }

                (output_dir / "metadata.json").write_text(
                    json.dumps(metadata, indent=2),
                    encoding="utf-8",
                )

            downloaded += 1
            annual_count = sum(
                form in {"10-K", "10-K/A"}
                for form in payload["form"]
            )

            print(f"Saved: {filename}")
            print(f"Annual filing entries: {annual_count}")
            print(f"Path: {output_dir.relative_to(PROJECT_ROOT)}")

    finally:
        client.close()

    print(f"SUCCESS: {downloaded} history file(s) downloaded.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError, KeyError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)