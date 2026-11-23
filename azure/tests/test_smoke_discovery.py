"""Readiness handling without Azure access or real credentials."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('smoke_http', SCRIPTS / 'smoke_http.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

class DiscoveryTests(unittest.TestCase):
    def test_waits_for_empty_keys_then_accepts_default(self):
        with patch.object(smoke, 'az_value', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', side_effect=['{}', '{"functionKeys":{"default":"fake-test-key"}}']), \
             patch.object(smoke.time, 'sleep') as sleep:
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 2), ('example.azurewebsites.net', 'fake-test-key'))
            sleep.assert_called_once_with(10)

    def test_accepts_existing_named_host_key_without_master(self):
        with patch.object(smoke, 'az_value', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', return_value='{"masterKey":"unused","functionKeys":{"named":"fake-named-key"}}'):
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 1)[1], 'fake-named-key')

    def test_missing_keys_are_bounded_and_master_is_not_used(self):
        with patch.object(smoke, 'az_value', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', return_value='{"masterKey":"unused"}'), \
             patch.object(smoke.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'no host invocation key'):
                smoke.discover_host_and_key('group', 'app', 1)

    def test_retries_transient_cli_failure(self):
        with patch.object(smoke, 'az_value', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', side_effect=[subprocess.CalledProcessError(1, ['az']), '{"functionKeys":{"default":"fake-test-key"}}']), \
             patch.object(smoke.time, 'sleep'):
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 2)[1], 'fake-test-key')

if __name__ == '__main__': unittest.main()
