#!/usr/bin/env python3
"""Valida i risultati e rigenera gli indici.

Uso:
    python tools/build.py            # valida tutto e riscrive results/<piattaforma>/index.json
    python tools/build.py --check    # solo validazione (usata dalla CI), esce con codice 1 se ci sono errori

Ogni esperimento e un file results/<piattaforma>/<data>-<slug>.json (schema in docs/SCHEMA.md).
Gli indici sono per piattaforma: chi lavora su Windows tocca solo results/windows/index.json,
chi lavora su Mac solo results/mac/index.json, quindi non ci sono mai conflitti di merge.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {'windows', 'mac', 'linux'}
CATEGORIES = {'speed', 'quality-tiny', 'quality-suite-s', 'agent', 'armature', 'speculative', 'harness', 'other'}
STATUSES = {'ok', 'partial', 'failed'}
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
ID_RE = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
# metriche mostrate in evidenza nelle card (in questo ordine, le prime 4 presenti)
HEADLINE = ['decode_tps_1', 'tps_media', 'duro_pct', 'agente_pct', 'harness_omp_pieno_pct', 'harness_omp_parziale_pct',
            'q_medio', 'indice_uso', 'agente_mini', 'humaneval', 'draft_acceptance_pct', 'prompt_tps']


def validate(e, path):
    err = []

    def need(cond, msg):
        if not cond:
            err.append(f'{path.name}: {msg}')
    need(e.get('schema') == 1, 'schema deve essere 1')
    need(isinstance(e.get('id'), str) and ID_RE.match(e.get('id', '')), 'id mancante o non valido (minuscolo, cifre, - . _)')
    need(e.get('id') == path.stem, f"id deve coincidere con il nome file ({path.stem})")
    need(e.get('platform') in PLATFORMS, f'platform deve essere uno di {sorted(PLATFORMS)}')
    need(path.parent.name == e.get('platform'), 'il file deve stare in results/<platform>/')
    need(isinstance(e.get('author'), str) and e.get('author'), 'author mancante')
    need(DATE_RE.match(str(e.get('date', ''))), 'date nel formato AAAA-MM-GG')
    need(e.get('category') in CATEGORIES, f'category deve essere una di {sorted(CATEGORIES)}')
    need(e.get('status') in STATUSES, f'status deve essere uno di {sorted(STATUSES)}')
    need(isinstance(e.get('title'), str) and e.get('title'), 'title mancante')
    need(isinstance(e.get('summary'), str) and e.get('summary'), 'summary mancante (1-3 frasi: cosa dice questo test)')
    m = e.get('model')
    need(isinstance(m, dict) and m.get('name'), 'model.name mancante')
    h = e.get('hardware')
    need(isinstance(h, dict) and (h.get('gpu') or h.get('chip')), 'hardware.gpu o hardware.chip mancante')
    need(isinstance(e.get('metrics'), dict), 'metrics deve essere un oggetto (puo essere vuoto se status=failed)')
    if e.get('status') != 'failed':
        need(bool(e.get('metrics')), 'metrics vuoto: se il test e fallito usa status=failed e spiega in summary')
    return err


def headline(metrics):
    out = {}
    for k in HEADLINE:
        v = metrics.get(k)
        if isinstance(v, (int, float)):
            out[k] = v
        if len(out) == 4:
            break
    return out


def main(check_only=False):
    errors, total = [], 0
    for plat in sorted(PLATFORMS):
        d = ROOT / 'results' / plat
        if not d.exists():
            continue
        index = []
        hidden_failed = 0
        for f in sorted(d.glob('*.json')):
            if f.name == 'index.json':
                continue
            try:
                e = json.loads(f.read_text(encoding='utf-8'))
            except Exception as ex:
                errors.append(f'{f.name}: JSON non valido ({ex})')
                continue
            errors += validate(e, f)
            total += 1
            if e.get('status') == 'failed':
                # i fallimenti restano nel repo (onesta), ma non sporcano la dashboard
                hidden_failed += 1
                continue
            m = e.get('model') or {}
            index.append({
                'id': e.get('id'), 'file': f'results/{plat}/{f.name}', 'platform': plat, 'author': e.get('author'),
                'date': e.get('date'), 'category': e.get('category'), 'status': e.get('status'), 'title': e.get('title'),
                'summary': e.get('summary'), 'model': m.get('name'), 'repo': m.get('repo'), 'quant': m.get('quant'), 'size_gb': m.get('size_gb'),
                'engine': (e.get('engine') or {}).get('name'), 'ref': bool(e.get('reference')),
                'headline': headline(e.get('metrics') or {}), 'tags': e.get('tags', []),
            })
        index.sort(key=lambda x: (x['date'] or '', x['id'] or ''), reverse=True)
        if not check_only:
            (d / 'index.json').write_text(json.dumps({'platform': plat, 'count': len(index), 'hidden_failed': hidden_failed, 'experiments': index}, ensure_ascii=False, indent=1), encoding='utf-8')
    for x in errors:
        print('ERRORE', x)
    print(f'{total} esperimenti, {len(errors)} errori')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main('--check' in sys.argv))
