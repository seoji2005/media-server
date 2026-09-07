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
import continue_gemini_comparison as continuation


class ComparisonTests(unittest.TestCase):
    def test_overlapping_continuation_cannot_call_or_overwrite_accounting(self):
        from media_clarity.storage import MediaError
        calls=[]
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GEMINI_API_KEY':'dummy'}),contextlib.redirect_stdout(io.StringIO()):
            out=Path(temp)/'run'
            def forbidden(*args):self.fail('overlapping paid call')
            def outer(key,method,body,model):
                calls.append(json.loads(body['contents'][0]['parts'][0]['text'])[0]['id'])
                reserved=(out/'report.json').read_bytes()
                with self.assertRaisesRegex(MediaError,'processing_worker_active'):
                    continuation.run(out,model,1,Decimal('2'),forbidden)
                self.assertEqual((out/'report.json').read_bytes(),reserved)
                return {'seconds':1,'error':'http_error','http_status':503}
            report=continuation.run(out,'gemini-3.1-flash-lite',1,Decimal('2'),outer)
            self.assertEqual(calls,['tos_00'])
            self.assertEqual(len(report['requests']),1)
            self.assertEqual(report,json.loads((out/'report.json').read_text()))

    def test_continuation_reuses_prior_results_and_does_not_repeat_completed_calls(self):
        seen = []
        def call(key,method,body,model):
            ids=[r['id'] for r in json.loads(body['contents'][0]['parts'][0]['text'])]
            seen.append(ids)
            return {'seconds':1,'data':{'usageMetadata':{'promptTokenCount':100,'totalTokenCount':200},
                'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(
                    {'translations':[{'id':i,'text':'검증 번역'} for i in ids]})}]}}]}}
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GEMINI_API_KEY':'dummy'}),contextlib.redirect_stdout(io.StringIO()):
            out=Path(temp)/'run'
            first=continuation.run(out,'gemini-3.8-flash',1,Decimal('2'),call)
            self.assertEqual(first['attempted_unique_cases'],24)
            second=continuation.run(out,'gemini-3.8-flash',1,Decimal('2'),call)
            self.assertEqual(second['attempted_unique_cases'],32)
            self.assertEqual(seen,[[f'tos_{i:02}' for i in range(16,24)], [f'tos_{i:02}' for i in range(24,32)]])
            before=(out/'report.json').read_bytes()
            with self.assertRaises(ValueError):continuation.run(out,'gemini-3.1-flash-lite',1,Decimal('2'),call)
            self.assertEqual((out/'report.json').read_bytes(),before)

    def test_continuation_keeps_unknown_reservation_and_stops_repeated_transport_failure(self):
        calls=[]
        def crash(*args):
            calls.append('crash')
            raise KeyboardInterrupt()
        def fail(*args):
            calls.append('fail')
            return {'seconds':1,'error':'http_error','http_status':503}
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GEMINI_API_KEY':'dummy'}),contextlib.redirect_stdout(io.StringIO()):
            out=Path(temp)/'run'
            with self.assertRaises(KeyboardInterrupt):continuation.run(out,'gemini-3.1-flash-lite',1,Decimal('2'),crash)
            saved=json.loads((out/'report.json').read_text())
            self.assertEqual(saved['requests'][0]['state'],'reserved')
            self.assertGreater(Decimal(saved['requests'][0]['accounted_usd']),0)
            report=continuation.run(out,'gemini-3.1-flash-lite',8,Decimal('2'),fail)
            self.assertEqual(calls,['crash','fail'])
            self.assertEqual(report['state'],'consecutive_failure_stop')
            self.assertEqual(report['attempted_unique_cases'],16)
            continuation.run(out,'gemini-3.1-flash-lite',8,Decimal('2'),fail)
            self.assertEqual(calls,['crash','fail'])

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

    def test_http_error_retains_only_fixed_diagnostic_labels(self):
        for status, message, signal in (
                ('UNAVAILABLE', 'This model is overloaded.', 'capacity'),
                ('RESOURCE_EXHAUSTED', 'Your prepayment credits are depleted.', 'billing'),
                ('NOT_FOUND', 'Model is not found for API version v1beta.', 'model_or_method')):
            payload = json.dumps({'error': {'status': status,
                'message': message + ' project: private-project key: dummy-secret',
                'details': [{'secret': 'dummy-secret'}]}}).encode()
            stream = io.BytesIO(payload)
            class Opener:
                def open(self, *args, **kwargs):
                    raise compare.urllib.error.HTTPError('private-url', 503,
                        'private-reason', {'private-header': 'dummy-secret'}, stream)
            with patch.object(compare.urllib.request, 'build_opener', return_value=Opener()):
                result = compare.request('dummy-secret', 'generateContent', {})
            self.assertEqual(result['api_status'], status)
            self.assertIn(signal, result['message_signals'])
            self.assertEqual(result['http_status'], 503)
            self.assertTrue(stream.closed)
            self.assertNotIn('dummy-secret', json.dumps(result))
            self.assertNotIn('private', json.dumps(result))

    def test_error_body_malformed_or_arbitrary_values_never_escape(self):
        for value in (None, [], {'error': None}, {'error': []},
                {'error': {'status': ['UNAVAILABLE'], 'message': []}},
                {'error': {'status': 'private-secret', 'message': 'private-secret'}}):
            result = compare.error_summary(json.dumps(value))
            self.assertNotIn('private-secret', json.dumps(result))
        for payload in (b'<html>private-secret</html>', b'\xff', b'[' * 2000):
            self.assertEqual(compare.error_summary(payload), {'error_body': 'unrecognized'})

    def test_error_close_failure_still_saves_failed_request(self):
        class BrokenClose(io.BytesIO):
            def close(self):
                super().close()
                raise OSError('private cleanup detail')
        class Opener:
            def open(self, request, timeout):
                if request.full_url.endswith(':countTokens'):
                    return io.BytesIO(b'{"totalTokens":300}')
                raise compare.urllib.error.HTTPError('private-url', 503, 'private', {},
                    BrokenClose(b'{"error":{"status":"UNAVAILABLE","message":"overloaded"}}'))
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'GEMINI_API_KEY': 'dummy'}), \
                patch.object(compare.urllib.request, 'build_opener', return_value=Opener()), \
                contextlib.redirect_stdout(io.StringIO()):
            out = Path(temp) / 'result'
            report = compare.run(out, Decimal('1'))
            self.assertEqual(report['state'], 'request_or_accounting_failure')
            saved = json.loads((out / 'report.json').read_text())
            self.assertEqual(len(saved['requests']), 1)
            self.assertEqual(saved['requests'][0]['api_status'], 'UNAVAILABLE')
            self.assertGreater(Decimal(saved['accounted_usd']), 0)
            self.assertNotIn('private', json.dumps(saved))


if __name__ == '__main__':
    unittest.main()
