"""Run SEC ingestion for all configured companies."""

import json
import logging
from datetime import datetime, timezone

import requests

from sec_client import PROJECT_ROOT, SECClient


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                log_dir / f"ingestion_{run_id}.log",
                encoding="utf-8",
            ),
        ],
    )
    logger = logging.getLogger(__name__)

    config_path = PROJECT_ROOT / "config" / "companies.json"
    companies = json.loads(config_path.read_text(encoding="utf-8-sig"))

    if not isinstance(companies, list) or not companies:
        raise ValueError("Company configuration must be a non-empty list.")

    seen_ciks = set()
    for company in companies:
        if not isinstance(company, dict):
            raise ValueError("Each company must be a JSON object.")

        cik = company.get("cik")
        ticker = company.get("ticker")
        if (
            not isinstance(cik, str)
            or len(cik) != 10
            or not cik.isdigit()
            or not isinstance(ticker, str)
            or not ticker.strip()
        ):
            raise ValueError("Each company needs a ticker and 10-digit CIK.")

        if cik in seen_ciks:
            raise ValueError(f"Duplicate company CIK: {cik}")
        seen_ciks.add(cik)

    results = []
    client = SECClient()

    try:
        for company in companies:
            for dataset in ("submissions", "companyfacts"):
                ticker = company["ticker"]
                cik = company["cik"]

                logger.info("Starting ticker=%s dataset=%s", ticker, dataset)

                try:
                    metadata = client.download(cik, dataset)
                except (requests.RequestException, ValueError, OSError) as error:
                    logger.exception(
                        "Failed ticker=%s dataset=%s", ticker, dataset
                    )
                    results.append({
                        "ticker": ticker,
                        "cik": cik,
                        "dataset": dataset,
                        "status": "failed",
                        "error": str(error),
                    })
                else:
                    results.append({
                        "ticker": ticker,
                        "cik": cik,
                        "dataset": dataset,
                        "status": "success",
                        "metadata": metadata,
                    })
    finally:
        client.close()

    successful = sum(item["status"] == "success" for item in results)
    failed = len(results) - successful

    summary = {
        "run_id": run_id,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "successful": successful,
        "failed": failed,
        "results": results,
    }

    summary_path = log_dir / f"ingestion_{run_id}_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    logger.info(
        "FINISHED: successful=%s failed=%s", successful, failed
    )
    logger.info("Run summary: %s", summary_path)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())