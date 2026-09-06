"""One explicitly approved, public-text-only Gemini experiment; no app integration.

GEMINI_API_KEY is read from the environment. An exclusive output directory prevents
accidental reruns over an existing experiment. No automatic retry or resume.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

from prepare_translation_compare import MODEL, prepare

FIXTURE_SHA = 'd6a3734789dd02e5d9425635e81484fa187e1fdf58163e3e05dda55955501dec'
HOST = 'https://generativelanguage.googleapis.com/v1beta/models/'
INPUT_RATE, OUTPUT_RATE = Decimal('0.75') / 1000000, Decimal('3.75') / 1000000
RATES = {'gemini-3.8-flash': (Decimal('0.75'), Decimal('3.75')),
         'gemini-3.7-flash': (Decimal('0.75'), Decimal('3.75')),
         'gemini-2.5-flash': (Decimal('0.30'), Decimal('2.50'))}
# Reserve the model's entire documented output limit (including thinking), much
# more than the requested 4096, before each request; release only against usage.
MAX_MODEL_OUTPUT = 65536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def redact(value, key):
    if isinstance(value, str):
        return value.replace(key, '[redacted]')
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    if isinstance(value, dict):
        return {redact(k, key): redact(v, key) for k, v in value.items()}
    return value


def error_summary(payload):
    """Keep fixed diagnostic labels, never provider text/account IDs/headers."""
    result = {'error_body': 'unrecognized'}
    try:
        data = json.loads(payload)
        error = data.get('error') if type(data) is dict else None
        if type(error) is not dict:
            return result
        result['error_body'] = 'json_error'
        status = error.get('status')
        if type(status) is str and status in {
                'INVALID_ARGUMENT', 'FAILED_PRECONDITION', 'UNAUTHENTICATED',
                'PERMISSION_DENIED', 'NOT_FOUND', 'RESOURCE_EXHAUSTED',
                'INTERNAL', 'UNAVAILABLE', 'DEADLINE_EXCEEDED'}:
            result['api_status'] = status
        message = error.get('message')
        if type(message) is str:
            message = message.lower()
            signals = {
                'capacity': ('overloaded', 'high demand', 'capacity'),
                'billing': ('billing', 'prepayment', 'prepay', 'credits'),
                'quota': ('quota', 'rate limit'),
                'credential': ('api key', 'api_key'),
                'location': ('location is not supported', 'unsupported location'),
                'model_or_method': ('not found for api version', 'not supported for'),
            }
            result['message_signals'] = [label for label, phrases in signals.items()
                                         if any(p in message for p in phrases)]
    except (ValueError, TypeError, RecursionError):
        pass
    return result


def request(key, method, body, model=MODEL):
    if method not in ('countTokens', 'generateContent') or model not in RATES:
        raise ValueError('invalid_method')
    raw = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(HOST + model + ':' + method, data=raw,
        headers={'x-goog-api-key': key, 'Content-Type': 'application/json'})
    start = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            payload = response.read(1048577)
            if len(payload) > 1048576:
                return {'error': 'response_too_large', 'seconds': time.monotonic() - start}
            # Do not retain a credential even if an upstream response echoes it.
            data = redact(json.loads(payload), key)
            if type(data) is not dict:
                return {'error': 'invalid_response_envelope', 'seconds': time.monotonic() - start}
            return {'data': data, 'seconds': time.monotonic() - start}
    except urllib.error.HTTPError as error:
        # Read a bounded body only to classify it; retain no raw text or headers.
        try:
            payload = error.read(16385)
            detail = error_summary(payload) if len(payload) <= 16384 else {'error_body': 'too_large'}
        except Exception:
            detail = {'error_body': 'unreadable'}
        finally:
            try:
                error.close()
            except Exception:
                pass  # Cleanup must not discard the failed request/accounting.
        return {'error': 'http_error', 'http_status': error.code,
                'seconds': time.monotonic() - start, **detail}
    except Exception:
        return {'error': 'transport_or_json_error', 'seconds': time.monotonic() - start}


def token_cost(usage, input_rate=INPUT_RATE, output_rate=OUTPUT_RATE):
    if type(usage) is not dict:
        return None
    names = ('promptTokenCount', 'candidatesTokenCount', 'thoughtsTokenCount', 'totalTokenCount')
    values = [usage.get(k, 0) for k in names]
    if ('promptTokenCount' not in usage or 'totalTokenCount' not in usage
            or any(type(v) is not int or v < 0 for v in values)):
        return None
    prompt, candidate, thought, total = values
    if total < prompt:
        return None
    return input_rate * prompt + output_rate * max(total - prompt, candidate + thought)


def assess(body, data):
    expected = [r['id'] for r in json.loads(body['contents'][0]['parts'][0]['text'])]
    candidates = data.get('candidates', [])
    result = {'expected_ids': expected, 'valid': False,
              'prompt_feedback': data.get('promptFeedback'), 'model_version': data.get('modelVersion')}
    if (type(candidates) is not list or
            (data.get('promptFeedback') is not None and type(data['promptFeedback']) is not dict)):
        result['problem'] = 'invalid_response_envelope'
        return result
    if len(candidates) != 1:
        result['problem'] = 'candidate_count'
        return result
    candidate = candidates[0]
    if type(candidate) is not dict or type(candidate.get('content', {})) is not dict:
        result['problem'] = 'invalid_response_envelope'
        return result
    result.update(finish_reason=candidate.get('finishReason'), safety_ratings=candidate.get('safetyRatings'))
    parts = candidate.get('content', {}).get('parts', [])
    if (type(parts) is not list or any(type(p) is not dict or
            type(p.get('text', '')) is not str for p in parts)):
        result['problem'] = 'invalid_response_envelope'
        return result
    raw = ''.join(p.get('text', '') for p in parts if not p.get('thought', False))
    result['output_text'] = raw
    try:
        value = json.loads(raw)
        rows = value['translations']
        valid = (type(value) is dict and set(value) == {'translations'} and type(rows) is list
            and all(type(r) is dict and set(r) == {'id', 'text'} for r in rows)
            and [r['id'] for r in rows] == expected
            and all(type(r['text']) is str and r['text'].strip() and len(r['text']) <= 4000
                    and all(c.isprintable() or c == '\n' for c in r['text']) for r in rows))
    except (ValueError, KeyError, TypeError):
        valid = False
    result['valid'] = bool(valid and candidate.get('finishReason') == 'STOP'
                           and not (data.get('promptFeedback') or {}).get('blockReason'))
    if result['valid']:
        result['translations'] = rows
    else:
        result['problem'] = 'blocked_incomplete_or_invalid_output'
    return result


def run(out, limit, call=None, model=MODEL):
    key = os.environ.get('GEMINI_API_KEY', '')
    if not key or not Decimal('0') < limit <= Decimal('1'):
        raise ValueError('key_and_approved_budget_required')
    bundle = prepare()
    if bundle['fixture_sha256'] != FIXTURE_SHA or bundle['model'] != 'gemini-3.8-flash':
        raise ValueError('unapproved_fixture_or_model')
    if model not in RATES:
        raise ValueError('unapproved_model')
    input_rate, output_rate = (r / 1000000 for r in RATES[model])
    if call is None:
        call = lambda key, method, body: request(key, method, body, model)
    if model == 'gemini-2.5-flash':
        for spec in bundle['requests']:
            spec['body']['generationConfig']['thinkingConfig'] = {'thinkingBudget': 1024}
    if out.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('output_must_be_outside_repository')
    out.mkdir(mode=0o700)  # Fail before any call if it already exists.
    report = {'model': model, 'fixture_sha256': FIXTURE_SHA, 'limit_usd': str(limit),
              'input_per_million_usd': str(RATES[model][0]), 'output_per_million_usd': str(RATES[model][1]),
              'safety': bundle['safety'], 'state': 'running', 'requests': []}
    def save():
        # The directory was created by this invocation and contains public results only.
        (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    spent = Decimal('0')
    with (out / 'reservations.jsonl').open('x') as ledger:
        for i, spec in enumerate(bundle['requests']):
            body = spec['body']
            counted = call(key, 'countTokens', {'generateContentRequest': dict(body, model='models/' + model)})
            count = counted.get('data', {}).get('totalTokens')
            if 'error' in counted or type(count) is not int or count < 0:
                report.update(state='count_failed', failed_count=counted)
                break
            # Include extra room for schema/system accounting differences.
            prompt_reserve = max(count + 1024, len(json.dumps(body, ensure_ascii=False).encode()))
            reserve = input_rate * prompt_reserve + output_rate * MAX_MODEL_OUTPUT
            if spent + reserve > limit:
                report['state'] = 'budget_stop'
                break
            ledger.write(json.dumps({'request': i, 'reserved_usd': str(reserve)}) + '\n')
            ledger.flush()
            os.fsync(ledger.fileno())  # Keep unknown-cost calls visible after interruption.
            row = {'index': i, 'group': spec['group'], 'repetition': spec['repetition'],
                   'input_tokens_before': count, 'count_seconds': counted['seconds'],
                   'reserved_usd': str(reserve), 'request_sha256': hashlib.sha256(
                       json.dumps(body, ensure_ascii=False).encode()).hexdigest()}
            outcome = call(key, 'generateContent', body)
            row.update(outcome)
            data = outcome.get('data', {})
            cost = token_cost(data.get('usageMetadata', {}), input_rate, output_rate)
            spent += reserve if cost is None else cost
            row['accounted_usd'] = str(reserve if cost is None else cost)
            row['usage_missing'] = cost is None
            row['assessment'] = assess(body, data)
            report['requests'].append(row)
            report['accounted_usd'] = str(spent)
            save()
            print(json.dumps({'finished': i + 1, 'valid': row['assessment']['valid'],
                              'seconds': row['seconds'], 'accounted_usd': str(spent)}), flush=True)
            if ('error' in outcome or cost is None or cost > reserve or
                    row['assessment'].get('problem') == 'invalid_response_envelope'):
                report['state'] = 'request_or_accounting_failure'
                break
        else:
            report['state'] = 'completed'
    report['accounted_usd'] = str(spent)
    save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--approved-budget-usd', type=Decimal, required=True)
    parser.add_argument('--model', choices=sorted(RATES), default=MODEL)
    args = parser.parse_args()
    try:
        result = run(args.out, args.approved_budget_usd, model=args.model)
    except Exception:
        print('comparison_stopped; inspect saved public results', file=sys.stderr)
        raise SystemExit(1) from None
    raise SystemExit(0 if result['state'] == 'completed' else 2)
