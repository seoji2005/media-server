"""Bounded Linux CPU Qwen3.5 experiment using only the frozen public fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_translation_compare import PROMPT

MODEL = 'unsloth/Qwen3.5-4B-GGUF'
REVISION = 'e87f176479d0855a907a41277aca2f8ee7a09523'
MODEL_SHA = 'fdedd781c9ce676ab66b018ca247ff78e8a33c98098a822c1e2d5075e7718f66'
FIXTURE_SHA = 'd6a3734789dd02e5d9425635e81484fa187e1fdf58163e3e05dda55955501dec'
SETTINGS = {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'min_p': 0.0,
            'presence_penalty': 1.5, 'repeat_penalty': 1.0, 'max_tokens': 256,
            'cache_prompt': False, 'chat_template_kwargs': {'enable_thinking': False}}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024**2):
            result.update(chunk)
    return result.hexdigest()


def main():
    if sys.flags.optimize:
        raise RuntimeError('optimized Python disables required integrity and validation checks')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--group', choices=('authored', 'film-first', 'film-last'), required=True)
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(ROOT):
        parser.error('raw output must be outside the repository')
    fixture = (ROOT / 'tests/fixtures/translation_compare.json').read_bytes()
    assert hashlib.sha256(fixture).hexdigest() == FIXTURE_SHA
    cases = json.loads(fixture)['cases']
    selected = {'authored': cases[56:], 'film-first': cases[:28], 'film-last': cases[28:56]}[args.group]
    report = {'model': MODEL, 'model_revision': REVISION, 'quantization': 'Q6_K',
              'fixture_sha256': FIXTURE_SHA, 'group': args.group,
              'code_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'prompt': PROMPT, 'settings': SETTINGS, 'device': 'Linux CPU', 'threads': 4,
              'context_size': 2048, 'parallel_slots': 1, 'rows': [], 'complete': False,
              'python_external_network_attempts': 0,
              'network_limit': 'Native server uses --offline, local weights, loopback and an ephemeral API key. Python audit does not observe native server syscalls; strace is unavailable (ptrace EPERM).'}
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)

    def save():
        temporary = args.out.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(args.out)

    def audit(event, values):
        if event == 'socket.connect' and values[1][0] != '127.0.0.1':
            report['python_external_network_attempts'] += 1
            raise RuntimeError('external_network_blocked')
        if event == 'socket.getaddrinfo' and values[0] != '127.0.0.1':
            report['python_external_network_attempts'] += 1
            raise RuntimeError('external_network_blocked')

    sys.addaudithook(audit)
    began = time.monotonic()
    process = None
    try:
        report['model_sha256'] = digest(args.model)
        assert report['model_sha256'] == MODEL_SHA
        files = {p.name: digest(p) for p in sorted(args.runtime.iterdir())
                 if p.is_file() and (p.name == 'llama-server' or '.so' in p.name)}
        report['runtime_file_hashes'] = files
        report['runtime_manifest_sha256'] = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
        assert report['runtime_manifest_sha256'] == 'd1488f84f35c94c25660b5a6d205aa431230ec2a047c0da0f2f000e2ea0bdfb5'
        report['verification_seconds'] = round(time.monotonic() - began, 3)
        server = args.runtime.resolve() / 'llama-server'
        report['runtime_version'] = subprocess.check_output([str(server), '--version'], text=True, stderr=subprocess.STDOUT, timeout=10).strip()
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            port = reserve.getsockname()[1]
        key = secrets.token_hex(32)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, payload=None, timeout=60, evidence=None):
            raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode()
            req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=raw,
                                         headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=timeout) as response:
                    body = response.read().decode('utf-8')
                    if evidence is not None:
                        evidence['http_status'] = response.status
                        evidence['raw_response'] = body
                    return json.loads(body)
            except urllib.error.HTTPError as error:
                if evidence is not None:
                    evidence['http_status'] = error.code
                    evidence['raw_response'] = error.read().decode('utf-8', errors='replace')
                raise

        command = [str(server), '--model', str(args.model.resolve()), '--alias', 'qwen35-fixture',
                   '--host', '127.0.0.1', '--port', str(port), '--offline', '--no-webui',
                   '--threads', '4', '--threads-batch', '4', '--ctx-size', '2048',
                   '--parallel', '1', '--n-gpu-layers', '0', '--reasoning', 'off', '--log-disable']
        environment = {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OMP_NUM_THREADS': '4',
                       'HF_HUB_OFFLINE': '1', 'LLAMA_API_KEY': key}
        with args.out.with_suffix('.server.log').open('xb') as log:
            started = time.monotonic()
            process = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            while True:
                if process.poll() is not None:
                    raise RuntimeError('server_exited_during_startup')
                if time.monotonic() - started > 45:
                    raise TimeoutError('server_startup_timeout')
                try:
                    models = request('/v1/models', timeout=1)
                    assert any(m['id'] == 'qwen35-fixture' for m in models['data'])
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.2)
            report['startup_seconds'] = round(time.monotonic() - started, 3)
            properties = request('/props')
            template = properties.get('chat_template', '')
            assert template
            report['chat_template'] = template
            report['chat_template_sha256'] = hashlib.sha256(template.encode()).hexdigest()
            save()
            for case in selected:
                if time.monotonic() - began > 450:
                    raise TimeoutError('group_budget_exhausted')
                target = {k: case[k] for k in ('id', 'text', 'before', 'after')}
                seed = 20260907 + next(i for i, c in enumerate(cases) if c['id'] == case['id'])
                payload = dict(SETTINGS, model='qwen35-fixture', seed=seed,
                               messages=[{'role': 'system', 'content': PROMPT},
                                         {'role': 'user', 'content': json.dumps([target], ensure_ascii=False)}])
                started = time.monotonic()
                row = {'id': case['id'], 'seed': seed,
                       'request_sha256': hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest(),
                       'valid': False}
                report['rows'].append(row)
                save()
                try:
                    response = request('/v1/chat/completions', payload, evidence=row)
                    row['response'] = response
                except Exception as error:
                    row['error'] = type(error).__name__
                    raise
                finally:
                    row['seconds'] = round(time.monotonic() - started, 3)
                    save()
                try:
                    choice, = response['choices']
                    row['raw_output'] = choice['message']['content']
                    parsed = json.loads(row['raw_output'])
                    assert type(parsed) is dict and set(parsed) == {'translations'}
                    assert type(parsed['translations']) is list
                    value, = parsed['translations']
                    assert type(value) is dict and set(value) == {'id', 'text'} and value['id'] == case['id']
                    assert type(value['text']) is str and value['text'].strip() and choice['finish_reason'] == 'stop'
                    assert not choice['message'].get('reasoning_content')
                    row['text'] = value['text']
                    row['valid'] = True
                except (ValueError, KeyError, TypeError, AssertionError):
                    row['error'] = 'invalid_translation_response'
                save()
                print(json.dumps({'id': row['id'], 'valid': row['valid'], 'seconds': row['seconds']}), flush=True)
            report['complete'] = True
    except BaseException as error:
        report['execution_error'] = type(error).__name__
        report['execution_error_message'] = str(error)
        raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                report['server_exit_code'] = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                report['server_exit_code'] = process.wait(timeout=5)
        report['elapsed_seconds'] = round(time.monotonic() - began, 3)
        save()
    return 0 if all(row['valid'] for row in report['rows']) else 1


if __name__ == '__main__':
    sys.exit(main())
