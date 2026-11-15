"""Queue-triggered SEC extraction. Publishes one complete, hash-addressed run."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import threading

import azure.functions as func
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient

app = func.FunctionApp()


def validate_request_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("request_id must be a 32-character lowercase hex UUID")
    return value


@app.queue_trigger(arg_name="message", queue_name="ingestion-requests", connection="AzureWebJobsStorage")
def ingest(message: func.QueueMessage):
    request_id = validate_request_id(json.loads(message.get_body())["request_id"])
    credential = DefaultAzureCredential()
    service = BlobServiceClient(os.environ["EDGAR_LAKE_URL"], credential=credential)
    container = service.get_container_client(os.getenv("EDGAR_CONTAINER", "edgar"))
    lock = container.get_blob_client(f"locks/{request_id}")
    try:
        lock.upload_blob(b"lock", overwrite=False)
    except ResourceExistsError:
        pass
    # Lease renewals protect against duplicate delivery; expiry permits recovery after a crash.
    lease = lock.acquire_lease(lease_duration=60)
    stopped = threading.Event()
    lease_error = []

    def renew():
        while not stopped.wait(20):
            try:
                lease.renew()
            except Exception as error:
                lease_error.append(error)
                return

    thread = threading.Thread(target=renew, daemon=True)
    thread.start()
    manifest_blob = container.get_blob_client(f"runs/{request_id}/manifest.json")
    try:
        try:
            previous = json.loads(manifest_blob.download_blob().readall())
            if previous.get("status") == "complete":
                logging.info("Already completed request %s", request_id)
                return
        except ResourceNotFoundError:
            pass

        with tempfile.TemporaryDirectory(prefix="edgar-") as folder:
            workspace = Path(folder)
            bundle = Path(__file__).resolve().parent
            shutil.copytree(bundle / "src", workspace / "src")
            shutil.copytree(bundle / "config", workspace / "config")
            env = os.environ.copy()
            env["SEC_EDGAR_PROJECT_ROOT"] = str(workspace)
            env["PYTHONIOENCODING"] = "utf-8"
            for script in ["run_ingestion.py", "verify_ingestion.py", "ingest_submission_history.py",
                           "build_annual_filings.py", "build_financial_measures.py", "check_financial_measures.py"]:
                # Bounded output: private settings are never explicitly printed.
                subprocess.run([sys.executable, str(workspace / "src" / script)],
                               env=env, cwd=workspace, check=True, timeout=900)
            if lease_error:
                raise RuntimeError("Lost the ingestion request lease")
            files = []
            for subdir in ["data", "logs"]:
                for path in sorted((workspace / subdir).rglob("*")):
                    if path.is_file():
                        content = path.read_bytes()
                        relative = path.relative_to(workspace).as_posix()
                        blob_path = f"runs/{request_id}/{relative}"
                        container.upload_blob(blob_path, content, overwrite=True)
                        files.append({"path": relative, "blob": blob_path,
                                      "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
            summary_path = next((workspace / "logs").glob("ingestion_*_summary.json"))
            summary = json.loads(summary_path.read_text())
            if lease_error:
                raise RuntimeError("Lost the ingestion request lease")
            manifest = {"request_id": request_id, "status": "complete",
                        "ingestion_run_id": summary["run_id"],
                        "completed_at_utc": datetime.now(timezone.utc).isoformat(), "files": files}
            # Readiness marker is written last, only after all source/cleaned bytes are stored.
            manifest_blob.upload_blob(json.dumps(manifest, indent=2), overwrite=True)
            logging.info("Completed request %s ingestion=%s", request_id, summary["run_id"])
    finally:
        stopped.set()
        thread.join(timeout=5)
        lease.release()
        service.close()
        credential.close()
