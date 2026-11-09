#!/usr/bin/env python3
"""Esporta la coda della Fabbrica Windows in data/queue.json (da eseguire a ogni ciclo lato Windows).
Uso: python tools/legacy/export_queue.py <cartella fabbrica>
Gli altri collaboratori mantengono le proprie voci in data/queue.json con platform diverso (stesso formato)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
F = Path(sys.argv[1])
done = {json.loads(l)['name'] for l in (F / 'risultati.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()}
coda = json.loads((F / 'coda.json').read_text(encoding='utf-8'))
WHY = json.loads((ROOT / 'data' / 'queue_notes.json').read_text(encoding='utf-8')) if (ROOT / 'data' / 'queue_notes.json').exists() else {}


def kind(x):
    if x.get('harness'):
        return 'agente reale (' + ', '.join(x['harness']) + ')'
    if x.get('speed_only'):
        return 'velocita (~3 min)'
    if x.get('arm'):
        return 'armature'
    if x.get('serio') and x.get('serio_parts'):
        return 'Suite S parziale: ' + ', '.join(x['serio_parts'])
    if x.get('serio'):
        return 'Suite S + agente-mini (~40 min)'
    return 'tiny (~10 min, saturo)'


items = []
for x in coda:
    if x['name'] in done:
        continue
    n = len(items) + 1
    items.append({'order': n, 'name': x['name'], 'kind': kind(x), 'why': x.get('consulenza') or WHY.get(x['name'], ''), 'repo': x.get('repo')})
(ROOT / 'data' / 'queue.json').write_text(json.dumps({'platform': 'windows', 'updated': __import__('datetime').date.today().isoformat(), 'items': items}, ensure_ascii=False, indent=1), encoding='utf-8')
print(len(items), 'in coda')
