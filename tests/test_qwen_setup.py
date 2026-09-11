"""Setup route selection and TLS/offline protection; no model or external request."""
import importlib.util
import io
import os
from pathlib import Path
import socket
import ssl
import sys
import unittest
from unittest.mock import patch

import certifi
import httpx

from scripts import prepare_qwen_models as setup


class SetupProxyTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            'HTTPS_PROXY': 'http://127.0.0.1:19191',
            'ALL_PROXY': 'socks5h://127.0.0.1:19192',
            'SSL_CERT_FILE': certifi.where(),
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for method in ('connect', 'connect_ex'):
            guard = patch.object(socket.socket, method, side_effect=AssertionError('network forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_explicit_https_constructs_without_socks_and_keeps_tls(self):
        if importlib.util.find_spec('socksio') is None:
            with self.assertRaisesRegex(ImportError, 'socksio'):
                httpx.Client()
        before = dict(os.environ)
        hook = lambda request: None
        with patch('ssl.create_default_context', wraps=ssl.create_default_context) as tls:
            with setup.https_client(setup.system_https_proxy(), hook) as client:
                self.assertTrue(client.trust_env)
                self.assertTrue(client.follow_redirects)
                self.assertEqual(client.timeout.connect, 10)
                self.assertEqual(client.timeout.read, 30)
                self.assertEqual(client.event_hooks['request'], [hook])
                self.assertEqual(client._transport._pool._ssl_context.verify_mode, ssl.CERT_REQUIRED)
                self.assertTrue(client._transport._pool._ssl_context.check_hostname)
            self.assertTrue(any(call.kwargs.get('cafile') == certifi.where() for call in tls.call_args_list))
        self.assertEqual(dict(os.environ), before)

    def test_existing_lowercase_https_takes_precedence(self):
        os.environ['https_proxy'] = 'https://127.0.0.1:19193'
        self.assertEqual(setup.system_https_proxy(), os.environ['https_proxy'])
        os.environ['https_proxy'] = ''
        self.assertEqual(setup.system_https_proxy(), os.environ['HTTPS_PROXY'])

    def test_missing_or_invalid_https_never_falls_back_or_echoes_secrets(self):
        for value in ('', 'socks5h://user:secret@127.0.0.1:19192',
                      'http://', 'http://user:secret@127.0.0.1:99999',
                      'http://127.0.0.1/path', 'http://127.0.0.1?secret',
                      'http://127.0.0.1#secret', 'http://127.0.0.1\n',
                      'http://[broken'):
            with self.subTest(value=value):
                os.environ['HTTPS_PROXY'] = value
                with self.assertRaises(ValueError) as error:
                    setup.system_https_proxy()
                self.assertNotIn('secret', str(error.exception))
                self.assertNotIn('127.0.0.1', str(error.exception))

    def test_ca_failure_is_not_replaced_with_insecure_tls(self):
        os.environ['SSL_CERT_FILE'] = str(Path(__file__).with_name('missing-test-ca.pem'))
        with self.assertRaises(FileNotFoundError):
            setup.https_client(setup.system_https_proxy(), lambda request: None)

    def test_invalid_cli_proxy_stops_before_model_setup_without_disclosure(self):
        os.environ['HTTPS_PROXY'] = 'socks5h://user:secret@127.0.0.1:19192'
        with patch.object(sys, 'argv', ['prepare_qwen_models.py', '--use-system-https-proxy']), \
                patch.object(setup, 'default_data_dir', return_value=Path('unused-test-data')), \
                patch('sys.stderr', new_callable=io.StringIO) as stderr, \
                patch.object(setup, 'no_symlink') as storage:
            with self.assertRaises(SystemExit) as error:
                setup.main()
            self.assertEqual(error.exception.code, 2)
            self.assertNotIn('secret', stderr.getvalue())
            self.assertNotIn('127.0.0.1', stderr.getvalue())
            storage.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('huggingface_hub'), 'optional model runtime not installed')
    def test_actual_hf_session_keeps_offline_guard_and_does_not_connect(self):
        from huggingface_hub import get_session, set_client_factory
        from huggingface_hub import constants
        from huggingface_hub.errors import OfflineModeIsEnabled
        from huggingface_hub.utils import _http
        original = _http._GLOBAL_CLIENT_FACTORY
        self.addCleanup(lambda: set_client_factory(original))
        before = dict(os.environ)
        setup.configure_system_https_proxy()
        session = get_session()
        self.assertIs(session, get_session())
        with patch.object(constants, 'is_offline_mode', return_value=True):
            with self.assertRaises(OfflineModeIsEnabled):
                session.get('https://huggingface.co/unused-offline-test')
        self.assertEqual(dict(os.environ), before)


if __name__ == '__main__':
    unittest.main()
