import json
import logging
import sys
from pathlib import Path

import azure.functions as func

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_FOLDER = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SRC_FOLDER) not in sys.path:
    sys.path.insert(0, str(SRC_FOLDER))
from run_ingestion import main as run_sec_ingestion


app = func.FunctionApp()


@app.route(route="ingest", methods=["POST"])
def ingest(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SEC ingestion function was triggered.")

    try:
        result = run_sec_ingestion()

        if result["failed"] == 0:
            status = "success"
            status_code = 200
        else:
            status = "failed"
            status_code = 500

        response = {
            "status": status,
            "run_id": result["run_id"],
            "completed_at_utc": result["completed_at_utc"],
            "successful": result["successful"],
            "failed": result["failed"],
            "results": result["results"],
        }

        return func.HttpResponse(
            json.dumps(response, indent=2),
            status_code=status_code,
            mimetype="application/json",
        )

    except Exception:
        logging.exception("SEC ingestion failed.")

        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "SEC ingestion encountered an unexpected error.",
            }),
            status_code=500,
            mimetype="application/json",
        )
