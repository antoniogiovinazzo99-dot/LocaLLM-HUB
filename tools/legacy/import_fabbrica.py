#!/usr/bin/env python3
"""Importa risultati.jsonl della Fabbrica (runner Windows di Motti) come file results/windows/*.json.

Una tantum, per la storia dei test. I nuovi test vanno scritti direttamente nel formato di docs/SCHEMA.md.
Uso: python tools/legacy/import_fabbrica.py <percorso/risultati.jsonl>
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / 'results' / 'windows'
HW = {'gpu': 'NVIDIA RTX 3060 12GB', 'ram_gb': 16, 'os': 'Windows 11', 'cpu': 'Ryzen 5 5600G'}

# note scritte a mano per i risultati che contano (verdetto, non solo numeri)
NOTE = {
    'agents-a1-35b-iq2m': 'Il tiny dice 91,2 ma la Suite S (agents-a1-35b-iq2m-serio) dice 60,6: il tiny e quasi saturo e non vede il costo della compressione a 2 bit.',
    'agents-a1-35b-iq2m-serio': 'Suite S + agente-mini. Rispetto al Q4 perde circa 8 punti di indice d uso e scende al 50% sull agente: IQ2_M non e un sostituto del Q4.',
    'agents-a1-35b-q4-serio': 'Pari a Flash-Next sulla Suite S (69,1 vs 68,4) e sull agente (83%), alla stessa velocita. Intelligenza pari, non meglio.',
    'op-flashnext-ref-serio2': 'Riferimento Flash-Next rieseguito con budget alto: il numero da usare per i confronti seri (il primo giro aveva campioni troppo piccoli).',
    'op-flashnext-ref-p10': 'Primo giro del riferimento con budget basso: molte parti con 3-12 campioni, poco affidabile. Vedi op-flashnext-ref-serio2.',
    'sp-27b-xxs-dspine': 'FALLITO: il server del fork llama-dspine si pianta (timeout dopo ~2 ore). Nessun numero su DSpine.',
    'op-qwen38-27b-iq2s-dspine': 'FALLITO: connessione chiusa dal server del fork llama-dspine. Primo tentativo, IQ2_S + drafter Q8 + contesto 32K saturava la VRAM.',
    'op-qwen38-27b-iq2s-dflash2': 'Peggiora (12 vs 20 t/s): VRAM piena e accettazione del drafter solo 37%. Rifatto in sp-27b-xxs-dflash2 con IQ2_XXS e ctx 8K.',
    'sp-27b-xxs-dflash2': 'DFlash2 su IQ2_XXS, ctx 8K, drafter Q4: +63% rispetto al base (33,0 vs 20,2 t/s). Sul codice resta lento (25,6) perche l accettazione cala.',
    'op-ornith35-mtp-imini': 'MTP piu lento del no-MTP (38,5 vs 43,9 t/s medi) con accettazione 48%.',
    'ornith-1.5-9b-arm': 'Armature su matematica (100 domande): voto su 5 98% in 10,8 min, programma eseguito (PAL) 83-86% in 0,8 min. Manca ancora la base senza armatura sugli stessi 100.',
    'agents-a1-4b-arm': 'Con armatura peggiora: 72,7 vs 77,6 della base, il codice scende da 58 a 42.',
}
FORMAT_NOTE = 'Colonna lungo = 0 NON valida: bug del runner (server a 4 slot da 8K, il test mandava ~41K token: errore di contesto contato come risposta sbagliata). Corretto con slot da 49K, vedi a1-35b-q4-lungo-fix.'


def slug(s):
    return re.sub(r'[^a-z0-9._-]+', '-', s.lower()).strip('-')


def quant_of(f):
    m = re.search(r'(UD-)?(I?Q\d(?:_[A-Z0-9]+)*|BF16|F16)', f or '', re.I)
    return m.group(0).upper() if m else None


def scrub(a):
    out = []
    for x in a:
        x = str(x).replace('\\', '/')
        if re.match(r'^[A-Za-z]:/', x) or x.startswith('<HOME>'):
            x = '<PATH>/' + x.rsplit('/', 1)[-1]
        out.append(x)
    return out


def convert(r):
    it = r.get('item') or {}
    name = r['name']
    date = (r.get('ts') or '2026-11-09')[:10]
    cat = 'quality-tiny'
    if r.get('tps_tipi'):
        cat = 'speed'
    elif r.get('arm'):
        cat = 'armature'
    elif r.get('serio'):
        cat = 'quality-suite-s'
    spec = any(a in (it.get('args') or []) for a in ('--spec-type', '-md'))
    if cat == 'speed' and spec:
        cat = 'speculative'
    m = {}
    mp = {'decode_tps_1': 'decode_tps_1', 'decode_tps': 'decode_tps_4', 'prompt_tps': 'prompt_tps', 'tps_media': 'tps_media', 'mmlu': 'mmlu', 'arc': 'arc', 'gsm': 'gsm',
          'code12': 'code12', 'humaneval': 'humaneval', 'q_medio': 'q_medio', 'parole_inventate_pct': 'invented_words_pct', 'ago64k': 'needle_64k', 'load_s': 'load_s', 'indice_uso': 'indice_uso'}
    for k, v in mp.items():
        if r.get(k) is not None:
            m[v] = r[k]
    if r.get('tps_tipi'):
        m['tps_by_type'] = {k: v['tps'] for k, v in r['tps_tipi'].items()}
        acc = {k: v['accettazione'] for k, v in r['tps_tipi'].items() if v.get('accettazione') is not None}
        if acc:
            m['draft_acceptance_by_type'] = acc
            m['draft_acceptance_pct'] = acc.get('codice')
    if r.get('serio'):
        for k, v in r['serio'].items():
            m[k] = v['acc']
        m['suite_s_samples'] = {k: f"{v['n']}/{v['n_tot']}" for k, v in r['serio'].items()}
    if r.get('agente'):
        a = r['agente']
        m['agente_mini'] = a['agente_mini']
        m['agente_parziale'] = a['parziale']
        m['agente_turni_medi'] = a['turni_medi']
        m['agente_chiamate_non_valide'] = a['non_valide']
    if r.get('arm'):
        m['armature'] = {k: {'acc': v['acc'], 'n': v['n'], 'min': v['min']} for k, v in r['arm'].items() if isinstance(v, dict) and 'acc' in v}
    ok = not r.get('errore') and bool(m)
    repo = r.get('repo')
    f = r.get('file')
    notes = [NOTE.get(name)] if NOTE.get(name) else []
    if r.get('serio'):
        notes.append(FORMAT_NOTE)
    if it.get('consulenza'):
        notes.append(it['consulenza'])
    e = {
        'schema': 1, 'id': f'{date}-{slug(name)}', 'platform': 'windows', 'author': 'Motti', 'date': date, 'category': cat,
        'status': 'ok' if ok else 'failed', 'title': name, 'reference': bool(r.get('ref')),
        'model': {'name': (repo or name).split('/')[-1], 'repo': repo, 'file': f, 'quant': quant_of(f), 'size_gb': r.get('size_gb')},
        'engine': {'name': 'strata' if (it.get('backend') == 'strata' or r.get('ref')) else 'llama.cpp', 'version': r.get('engine'), 'args': scrub(it.get('args') or [])},
        'hardware': dict(HW),
        'benchmark': {'suite': {'quality-suite-s': 'suite-s+agente-mini', 'speed': 'speed-4-prompts', 'speculative': 'speed-4-prompts', 'armature': 'armature-math+mcq'}.get(cat, 'tiny-fabbrica'), 'harness': 'fabbrica-runner'},
        'metrics': m if ok else {},
        'notes': ' '.join(notes),
        'tags': [t for t in ['reference' if r.get('ref') else None, 'speculative' if spec else None] if t],
    }
    if not ok:
        e['summary'] = f"Test fallito: {r.get('errore')}." + (' ' + NOTE[name] if name in NOTE else '')
    else:
        bits = []
        if 'q_medio' in m:
            bits.append(f"qualita tiny {m['q_medio']}")
        if 'indice_uso' in m:
            bits.append(f"indice d uso Suite S {m['indice_uso']}")
        if 'agente_mini' in m:
            bits.append(f"agente-mini {m['agente_mini']}%")
        if 'decode_tps_1' in m:
            bits.append(f"{m['decode_tps_1']} t/s a un flusso")
        if 'tps_media' in m:
            bits.append(f"{m['tps_media']} t/s medi su 4 tipi di prompt")
        if 'draft_acceptance_pct' in m and m['draft_acceptance_pct'] is not None:
            bits.append(f"accettazione drafter sul codice {m['draft_acceptance_pct']}%")
        if r.get('arm'):
            best = max(m['armature'].items(), key=lambda kv: kv[1]['acc'])
            bits.append(f"armature: migliore {best[0]} {best[1]['acc']}%")
        e['summary'] = (', '.join(bits) or 'risultato registrato').capitalize() + '.' + (' ' + NOTE[name] if name in NOTE else '')
    return e


def main(path):
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            seen[r['name']] = r  # ultimo risultato per nome
    for r in seen.values():
        e = convert(r)
        (OUT / f"{e['id']}.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding='utf-8')
    print(len(seen), 'esperimenti scritti in', OUT)


if __name__ == '__main__':
    main(sys.argv[1])
