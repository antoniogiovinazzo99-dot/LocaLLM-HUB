"""duro.py su un insieme di SVILUPPO disgiunto dal campione standard (seed 2026, n=15) usato come TEST.
Serve per mettere a punto prompt/knowledge pack senza barare: si regola su DEV, si misura una volta su TEST.
Uso: come duro.py (stessi argomenti); --n=K e il numero di domande DEV per categoria (mmlu: 1 per materia, come duro)."""
import os, random, sys

MP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'LocaLLM-HUB', 'benchmarks', 'mac-pietro')
sys.path.insert(0, MP)
import duro  # noqa: E402


def chiave(item):
    kind, x, gold = item
    return (kind, x['task_id'] if isinstance(x, dict) else x[:200])


_load = duro.load


def load_dev(sets, n):
    test = {chiave(i) for i in _load(sets, 15)}          # campione standard = TEST, mai usato per regolare
    Rnd = random.Random
    duro.random.Random = lambda seed=None: Rnd(777)       # altro seme per pescare DEV
    try:
        cand = _load(sets, n + 20)
    finally:
        duro.random.Random = Rnd
    per, out = {}, []
    lim = {'mmlu': max(14, n)}
    for it in cand:
        if chiave(it) in test:
            continue
        k = it[0]
        if per.get(k, 0) >= lim.get(k, n):
            continue
        per[k] = per.get(k, 0) + 1
        out.append(it)
    return out


duro.load = load_dev
duro.OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'risultati', 'duro-dev.jsonl')
duro.main()
