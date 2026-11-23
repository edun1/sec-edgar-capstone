"""HTTP acceptance, binding and deployment tests; no cloud or SEC calls."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock
import zipfile

ROOT = Path(__file__).resolve().parents[2]

class HttpIngestionTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / 'azure/functions/function_app.py'
        spec = importlib.util.spec_from_file_location('http_function_under_test', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.function = next(f for f in self.module.app.get_functions()
                             if f.get_function_name() == 'request_ingestion')

    def test_acceptance_enqueues_worker_contract_without_running_download(self):
        output = MagicMock()
        response = self.function.get_user_function()(MagicMock(), output)
        self.assertEqual(response.status_code, 202)
        body = json.loads(response.get_body())
        self.assertEqual(body['status'], 'accepted')
        self.module.validate_request_id(body['request_id'])
        output.set.assert_called_once_with(json.dumps({'request_id': body['request_id']}))
        self.assertEqual(body['manifest_path'], f"runs/{body['request_id']}/manifest.json")
        self.assertNotIn('successful', body)

    def test_endpoint_requires_function_key_and_uses_existing_queue(self):
        bindings = json.loads(self.function.get_function_json())['bindings']
        http = next(b for b in bindings if b['type'] == 'httpTrigger')
        queue = next(b for b in bindings if b['type'] == 'queue')
        self.assertEqual(http['authLevel'].lower(), 'function')
        self.assertEqual(http['methods'], ['POST'])
        self.assertEqual(queue['queueName'], 'ingestion-requests')
        self.assertEqual(queue['connection'], 'AzureWebJobsStorage')

    def test_deployment_zip_contains_both_triggers_and_shared_sources(self):
        subprocess.run([sys.executable, str(ROOT / 'azure/scripts/package_function.py')], check=True)
        with zipfile.ZipFile(ROOT / 'azure/function.zip') as archive:
            source = archive.read('function_app.py').decode()
            self.assertIn('def request_ingestion(', source)
            self.assertIn('def ingest(', source)
            self.assertIn('src/run_ingestion.py', archive.namelist())
            self.assertIn('config/companies.json', archive.namelist())
            self.assertFalse(any(n.startswith('azure_function/') for n in archive.namelist()))

if __name__ == '__main__':
    unittest.main()
