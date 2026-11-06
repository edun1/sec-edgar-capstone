"""Download and preserve Apple's SEC submissions response."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CIK = "0000320193"
URL = f"https://data.sec.gov/submissions/CIK{CIK}.json"


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()

    if (
        not user_agent
        or "your-email@example.com" in user_agent
        or "@" not in user_agent
    ):
        raise ValueError("Set SEC_USER_AGENT with your contact email in .env.")

    print("Requesting Apple's SEC submissions...")

    response = requests.get(
        URL,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
        timeout=(10, 60),
    )
    print(f"HTTP status: {response.status_code}")
    response.raise_for_status()

    payload = response.json()

    # Validate the company and expected structure before saving.
    if str(payload.get("cik", "")).zfill(10) != CIK:
        raise ValueError("The response does not match the requested company.")

    recent = payload.get("filings", {}).get("recent")
    if not isinstance(recent, dict):
        raise ValueError("The response is missing recent filing metadata.")

    retrieved_at = datetime.now(timezone.utc)
    run_id = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")

    output_dir = (
        PROJECT_ROOT / "data" / "raw" / "submissions" / CIK / run_id
    )
    output_dir.mkdir(parents=True, exist_ok=False)

    # Preserve the response content without reformatting its JSON.
    raw_path = output_dir / "response.json"
    raw_path.write_bytes(response.content)

    metadata = {
        "source_url": URL,
        "cik": CIK,
        "retrieved_at_utc": retrieved_at.isoformat(),
        "http_status": response.status_code,
        "content_type": response.headers.get("Content-Type"),
        "size_bytes": len(response.content),
        "sha256": hashlib.sha256(response.content).hexdigest(),
    }

    metadata_path = output_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"Company: {payload.get('name')}")
    print(f"Recent filings: {len(recent.get('accessionNumber', []))}")
    print(f"Raw response saved: {raw_path.relative_to(PROJECT_ROOT)}")
    print(f"Metadata saved: {metadata_path.relative_to(PROJECT_ROOT)}")
    print("SUCCESS: First SEC extraction completed.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, ValueError, OSError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1)