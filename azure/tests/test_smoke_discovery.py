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
        with patch.object(smoke, 'discover_hostname', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', side_effect=['{}', '{"functionKeys":{"default":"fake-test-key"}}']), \
             patch.object(smoke.time, 'sleep') as sleep:
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 2), ('example.azurewebsites.net', 'fake-test-key'))
            sleep.assert_called_once_with(10)

    def test_accepts_existing_named_host_key_without_master(self):
        with patch.object(smoke, 'discover_hostname', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', return_value='{"masterKey":"unused","functionKeys":{"named":"fake-named-key"}}'):
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 1)[1], 'fake-named-key')

    def test_missing_keys_are_bounded_and_master_is_not_used(self):
        with patch.object(smoke, 'discover_hostname', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', return_value='{"masterKey":"unused"}'), \
             patch.object(smoke.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'no host invocation key'):
                smoke.discover_host_and_key('group', 'app', 1)

    def test_retries_transient_cli_failure(self):
        with patch.object(smoke, 'discover_hostname', return_value='example.azurewebsites.net'), \
             patch.object(smoke.subprocess, 'check_output', side_effect=[subprocess.CalledProcessError(1, ['az']), '{"functionKeys":{"default":"fake-test-key"}}']), \
             patch.object(smoke.time, 'sleep'):
            self.assertEqual(smoke.discover_host_and_key('group', 'app', 2)[1], 'fake-test-key')

class HostnameTests(unittest.TestCase):
    def test_cli_casing_variants(self):
        for field in ['defaultHostName', 'defaultHostname']:
            self.assertEqual(smoke.hostname_from_site({field: 'example.azurewebsites.net'}), 'example.azurewebsites.net')

    def test_raw_arm_shape(self):
        self.assertEqual(smoke.hostname_from_site({'properties': {'defaultHostName': 'example.southafricanorth-01.azurewebsites.net'}}), 'example.southafricanorth-01.azurewebsites.net')

    def test_rejects_external_or_malformed_host(self):
        for value in ['example.com', 'https://example.azurewebsites.net', 'example.azurewebsites.net/evil', None]:
            with self.assertRaises(RuntimeError):
                smoke.hostname_from_site({'defaultHostName': value})

    def test_falls_back_to_arm_without_guessing_hostname(self):
        with patch.object(smoke.subprocess, 'check_output', side_effect=[
            '{"id":"/subscriptions/test/resourceGroups/g/providers/Microsoft.Web/sites/app"}',
            '{"properties":{"defaultHostName":"example.azurewebsites.net"}}'
        ]) as call:
            self.assertEqual(smoke.discover_hostname('g', 'app'), 'example.azurewebsites.net')
            self.assertEqual(call.call_count, 2)

if __name__ == '__main__': unittest.main()
