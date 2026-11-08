"""Failure handling checks for the offline pipeline runner."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'pipeline', Path(__file__).resolve().parents[1] / 'src' / 'run_pipeline.py'
)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_failed_child_returns_nonzero(self):
        with self.assertRaises(subprocess.CalledProcessError):
            pipeline.run_stage('failure', [sys.executable, '-c', 'raise SystemExit(7)'],
                               dict(__import__('os').environ), io.StringIO())

    def test_failure_stops_remaining_stages_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(pipeline, 'PROJECT_ROOT', root), patch.object(
                pipeline, 'run_stage', side_effect=subprocess.CalledProcessError(2, ['test'])
            ) as stage:
                self.assertEqual(pipeline.main([]), 1)
                self.assertEqual(stage.call_count, 1)
            summary = json.loads(next((root/'logs').glob('pipeline_*_summary.json')).read_text())
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual(summary['stages'][0]['status'], 'failed')
            self.assertFalse((root/'logs/.pipeline.lock').exists())
            self.assertNotIn('output', summary)

    def test_existing_lock_prevents_second_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'logs/.pipeline.lock').mkdir(parents=True)
            with patch.object(pipeline, 'PROJECT_ROOT', root), patch.object(pipeline, 'run_stage') as stage:
                self.assertEqual(pipeline.main([]), 1)
                stage.assert_not_called()


if __name__ == '__main__':
    unittest.main()
