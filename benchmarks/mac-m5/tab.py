#!/usr/bin/env python3
"""Tabella compatta dei risultati: tab.py [prefisso_id ...]"""
import json, os, sys
D = os.path.dirname(os.path.abspath(__file__))
pre = sys.argv[1:]
for line in open(os.path.join(D, 'risultati', 'notte.jsonl')):
    r = json.loads(line)
    if pre and not any(r['id'].startswith(p) for p in pre):
        continue
    parts = []
    for k, v in r.get('tests', {}).items():
        n = k.split()[0]
        if 'errore' in v:
            parts.append(f"{k}: ERR {v['errore'][-60:]!r}")
        elif n == 'speed':
            parts.append(f"nuovo {v['tps']}" + (f" [{v['min']}-{v['max']}]" if v.get('giri') else '') + f" (acc {v.get('acc', '-')})")
        elif n == 'long':
            parts.append(f"lungo15k: legge {v['lettura_tps']} scrive {v['tps']} [prosa {v['prosa']} json {v['json']} cod {v['codice']}] acc {v.get('acc', '-')}")
        elif n == 'core':
            parts.append(f"core {v.get('tps')} acc {v.get('acc')}")
        elif n == 'agente':
            parts.append(f"agente {v.get('corrette')} {v.get('sec_compito')}s")
        elif n in ('ufficiale', 'bench2', 'bench3', 'bench4'):
            parts.append(f"{k.split(' --timeout')[0]}: {v.get('pct')}% ({v.get('corrette')}) {v.get('sec_domanda')}s/d")
        elif n in ('duro', 'durodev'):
            parts.append(f"{k.split(' --timeout')[0].replace('', '').replace('', '')}: {v.get('pct')}% ({v.get('ok')}/{v.get('n')}) {v.get('cat')} {v.get('sec_domanda')}s/d tronc {v.get('troncate')}")
        elif n == 'agentemini':
            parts.append(f"amini pieni {v.get('pieni_pct')}% parz {v.get('parziale_pct')}% {v.get('sec')}s nv {v.get('non_valide')}")
        else:
            parts.append(f"{k}: {json.dumps(v, ensure_ascii=False)[:200]}")
    m = r.get('mem', {})
    print(f"{r['id']:<26} | " + ' | '.join(parts) + (f" | swap {m.get('swap_prima', 0):.0f}->{m.get('swap_dopo', 0):.0f} oom {m.get('oom_gpu')}" if m else '') + (f" | ERRORE {r['errore'][-80:]!r}" if r.get('errore') else ''))
