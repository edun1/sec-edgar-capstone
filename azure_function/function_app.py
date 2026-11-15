import azure.functions as func
import logging

app = func.FunctionApp()


@app.route(route="ingest", methods=["POST"])
def ingest(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("SEC ingestion function was called.")

    return func.HttpResponse(
        "SEC ingestion function is ready.",
        status_code=200
    )
