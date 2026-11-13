"""Mocked cloud I/O tests; no SEC requests or Azure resources are used."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

try:
    import azure.functions
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

@unittest.skipUnless(SDK_AVAILABLE, 'Function SDK not installed; run with cloud dependencies for worker tests')
class FunctionTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / 'functions' / 'function_app.py'
        spec = importlib.util.spec_from_file_location('function_under_test', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.worker = self.module.app.get_functions()[0].get_user_function()
        self.message = MagicMock()
        self.message.get_body.return_value = json.dumps({'request_id':'a'*32}).encode()
        self.container = MagicMock()
        self.marker = MagicMock()
        self.lock = MagicMock()
        self.container.get_blob_client.side_effect = [self.lock, self.marker]
        self.marker.download_blob.side_effect = self.module.ResourceNotFoundError('not found')

    def patches(self):
        return patch.multiple(self.module, BlobServiceClient=MagicMock(), DefaultAzureCredential=MagicMock())

    def test_failure_never_publishes_completed_marker(self):
        with self.patches(), patch.dict('os.environ', {'EDGAR_LAKE_URL':'https://example.blob.core.windows.net'}), \
             patch.object(self.module.shutil, 'copytree'), \
             patch.object(self.module.subprocess, 'run', side_effect=subprocess.CalledProcessError(1,['test'])):
            self.module.BlobServiceClient.return_value.get_container_client.return_value = self.container
            with self.assertRaises(subprocess.CalledProcessError): self.worker(self.message)
        self.marker.upload_blob.assert_not_called()
        self.lock.acquire_lease.return_value.release.assert_called_once()

    def test_completed_duplicate_skips_work(self):
        self.marker.download_blob.side_effect = None
        self.marker.download_blob.return_value.readall.return_value = b'{"status":"complete"}'
        with self.patches(), patch.dict('os.environ', {'EDGAR_LAKE_URL':'https://example.blob.core.windows.net'}), \
             patch.object(self.module.subprocess, 'run') as run:
            self.module.BlobServiceClient.return_value.get_container_client.return_value = self.container
            self.worker(self.message)
        run.assert_not_called()
        self.marker.upload_blob.assert_not_called()

    def test_rejects_invalid_request_before_cloud_access(self):
        self.message.get_body.return_value = b'{"request_id":"../escape"}'
        with patch.object(self.module, 'BlobServiceClient') as service:
            with self.assertRaises(ValueError): self.worker(self.message)
            service.assert_not_called()

if __name__=='__main__': unittest.main()
