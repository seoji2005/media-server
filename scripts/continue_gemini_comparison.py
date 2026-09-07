"""Bounded continuation of the frozen public comparison; no retry of attempted IDs.

Read GEMINI_API_KEY from the environment. Run one model at a time, outside the repo.
The existing experiment transport uses the configured system HTTPS route (not the
production adapter's direct-only route). No safety override or private input.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

from prepare_translation_compare import ROOT, prepare
from run_translation_compare import FIXTURE_SHA, RATES, request, assess, token_cost

sys.path.insert(0, str(ROOT))
from media_clarity.jobs import worker_guard

MODELS = ('gemini-3.8-flash', 'gemini-3.1-flash-lite', 'gemini-2.5-flash-lite')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def old_results():
    first = json.loads((ROOT/'docs/evidence/translation_gemini_attempt.json').read_text())
    second = json.loads((ROOT/'docs/evidence/translation_gemini_diagnosis.json').read_text())
    rows = [first['runs'][0]['requests'][0], second['calls'][1]]
    assert all(r['assessment']['valid'] for r in rows)
    ids = [i for r in rows for i in r['assessment']['expected_ids']]
    assert ids == [f'tos_{i:02}' for i in range(16)]
    return rows


def run(out, model, max_calls, budget, call=request):
    if model not in MODELS or not 1 <= max_calls <= 8 or not Decimal('0') < budget <= Decimal('2'):
        raise ValueError('invalid_bounded_run')
    key = os.environ.get('GEMINI_API_KEY')
    if not key or out.resolve().is_relative_to(ROOT):
        raise ValueError('key_and_external_output_required')
    bundle = prepare()
    assert bundle['fixture_sha256'] == FIXTURE_SHA
    if not (out/'report.json').exists():
        out.mkdir(mode=0o700)
    # Reuse the application's kernel-owned lease. A crash releases it; concurrent
    # resumes cannot call with stale attempted IDs or overwrite accounting.
    with worker_guard(out):
        return _run_locked(out,model,max_calls,budget,call,key,bundle)


def _run_locked(out, model, max_calls, budget, call, key, bundle):
    specs = [s for s in bundle['requests'] if s['repetition'] == 0]
    if model == 'gemini-2.5-flash-lite':
        for spec in specs:
            spec['body']['generationConfig']['thinkingConfig'] = {'thinkingBudget':0}
    profile = digest(specs)
    path = out/'report.json'
    if path.exists():
        report = json.loads(path.read_text())
        if (report['model'] != model or report['fixture_sha256'] != FIXTURE_SHA
                or report['profile_sha256'] != profile or Decimal(report['budget_usd']) != budget):
            raise ValueError('saved_comparison_changed')
    else:
        reused = old_results() if model == 'gemini-3.8-flash' else []
        report = {'model':model, 'fixture_sha256':FIXTURE_SHA, 'profile_sha256':profile,
            'budget_usd':str(budget), 'rates_per_million_usd':[str(v) for v in RATES[model]],
            'safety':'provider defaults; no override', 'reused_prior_results':reused,
            'transport':'system-configured HTTPS route, redirects disabled',
            'requests':[]}
    def save():
        temp = out/'report.pending'
        with temp.open('w') as f:
            json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        temp.replace(path)
    attempted = {i for r in report['requests'] for i in r['ids']}
    attempted.update(i for r in report['reused_prior_results'] for i in r['assessment']['expected_ids'])
    spent = sum((Decimal(r['accounted_usd']) for r in report['requests']),Decimal(0))
    rates = [v/1000000 for v in RATES[model]]
    calls = 0
    failures = 0
    for r in reversed(report['requests']):
        if r.get('outcome',{}).get('error') or r['state'] == 'reserved': failures += 1
        else: break
    for index, spec in enumerate(specs):
        ids = [r['id'] for r in json.loads(spec['body']['contents'][0]['parts'][0]['text'])]
        if set(ids) <= attempted: continue
        if set(ids) & attempted: raise ValueError('partial_prior_request')
        if calls >= max_calls or failures >= 2: break
        # Conservative full model output reservation, not a claim about invoice charges.
        reserve = rates[0]*(len(json.dumps(spec['body'],ensure_ascii=False).encode())+1024) + rates[1]*65536
        if spent + reserve > budget: break
        row = {'index':index, 'ids':ids, 'group':spec['group'],
            'request_sha256':digest(spec['body']), 'state':'reserved',
            'reserved_usd':str(reserve), 'accounted_usd':str(reserve)}
        report['requests'].append(row);save()
        result = call(key,'generateContent',spec['body'],model)
        row.update(state='finished',outcome=result)
        if 'data' in result:
            row['assessment'] = assess(spec['body'],result['data'])
            cost = token_cost(result['data'].get('usageMetadata'),*rates)
            row['usage_price_estimate_usd'] = str(cost) if cost is not None else None
            if cost is not None: row['accounted_usd'] = str(cost)
        spent += Decimal(row['accounted_usd']);calls += 1
        failures = failures+1 if result.get('error') else 0
        report['new_accounted_usd'] = str(spent)
        report['attempted_unique_cases'] = len(attempted | {i for r in report['requests'] for i in r['ids']})
        save()
        print(json.dumps({'model':model,'ids':ids,'valid':row.get('assessment',{}).get('valid',False),
            'seconds':result.get('seconds'),'error':result.get('error'),'http_status':result.get('http_status')}),flush=True)
    report['attempted_unique_cases'] = len(attempted | {i for r in report['requests'] for i in r['ids']})
    report['state'] = 'attempted_all' if report['attempted_unique_cases'] == 80 else 'consecutive_failure_stop' if failures >= 2 else 'paused'
    save()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--model',choices=MODELS,required=True)
    parser.add_argument('--max-calls',type=int,default=4)
    parser.add_argument('--budget-usd',type=Decimal,required=True)
    args = parser.parse_args()
    try:
        report = run(args.out,args.model,args.max_calls,args.budget_usd)
        print(json.dumps({'state':report['state'],'attempted_unique_cases':report['attempted_unique_cases']}))
    except Exception:
        print('comparison_stopped; retain checkpoint and inspect public diagnostics',file=sys.stderr)
        raise SystemExit(1) from None
