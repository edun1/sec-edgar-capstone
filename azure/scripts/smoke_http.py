"""Live HTTP-to-lake smoke test; never prints Function credentials."""
import hashlib
import json
import os
import subprocess
import time

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient
from cloud_run import verify_manifest


def az_value(*args):
    return subprocess.check_output(['az', *args, '-o', 'tsv', '--only-show-errors'], text=True).strip()


def main():
    group = os.environ['AZURE_RESOURCE_GROUP']
    app = os.environ['AZURE_FUNCTION_NAME']
    hostname = az_value('functionapp', 'show', '-g', group, '-n', app, '--query', 'defaultHostName')
    key = az_value('functionapp', 'keys', 'list', '-g', group, '-n', app, '--query', 'functionKeys.default')
    if not key or not hostname or '/' in hostname:
        raise RuntimeError('Missing Function host or default key')
    if os.getenv('GITHUB_ACTIONS') == 'true':
        print('::add-mask::' + key, flush=True)
    url = 'https://' + hostname + '/api/ingest'
    # Deployment trigger synchronization may take a short time.
    for attempt in range(12):
        response = requests.post(url, timeout=30)
        if response.status_code in (401, 403):
            break
        if response.status_code not in (404, 502, 503):
            raise RuntimeError(f'Unauthenticated endpoint returned unexpected HTTP {response.status_code}')
        time.sleep(10)
    else:
        raise RuntimeError('Protected endpoint did not become available')
    print('PASS: unauthenticated POST rejected', flush=True)
    response = requests.post(url, headers={'x-functions-key': key}, timeout=60)
    if response.status_code != 202:
        raise RuntimeError(f'Authenticated endpoint returned HTTP {response.status_code}; expected 202')
    body = response.json()
    request_id = body.get('request_id', '')
    import re
    if not re.fullmatch('[a-f0-9]{32}', request_id) or body.get('status') != 'accepted':
        raise RuntimeError('Invalid HTTP acceptance contract')
    expected_path = f'runs/{request_id}/manifest.json'
    if body.get('manifest_path') != expected_path:
        raise RuntimeError('Manifest path does not match HTTP request')
    print(f'PASS: authenticated POST accepted request {request_id}', flush=True)
    with AzureCliCredential() as credential:
        with BlobServiceClient('https://' + os.environ['AZURE_LAKE_STORAGE'] + '.blob.core.windows.net', credential=credential) as service:
            container = service.get_container_client('edgar')
            deadline = time.monotonic() + 1200
            while time.monotonic() < deadline:
                try:
                    manifest = json.loads(container.download_blob(expected_path).readall())
                    break
                except ResourceNotFoundError:
                    time.sleep(15)
            else:
                raise TimeoutError('No completed manifest after 20 minutes; inspect worker logs/poison queue')
            verify_manifest(manifest, request_id)
            for record in manifest['files']:
                content = container.download_blob(record['blob']).readall()
                if len(content) != record['bytes'] or hashlib.sha256(content).hexdigest() != record['sha256']:
                    raise RuntimeError('Lake file failed integrity check: ' + record['path'])
    print(f"PASS: completed exact run; verified {len(manifest['files'])} lake files", flush=True)
    from pathlib import Path
    evidence = Path('azure/http-smoke-result.json')
    evidence.write_text(json.dumps({'status': 'passed', 'request_id': request_id,
                                   'files_verified': len(manifest['files']),
                                   'ingestion_run_id': manifest['ingestion_run_id']}, indent=2))


if __name__ == '__main__':
    main()
