"""No-network checks of the developer experiment's cost and egress boundaries."""
import contextlib
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import run_translation_compare as compare


class ComparisonTests(unittest.TestCase):
    def run_fake(self, response, budget='1'):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        out = Path(temp.name) / 'result'
        calls = []
        def call(key, method, body):
            self.assertEqual(key, 'dummy-not-a-key')
            calls.append(method)
            if method == 'countTokens':
                return {'seconds': .1, 'data': {'totalTokens': 300}}
            return response
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'dummy-not-a-key'}), contextlib.redirect_stdout(io.StringIO()):
            report = compare.run(out, Decimal(budget), call)
        return report, calls, out

    def test_budget_and_unknown_failure_stop_without_retry(self):
        report, calls, _ = self.run_fake({'error': 'http_error', 'http_status': 429, 'seconds': .2})
        self.assertEqual(calls, ['countTokens', 'generateContent'])
        self.assertEqual(report['state'], 'request_or_accounting_failure')
        self.assertGreater(Decimal(report['accounted_usd']), Decimal('.24'))
        report, calls, _ = self.run_fake({}, '.1')
        self.assertEqual(calls, ['countTokens'])
        self.assertEqual(report['state'], 'budget_stop')
        self.assertEqual(Decimal(report['accounted_usd']), 0)

    def test_changed_input_or_existing_output_never_calls(self):
        bad = compare.prepare()
        bad['fixture_sha256'] = 'changed'
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'GEMINI_API_KEY': 'dummy'}):
            def forbidden(*args):
                self.fail('network callback must not run')
            with patch.object(compare, 'prepare', return_value=bad), self.assertRaises(ValueError):
                compare.run(Path(temp) / 'new', Decimal('1'), forbidden)
            with self.assertRaises(FileExistsError):
                compare.run(Path(temp), Decimal('1'), forbidden)

    def test_missing_ids_refusal_and_usage_are_not_success(self):
        body = compare.prepare()['requests'][0]['body']
        targets = json.loads(body['contents'][0]['parts'][0]['text'])
        rows = [{'id': t['id'], 'text': '번역'} for t in targets]
        def data(values, reason='STOP'):
            return {'candidates': [{'finishReason': reason, 'content': {'parts': [
                {'text': json.dumps({'translations': values})}]}}]}
        self.assertTrue(compare.assess(body, data(rows))['valid'])
        for values in (rows[:-1], rows + rows[:1], rows[::-1]):
            self.assertFalse(compare.assess(body, data(values))['valid'])
        self.assertFalse(compare.assess(body, data(rows, 'SAFETY'))['valid'])
        self.assertFalse(compare.assess(body, {'promptFeedback': {'blockReason': 'SAFETY'}})['valid'])
        self.assertIsNone(compare.token_cost({}))
        self.assertEqual(compare.token_cost({'promptTokenCount': 100, 'candidatesTokenCount': 20,
            'thoughtsTokenCount': 40, 'totalTokenCount': 160}), Decimal('.0003'))
        report, calls, _ = self.run_fake({'data': data(rows), 'seconds': .2})
        self.assertEqual(calls, ['countTokens', 'generateContent'])
        self.assertEqual(report['state'], 'request_or_accounting_failure')

    def test_key_header_only_fixed_host_redacted_response_no_redirect(self):
        seen = []
        class Response(io.BytesIO):
            pass
        class Opener:
            def open(self, request, timeout):
                seen.append(request)
                encoded = ''.join('\\u%04x' % ord(c) for c in 'dummy-not-a-key')
                return Response(('{"echo":"' + encoded + '","' + encoded + '":["dummy-not-a-key"]}').encode())
        with patch.object(compare.urllib.request, 'build_opener', return_value=Opener()):
            result = compare.request('dummy-not-a-key', 'countTokens', {'contents': []})
        req = seen[0]
        self.assertEqual(req.full_url, compare.HOST + compare.MODEL + ':countTokens')
        self.assertNotIn('dummy-not-a-key', req.full_url + req.data.decode())
        self.assertEqual(req.get_header('X-goog-api-key'), 'dummy-not-a-key')
        self.assertNotIn('dummy-not-a-key', json.dumps(result))
        self.assertIsNone(compare.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.invalid'))

    def test_null_envelopes_keep_failed_request_and_cost(self):
        usage = {'promptTokenCount': 100, 'totalTokenCount': 120}
        for data in ({'usageMetadata': None}, {'usageMetadata': usage, 'candidates': None},
                     {'usageMetadata': usage, 'candidates': [{'content': {'parts': None}}]}):
            report, calls, out = self.run_fake({'data': data, 'seconds': .2})
            self.assertEqual(calls, ['countTokens', 'generateContent'])
            self.assertEqual(report['state'], 'request_or_accounting_failure')
            self.assertEqual(len(json.loads((out / 'report.json').read_text())['requests']), 1)
            self.assertGreater(Decimal(report['accounted_usd']), 0)

    def test_alternative_model_budget_and_endpoint_are_explicit(self):
        calls = []
        def call(key, method, body):
            calls.append((method, body))
            if method == 'countTokens':
                self.assertEqual(body['generateContentRequest']['model'], 'models/gemini-2.5-flash')
                return {'seconds': .1, 'data': {'totalTokens': 300}}
            self.assertEqual(body['generationConfig']['thinkingConfig'], {'thinkingBudget': 1024})
            return {'seconds': .2, 'error': 'http_error', 'http_status': 503}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'GEMINI_API_KEY': 'dummy'}), contextlib.redirect_stdout(io.StringIO()):
            report = compare.run(Path(temp) / 'result', Decimal('.5'), call, 'gemini-2.5-flash')
        self.assertEqual(report['model'], 'gemini-2.5-flash')
        self.assertEqual(report['output_per_million_usd'], '2.50')
        self.assertLess(Decimal(report['accounted_usd']), Decimal('.17'))
        self.assertEqual(len(calls), 2)
        with self.assertRaises(ValueError):
            compare.request('dummy', 'generateContent', {}, 'unapproved')


if __name__ == '__main__':
    unittest.main()
