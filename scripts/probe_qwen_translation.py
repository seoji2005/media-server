"""Offline, fixed public-fixture comparison; never reads a user's media library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_translation_compare import PROMPT

MODEL = 'Qwen/Qwen3-4B-Instruct-2507'
REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
FIXTURE_SHA = 'd6a3734789dd02e5d9425635e81484fa187e1fdf58163e3e05dda55955501dec'
WEIGHTS = {
    'model-00001-of-00003.safetensors':'75311d91bb08cf0b882913da464a1e722a31fb44db35208663487efb7a3d8ed6',
    'model-00002-of-00003.safetensors':'0b48adbb1f60e901153d91907ba11ce63bd4b8b584482e730f48808d055dfba1',
    'model-00003-of-00003.safetensors':'7dd39ccca5e4de123c74c14af44c9bf2eb75df33b4614382af0134528e060d5d',
}
SETTINGS = {'do_sample':True, 'temperature':0.7, 'top_p':0.8, 'top_k':20,
            'min_p':0.0, 'max_new_tokens':256, 'eos_token_id':[151645,151643], 'pad_token_id':151643}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(8*1024**2):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--group', choices=('authored','film-first','film-last'), required=True)
    parser.add_argument('--precision', choices=('float32','bfloat16'), default='float32')
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(ROOT):
        parser.error('raw experiment output belongs outside the repository')
    raw = (ROOT/'tests/fixtures/translation_compare.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == FIXTURE_SHA
    cases = json.loads(raw)['cases']
    selected = {'authored':cases[56:], 'film-first':cases[:28], 'film-last':cases[28:56]}[args.group]
    assert len(cases) == 80 and len({c['id'] for c in cases}) == 80
    seed_by_id = {c['id']:20260907+i for i,c in enumerate(cases)}
    targets = [{k:c[k] for k in ('id','text','before','after')} for c in selected]
    report = {'model':MODEL, 'model_revision':REVISION, 'fixture_sha256':FIXTURE_SHA,
              'code_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'group':args.group, 'device':'Linux CPU '+args.precision, 'threads':4, 'batch_size':1,
              'prompt':PROMPT, 'settings':SETTINGS, 'ids':[c['id'] for c in selected],
              'context':'Same frozen adjacent context/prompt as Gemini; MADLAD baseline is sentence-only.',
              'network_attempts':0, 'rows':[], 'complete':False}
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2)

    def save():
        temp = args.out.with_suffix(args.out.suffix+'.tmp')
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(args.out)

    def audit(event, values):
        if event in ('socket.connect','socket.getaddrinfo'):
            report['network_attempts'] += 1
            raise RuntimeError('network_blocked')

    for key in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK','ORT_DISABLE_TELEMETRY'):
        os.environ[key] = '1'
    sys.addaudithook(audit)
    from media_clarity.models import require_private_runtime
    require_private_runtime()
    began = time.monotonic()
    try:
        report['weight_hashes'] = {name:digest(args.model_dir/name) for name in WEIGHTS}
        assert report['weight_hashes'] == WEIGHTS
        report['file_hashes'] = {name:digest(args.model_dir/name) for name in
                                 ('config.json','generation_config.json','tokenizer.json','tokenizer_config.json','model.safetensors.index.json')}
        report['verification_seconds'] = round(time.monotonic()-began,3)
        import torch
        import transformers
        torch.set_num_threads(4)
        report['runtime'] = {'torch':torch.__version__, 'transformers':transformers.__version__}
        load_start = time.monotonic()
        tokenizer = transformers.AutoTokenizer.from_pretrained(args.model_dir,local_files_only=True,trust_remote_code=False)
        model = transformers.AutoModelForCausalLM.from_pretrained(args.model_dir,local_files_only=True,trust_remote_code=False,
                                                                 torch_dtype=getattr(torch,args.precision),attn_implementation='sdpa')
        model.eval()
        report['load_seconds'] = round(time.monotonic()-load_start,3)
        save()
        for target in targets:
            seed = seed_by_id[target['id']]; torch.manual_seed(seed)
            messages = [{'role':'system','content':PROMPT},
                        {'role':'user','content':json.dumps([target],ensure_ascii=False)}]
            prompt = tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
            inputs = tokenizer(prompt,return_tensors='pt')
            start = time.monotonic()
            with torch.inference_mode():
                generated = model.generate(**inputs,**SETTINGS)[0,inputs['input_ids'].shape[1]:]
            seconds = time.monotonic()-start
            output = tokenizer.decode(generated,skip_special_tokens=True)
            row = {'id':target['id'], 'seed':seed, 'request_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                   'input_tokens':inputs['input_ids'].numel(), 'output_tokens':len(generated),
                   'seconds':round(seconds,3), 'raw_output':output,
                   'finish':'eos' if int(generated[-1]) in SETTINGS['eos_token_id'] else 'length', 'valid':False}
            try:
                parsed = json.loads(output)
                translations = parsed['translations']
                assert type(parsed) is dict and set(parsed) == {'translations'}
                assert type(translations) is list and len(translations) == 1
                value = translations[0]
                assert type(value) is dict and set(value) == {'id','text'} and value['id'] == target['id']
                assert type(value['text']) is str and value['text'].strip() and row['finish'] == 'eos'
                row['text'] = value['text']; row['valid'] = True
            except (ValueError,KeyError,TypeError,AssertionError):
                row['error'] = 'invalid_translation_response'
            report['rows'].append(row)
            report['peak_rss_mib'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,3)
            save()
            print(json.dumps({'id':row['id'],'valid':row['valid'],'tokens':row['output_tokens'],'seconds':row['seconds'] }),flush=True)
        report['complete'] = True
    except BaseException as exc:
        report['execution_error'] = type(exc).__name__
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-began,3)
        save()
    return 0 if all(r['valid'] for r in report['rows']) else 1


if __name__ == '__main__':
    sys.exit(main())
