#!/usr/bin/env python3
"""Misura la velocita con il protocollo core-speed contro un server OpenAI-compatibile (llama-server, LM Studio, mlx_lm.server, ...)
e scrive direttamente un file results/<piattaforma>/<data>-<slug>.json pronto per il push.

Esempio (Mac con llama-server gia avviato su :8080):
    python tools/speedtest.py --platform mac --author Pietro --title "Qwen3.8-27B Q4 base" \
        --model-name Qwen3.8-27B --quant Q4_K_M --engine llama.cpp --engine-version b12141 \
        --chip "M3 Max" --ram-gb 64 --os "macOS 15" --port 8080

Se il server e llama.cpp usa i suoi timings (predicted_per_second, draft_n, draft_n_accepted); altrimenti stima
t/s = token generati / tempo (campo metrics.tps_method = "wallclock", meno preciso).
Solo libreria standard, funziona su Windows, Mac e Linux.
"""
import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO = json.loads((ROOT / 'benchmarks' / 'core-speed' / 'prompts.json').read_text(encoding='utf-8'))


def chat(base, model, prompt, seed, key=None):
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': PROTO['max_tokens'],
            'temperature': PROTO['temperature'], 'seed': seed, 'stream': False}
    h = {'Content-Type': 'application/json'}
    if key:
        h['Authorization'] = 'Bearer ' + key
    req = urllib.request.Request(base + '/v1/chat/completions', json.dumps(body).encode(), h)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1800) as r:
        d = json.loads(r.read())
    return d, time.time() - t0


def main():
    a = argparse.ArgumentParser()
    a.add_argument('--platform', required=True, choices=['windows', 'mac', 'linux'])
    a.add_argument('--author', required=True)
    a.add_argument('--title', required=True)
    a.add_argument('--model-name', required=True)
    a.add_argument('--quant')
    a.add_argument('--size-gb', type=float)
    a.add_argument('--repo')
    a.add_argument('--engine', default='llama.cpp')
    a.add_argument('--engine-version')
    a.add_argument('--engine-args', default='', help='argomenti usati per avviare il server, tra virgolette')
    a.add_argument('--gpu')
    a.add_argument('--chip')
    a.add_argument('--ram-gb', type=float)
    a.add_argument('--os')
    a.add_argument('--port', type=int, default=8080)
    a.add_argument('--host', default='127.0.0.1')
    a.add_argument('--api-key')
    a.add_argument('--category', default='speed', choices=['speed', 'speculative'])
    a.add_argument('--notes', default='')
    a.add_argument('--summary')
    a.add_argument('--out-dir')
    a = a.parse_args()
    if not (a.gpu or a.chip):
        sys.exit('serve --gpu o --chip')
    base = f'http://{a.host}:{a.port}'
    chat(base, a.model_name, 'Say hi.', 1, a.api_key)  # warm-up, non conta
    by, dn, da, method = {}, 0, 0, 'timings'
    allv = []
    for k, q in PROTO['prompts'].items():
        v = []
        for sd in PROTO['seeds']:
            d, el = chat(base, a.model_name, q, sd, a.api_key)
            n = (d.get('usage') or {}).get('completion_tokens') or 0
            tm = d.get('timings') or {}
            if tm.get('predicted_per_second'):
                tps = tm['predicted_per_second']
                n = tm.get('predicted_n', n)
                dn += tm.get('draft_n') or 0
                da += tm.get('draft_n_accepted') or 0
            else:
                tps, method = (n / el if el else 0), 'wallclock'
            if n >= PROTO['min_tokens']:
                v.append(tps)
        by[k] = round(statistics.median(v), 1) if v else None
        allv += v
        print(k, by[k], 't/s')
    vals = [x for x in by.values() if x]
    if not vals:
        sys.exit('nessuna misura valida (il modello ha generato meno di 40 token?)')
    m = {'decode_tps_1': round(statistics.median(allv), 1), 'tps_media': round(sum(vals) / len(vals), 1), 'tps_by_type': by, 'tps_method': method}
    if dn:
        m['draft_acceptance_pct'] = round(100 * da / dn, 1)
    today = date.today().isoformat()
    slug = re.sub(r'[^a-z0-9._-]+', '-', a.title.lower()).strip('-')
    e = {
        'schema': 1, 'id': f'{today}-{slug}', 'platform': a.platform, 'author': a.author, 'date': today, 'category': a.category, 'status': 'ok',
        'title': a.title, 'reference': False,
        'model': {'name': a.model_name, 'repo': a.repo, 'quant': a.quant, 'size_gb': a.size_gb},
        'engine': {'name': a.engine, 'version': a.engine_version, 'args': a.engine_args.split()},
        'hardware': {k: v for k, v in {'gpu': a.gpu, 'chip': a.chip, 'ram_gb': a.ram_gb, 'os': a.os}.items() if v},
        'benchmark': {'suite': 'core-speed', 'version': PROTO['version'], 'harness': 'tools/speedtest.py'},
        'metrics': m, 'notes': a.notes, 'tags': [],
        'summary': a.summary or f"{m['tps_media']} t/s medi su 4 tipi di prompt (core-speed v{PROTO['version']}), {m['decode_tps_1']} t/s mediana."
        + (f" Accettazione drafter {m['draft_acceptance_pct']}%." if dn else ''),
    }
    out = Path(a.out_dir) if a.out_dir else ROOT / 'results' / a.platform
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{e['id']}.json"
    f.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding='utf-8')
    print('scritto', f)
    print('ora: python tools/build.py && git add -A && git commit -m "..." && git push')


if __name__ == '__main__':
    main()
