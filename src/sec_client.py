"""Shared SEC client for sequential ingestion runs."""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(os.getenv("SEC_EDGAR_PROJECT_ROOT", str(Path(__file__).resolve().parents[1]))).resolve()
LOGGER = logging.getLogger(__name__)


class SECClient:
    def __init__(self):
        load_dotenv(PROJECT_ROOT / ".env")
        user_agent = os.getenv("SEC_USER_AGENT", "").strip()

        if (
            not user_agent
            or "your-email@example.com" in user_agent
            or "@" not in user_agent
        ):
            raise ValueError(
                "Set SEC_USER_AGENT with your contact email in .env."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json",
        })
        self.last_request_started = None

    def close(self):
        self.session.close()

    def _wait_before_request(self):
        # Space request starts at least one second apart in this client.
        if self.last_request_started is not None:
            elapsed = time.monotonic() - self.last_request_started
            time.sleep(max(0, 1.0 - elapsed))

        self.last_request_started = time.monotonic()

    def download(self, cik, dataset):
        if not isinstance(cik, str) or len(cik) != 10 or not cik.isdigit():
            raise ValueError("CIK must be a string containing 10 digits.")

        urls = {
            "submissions": (
                f"https://data.sec.gov/submissions/CIK{cik}.json"
            ),
            "companyfacts": (
                f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            ),
        }

        if dataset not in urls:
            raise ValueError(f"Unsupported dataset: {dataset}")

        url = urls[dataset]
        retryable_statuses = {429, 500, 502, 503, 504}
        max_attempts = 4

        for attempt in range(1, max_attempts + 1):
            self._wait_before_request()
            LOGGER.info(
                "Request dataset=%s cik=%s attempt=%s",
                dataset, cik, attempt,
            )

            try:
                response = self.session.get(url, timeout=(10, 120))
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt == max_attempts:
                    raise

                delay = 2 ** attempt
                LOGGER.warning(
                    "Network failure (%s); retrying in %s seconds",
                    type(error).__name__, delay,
                )
                time.sleep(delay)
                continue

            if response.status_code in retryable_statuses:
                if attempt == max_attempts:
                    response.raise_for_status()

                # Honour Retry-After when supplied by the server.
                retry_after = response.headers.get("Retry-After")
                delay = 2 ** attempt
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        from email.utils import parsedate_to_datetime

                        try:
                            retry_at = parsedate_to_datetime(retry_after)
                            seconds = (
                                retry_at - datetime.now(timezone.utc)
                            ).total_seconds()
                            delay = max(delay, seconds)
                        except (ValueError, TypeError, OverflowError):
                            pass

                LOGGER.warning(
                    "HTTP %s; retrying in %.1f seconds",
                    response.status_code, delay,
                )
                response.close()
                time.sleep(delay)
                continue

            # Other errors, including 403 and 404, fail without retrying.
            response.raise_for_status()
            break

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")

        if str(payload.get("cik", "")).zfill(10) != cik:
            raise ValueError("Response CIK does not match the requested CIK.")

        if dataset == "submissions":
            recent = payload.get("filings", {}).get("recent")
            if not isinstance(recent, dict):
                raise ValueError("Missing recent filing metadata.")
        else:
            concepts = payload.get("facts", {}).get("us-gaap")
            if not isinstance(concepts, dict) or not concepts:
                raise ValueError("Missing US GAAP financial concepts.")

        retrieved_at = datetime.now(timezone.utc)
        snapshot_id = retrieved_at.strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = (
            PROJECT_ROOT / "data" / "raw" / dataset / cik / snapshot_id
        )
        output_dir.mkdir(parents=True, exist_ok=False)

        raw_path = output_dir / "response.json"
        raw_path.write_bytes(response.content)

        metadata = {
            "source_url": url,
            "cik": cik,
            "dataset": dataset,
            "retrieved_at_utc": retrieved_at.isoformat(),
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type"),
            "size_bytes": len(response.content),
            "sha256": hashlib.sha256(response.content).hexdigest(),
        }

        # Write metadata last to mark a completed snapshot.
        (output_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )

        LOGGER.info(
            "Saved dataset=%s cik=%s bytes=%s path=%s",
            dataset, cik, len(response.content),
            raw_path.relative_to(PROJECT_ROOT),
        )
        response.close()
        return metadata