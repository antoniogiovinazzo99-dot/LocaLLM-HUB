"""Statistica onesta per la Fabbrica (consulenza Opus, 8/11/2026). Solo lettura: non tocca il runner.

Uso:
  python -I statistica.py                      -> tabella con intervalli di confidenza (Wilson 95%) per ogni run in risultati.jsonl
  python -I statistica.py NOME_A NOME_B        -> confronto appaiato domanda per domanda (McNemar esatto) usando log/<nome>-items.json
  python -I statistica.py --mde                -> differenza minima rilevabile per n domande

Perche serve: con 100 domande l'errore standard di una percentuale vicino al 67% e ~4,7 punti (IC95 circa +-9);
codice12 ha 12 compiti -> ogni compito vale 8,3 punti e da solo sposta Q medio di 2,1 punti.
"""
import json, math, pathlib, sys

ROOT = pathlib.Path(r'<HOME>\llm\fabbrica')
N = {'mmlu': 100, 'arc': 100, 'gsm': 100, 'code12': 12, 'humaneval': 82}


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 1), round(100 * (c + h), 1)


def binom_two_sided(b, c):
    """McNemar esatto: b = solo A giusto, c = solo B giusto."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def q_pesato(r):
    """Q medio pesato per numero di item (riduce il peso del rumore di codice12)."""
    num = den = 0
    for k, n in N.items():
        if r.get(k) is not None and k != 'humaneval':
            num += r[k] * n
            den += n
    return round(num / den, 1) if den else None


def tabella():
    rows = [json.loads(l) for l in (ROOT / 'risultati.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f"{'nome':34} {'MMLU':>16} {'ARC':>16} {'GSM':>16} {'code12':>16} {'Qmed':>6} {'Qpes':>6} {'vram_altro':>10}")
    for r in rows:
        if r.get('q_medio') is None:
            continue
        cells = []
        for k in ('mmlu', 'arc', 'gsm', 'code12'):
            v = r.get(k)
            if v is None:
                cells.append(f"{'-':>16}")
                continue
            lo, hi = wilson(round(v * N[k] / 100), N[k])
            cells.append(f"{v:5.1f} [{lo:4.0f}-{hi:3.0f}]".rjust(16))
        print(f"{r['name'][:34]:34} {' '.join(cells)} {r['q_medio']:6} {q_pesato(r):6} {r.get('hw', {}).get('vram_other_MiB', '?'):>10}")


def items(name):
    p = ROOT / 'log' / f'{name}-items.json'
    d = json.load(open(p))
    out = {}
    for i, (kind, ok, _ans) in enumerate(d['mcq']):
        out[f'{kind}{i}'] = ok
    for i, (ok, _a) in enumerate(d['gsm']):
        out[f'gsm{i}'] = ok
    for i, ok in enumerate(d['code12']):
        out[f'code{i}'] = ok
    return out


def confronto(a, b):
    A, B = items(a), items(b)
    for pref in ('mmlu', 'arc', 'gsm', 'code', ''):
        keys = [k for k in A if k in B and k.startswith(pref)]
        if not keys:
            continue
        bb = sum(1 for k in keys if A[k] and not B[k])
        cc = sum(1 for k in keys if B[k] and not A[k])
        print(f"{pref or 'TUTTO':6} n={len(keys):4}  A={sum(A[k] for k in keys):4}  B={sum(B[k] for k in keys):4}  solo A={bb:3}  solo B={cc:3}  p McNemar={binom_two_sided(bb, cc):.3f}")
    print('Regola: chiamare "migliore" solo con p<0.05 sul totale E coerenza su 2 run; altrimenti "indistinguibile".')


def mde():
    print('Differenza minima rilevabile (80% potenza, alfa 0.05, test non appaiato) in punti percentuali:')
    for n in (12, 30, 50, 100, 200, 500, 1000):
        for p in (0.7, 0.9):
            se = math.sqrt(2 * p * (1 - p) / n)
            print(f'  n={n:5} p={p:.1f}: {100 * 2.8 * se:5.1f}')
    print('Con confronto appaiato la soglia scende di solito del 30-50% (dipende dalla correlazione tra i due run).')


if __name__ == '__main__':
    if len(sys.argv) == 3:
        confronto(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] == '--mde':
        mde()
    else:
        tabella()
