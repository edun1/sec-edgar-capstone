"""Submit one ingestion request and download only its verified cleaned files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid


def verify_manifest(manifest, request_id):
    if manifest.get("request_id") != request_id or manifest.get("status") != "complete":
        raise ValueError("Manifest is not the requested completed run")
    paths = [record["path"] for record in manifest["files"]]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate manifest file paths")
    required = {"data/cleaned/annual_filings.csv", "data/cleaned/financial_measures.csv"}
    if not required.issubset(paths):
        raise ValueError("Completed manifest is missing cleaned datasets")
    for record in manifest["files"]:
        if record["blob"] != f"runs/{request_id}/{record['path']}":
            raise ValueError("Blob path does not belong to the requested run")
        if not re.fullmatch(r"[a-f0-9]{64}", record["sha256"]):
            raise ValueError("Invalid hash in manifest")
    return required


def main():
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient
    from azure.storage.queue import QueueClient

    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    request_id = uuid.uuid4().hex
    credential = AzureCliCredential()
    service = BlobServiceClient(f"https://{os.environ['AZURE_LAKE_STORAGE']}.blob.core.windows.net", credential=credential)
    container = service.get_container_client("edgar")
    with QueueClient(f"https://{os.environ['AZURE_HOST_STORAGE']}.queue.core.windows.net", "ingestion-requests", credential=credential) as queue:
        queue.send_message(json.dumps({"request_id": request_id}))
    print(f"Requested ingestion: {request_id}", flush=True)
    start = time.monotonic()
    while time.monotonic() - start < args.timeout:
        try:
            manifest = json.loads(container.download_blob(f"runs/{request_id}/manifest.json").readall())
            required = verify_manifest(manifest, request_id)
            break
        except ResourceNotFoundError:
            time.sleep(15)
    else:
        raise TimeoutError("No completed ingestion manifest; inspect Function logs and ingestion-requests-poison queue")

    root = Path.cwd()
    for record in manifest["files"]:
        if record["path"] in required:
            content = container.download_blob(record["blob"]).readall()
            if len(content) != record["bytes"] or hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise ValueError("Downloaded dataset failed integrity verification")
            path = root / record["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    (root / "data/cloud_manifest.json").write_text(json.dumps(manifest, indent=2))
    schema = f"run_{request_id}"
    if os.getenv("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a") as handle:
            handle.write(f"EDGAR_RUN_SCHEMA={schema}\nEDGAR_REQUEST_ID={request_id}\n")
    print(f"Verified completed run; SQL build schema: {schema}")
    service.close()
    credential.close()


if __name__ == "__main__":
    main()
