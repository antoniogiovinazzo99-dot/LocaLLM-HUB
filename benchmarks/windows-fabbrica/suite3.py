"""Suite 3 (consulenza Opus, 8/11/2026): test piu duri e non contaminabili, stessa interfaccia srv.chat della Fabbrica.

- mmlu_pro(srv): MMLU-Pro 200 (10 opzioni, gia scaricato in notte-20261105/dati) -> discrimina meglio di tinyMMLU (che satura).
- math_gen(srv, n, seed): problemi aritmetici a piu passi GENERATI al volo (numeri nuovi a ogni seed) -> impossibile averli
  visti in addestramento; n illimitato, quindi l'intervallo di confidenza si stringe quanto si vuole.
- var_track(srv, n_tokens): tracciamento di variabili a catena in un testo lungo (stile RULER 'variable tracking'),
  piu duro dell'ago a 3 chiavi che tutti i modelli passano.

Integrazione: vedi fabbrica_v2.diff (voce di coda con "t1b": true). Nessun effetto sul runner attuale finche non si applica il diff.
"""
import json, pathlib, random, re

NOTTE = pathlib.Path(r'<HOME>\llm\notte-20261105')
L = 'ABCDEFGHIJ'


def mmlu_pro(srv, ex=None, think=False):
    rows = json.load(open(NOTTE / 'dati' / 'mmlu_pro_200.json', encoding='utf-8'))

    def one(r):
        q = (f"The following is a multiple choice question about {r['category']}.\n\n{r['question']}\n"
             + '\n'.join(f'{L[i]}. {o}' for i, o in enumerate(r['options']))
             + '\n\nThink briefly if needed, then end with a final line exactly: ANSWER: <letter>')
        t, tim, _ = srv.chat(q, max_tokens=3000 if think else 700, temp=0.0, think=think)
        m = re.findall(r'ANSWER:\s*\(?([A-J])\)?', t)
        return int(bool(m) and m[-1] == r['answer']), tim, r['category']
    if ex is None:
        return [one(r) for r in rows]
    return list(ex.map(one, rows))


def _problem(rng):
    """Problema a 3-5 passi con risposta intera esatta."""
    kind = rng.choice(['negozio', 'serbatoio', 'interessi', 'turni', 'magazzino'])
    if kind == 'negozio':
        a, b, c, d = rng.randint(12, 90), rng.randint(3, 19), rng.randint(2, 9), rng.randint(5, 40)
        q = (f'A shop buys {a} boxes, each with {b} items. It sells {c} full boxes on Monday and then {d} single items on Tuesday. '
             f'Each remaining item is then split into packs of 3 (leftovers are discarded). How many packs are made?')
        ans = ((a - c) * b - d) // 3
    elif kind == 'serbatoio':
        cap, fill, leak, h = rng.randint(400, 3000), rng.randint(30, 90), rng.randint(5, 25), rng.randint(3, 12)
        q = (f'A tank holds {cap} litres and starts empty. A pump adds {fill} litres per hour while a leak removes {leak} litres per hour. '
             f'After {h} hours the pump stops and the leak continues for 2 more hours. How many litres are in the tank? (It cannot go below 0 or above capacity.)')
        v = min(cap, (fill - leak) * h)
        ans = max(0, v - 2 * leak)
    elif kind == 'interessi':
        p, r, y = rng.randint(10, 90) * 100, rng.choice([2, 3, 4, 5, 6, 8, 10]), rng.randint(2, 4)
        q = (f'You deposit {p} euros at {r}% simple interest per year for {y} years, then withdraw a third of the total (rounded down to whole euros). '
             f'How many whole euros remain?')
        tot = p + p * r * y // 100
        ans = tot - tot // 3
    elif kind == 'turni':
        w, s, d, o = rng.randint(4, 15), rng.randint(2, 4), rng.randint(5, 7), rng.randint(1, 6)
        q = (f'A factory has {w} workers. Each worker does {s} shifts per day, {d} days per week. {o} workers are on holiday for the whole week. '
             f'Each shift produces 7 parts. How many parts are produced in the week?')
        ans = (w - o) * s * d * 7
    else:
        x, y, z, k = rng.randint(100, 900), rng.randint(10, 99), rng.randint(2, 6), rng.randint(2, 5)
        q = (f'A warehouse has {x} crates. Every day {y} crates arrive and {z} times as many leave as arrive, but never more than are present. '
             f'How many crates are there after {k} days?')
        v = x
        for _ in range(k):
            v = max(0, v + y - min(v + y, z * y))
        ans = v
    return q, ans


def math_gen(srv, n=60, seed=20261108, ex=None):
    rng = random.Random(seed)
    probs = [_problem(rng) for _ in range(n)]

    def one(p):
        q, ans = p
        t, tim, _ = srv.chat(q + '\nReason step by step briefly, then end with a final line exactly: ANSWER: <number>', max_tokens=900, temp=0.0)
        m = re.findall(r'ANSWER:\s*\$?\s*(-?[\d,]*\.?\d+)', t)
        try:
            ok = bool(m) and abs(float(m[-1].replace(',', '')) - ans) < 1e-6
        except ValueError:
            ok = False
        return int(ok), tim
    return list(ex.map(one, probs)) if ex else [one(p) for p in probs]


def var_track(srv, n_lines=2500, hops=6, seed=7):
    """Catena di assegnazioni sparse in rumore: VAR_k = VAR_{k-1}; serve seguire tutti i salti. ~12 token per riga."""
    rng = random.Random(seed)
    names = [f'X{rng.randint(1000, 9999)}' for _ in range(hops)]
    lines = [f'Riga {i:05d}: nota di servizio senza importanza numero {rng.randint(0, 99999)}.' for i in range(n_lines)]
    val = rng.randint(10000, 99999)
    pos = sorted(rng.sample(range(n_lines), hops))
    lines[pos[0]] += f'\nVAR {names[0]} = {val}'
    for i in range(1, hops):
        lines[pos[i]] += f'\nVAR {names[i]} = VAR {names[i - 1]}'
    q = '\n'.join(lines) + f'\n\nQual e il valore numerico di VAR {names[-1]}? Rispondi solo con il numero.'
    t, tim, _ = srv.chat(q, max_tokens=40, timeout=5400)
    return int(str(val) in t), tim
