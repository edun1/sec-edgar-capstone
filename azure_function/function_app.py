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

        if result == 0:
            return func.HttpResponse(
                "SEC ingestion completed successfully.",
                status_code=200
            )

        return func.HttpResponse(
            "SEC ingestion finished with failures. Check the logs and run summary.",
            status_code=500
        )

    except Exception:
        logging.exception("SEC ingestion failed.")
        return func.HttpResponse(
            "SEC ingestion encountered an unexpected error.",
            status_code=500
        )
