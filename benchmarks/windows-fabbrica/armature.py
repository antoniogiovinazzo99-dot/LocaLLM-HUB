"""Laboratorio di armature: modi di far ragionare meglio LO STESSO modello, misurati sugli stessi test.
Ricette: sc5 (voto 5 campioni), pal (programma Python eseguito), pal_sc3, verify (rilettura), gated (accordo 3 campioni -> escalation),
mcq_sc5, mcq_gated, fixloop (scrivi codice + auto-test -> correggi con l'errore). Si esegue sul server gia avviato dalla Fabbrica."""
import collections, concurrent.futures as cf, json, os, pathlib, re, subprocess, sys, threading, time

ROOT = pathlib.Path(r'<HOME>\llm\fabbrica'); LOG = ROOT / 'log'
SUF = '\nReason step by step briefly, then end with a final line exactly: ANSWER: <number>'


def num(t):
    m = re.findall(r'ANSWER:\s*\$?\s*(-?[\d,]*\.?\d+)', t)
    return m[-1].replace(',', '') if m else None


def same(a, b):
    try:
        return abs(float(a) - float(b)) < 1e-6
    except Exception:
        return False


def vote(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, 0
    groups = []
    for v in vals:
        for g in groups:
            if same(g[0], v):
                g.append(v)
                break
        else:
            groups.append([v])
    groups.sort(key=len, reverse=True)
    return groups[0][0], len(groups[0])


def exec_py(code, timeout=20):
    p = LOG / f'_a{os.getpid()}_{threading.get_ident()}_{time.time_ns() % 10**9}.py'
    p.write_text(code, encoding='utf-8')
    try:
        r = subprocess.run([sys.executable, '-I', str(p)], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except Exception as e:
        return False, '', str(e)
    finally:
        try:
            p.unlink()
        except Exception:
            pass


def last_number(out):
    m = re.findall(r'-?\d[\d,]*\.?\d*', out or '')
    return m[-1].replace(',', '').rstrip('.') if m else None


def gold(r):
    return r['answer'].split('####')[-1].strip().replace(',', '')


# ---------------- GSM
def g_text(srv, r, temp=0.0, seed=1234):
    t, _, _ = srv.chat(r['question'] + SUF, max_tokens=900, temp=temp, seed=seed)
    return num(t), t


def g_pal(srv, r, temp=0.0, seed=1234):
    t, _, _ = srv.chat(r['question'] + '\nWrite a Python program that computes the answer and prints ONLY the final number. Output only code, no explanation.', max_tokens=500, temp=temp, seed=seed)
    import_code = re.search(r'```(?:python)?\n(.*?)```', t, re.S)
    code = import_code.group(1) if import_code else t
    ok, out, _ = exec_py(code)
    return last_number(out) if ok else None


def r_sc5(srv, r):
    return vote([g_text(srv, r, 0.7, 100 + i)[0] for i in range(5)])[0], 'sc'


def r_pal(srv, r):
    return g_pal(srv, r), 'pal'


def r_pal_sc3(srv, r):
    return vote([g_pal(srv, r, 0.7, 300 + i) for i in range(3)])[0], 'palsc'


def r_pal_fb(srv, r):
    v = g_pal(srv, r)
    return (v, 'pal') if v is not None else (g_text(srv, r)[0], 'fallback')


def r_verify(srv, r):
    a, t = g_text(srv, r)
    p = f"Problem: {r['question']}\n\nProposed solution:\n{t}\n\nCheck every step carefully for errors. If you find one, correct it. End with a final line exactly: ANSWER: <number>"
    t2, _, _ = srv.chat(p, max_tokens=900)
    return (num(t2) or a), 'verify'


def r_gated(srv, r):
    s = [g_text(srv, r)[0]] + [g_text(srv, r, 0.7, 200 + i)[0] for i in range(2)]
    v, n = vote(s)
    if v is not None and n == 3:
        return v, 'cheap'
    pal = [g_pal(srv, r, 0.7, 400 + i) for i in range(3)]
    return vote(s + pal)[0], 'escalated'


GSM = {'sc5': r_sc5, 'pal': r_pal, 'pal_fallback': r_pal_fb, 'pal_sc3': r_pal_sc3, 'verify': r_verify, 'gated': r_gated}


# ---------------- MCQ
def m_sample(srv, q, temp, seed):
    t, _, _ = srv.chat(q, max_tokens=400, temp=temp, seed=seed)
    m = re.search(r'\b([A-H])\b', t.strip()[:200])
    return m.group(1) if m else None


def mv(vals):
    vals = [v for v in vals if v]
    if not vals:
        return None, 0
    c = collections.Counter(vals).most_common(1)[0]
    return c[0], c[1]


def m_sc5(srv, q):
    return mv([m_sample(srv, q, 0.7, 100 + i) for i in range(5)])[0], 'sc'


def m_gated(srv, q):
    s = [m_sample(srv, q, 0.0, 1234)] + [m_sample(srv, q, 0.7, 200 + i) for i in range(2)]
    v, n = mv(s)
    if v and n == 3:
        return v, 'cheap'
    return mv(s + [m_sample(srv, q, 0.7, 500 + i) for i in range(4)])[0], 'escalated'


MCQ = {'mcq_sc5': m_sc5, 'mcq_gated': m_gated}


# ---------------- codice
def fixloop(srv, F, rounds=2):
    import suite2

    def one(t):
        desc, test, fn = t
        text, _, _ = srv.chat(suite2.PROMPT.format(desc) + f' Also add three assert-based self-tests at the bottom of the file that exercise {fn}; they run on import.', max_tokens=900)
        code = F.code_of(text)
        used = 0
        for rd in range(rounds + 1):
            ok, out, err = exec_py(code + '\nprint("PASS")\n')
            if ok and out.strip().endswith('PASS'):
                break
            if rd == rounds:
                break
            used += 1
            text, _, _ = srv.chat(f'The following Python code fails.\n\n{code}\n\nError:\n{err[-700:]}\n\nReturn the complete corrected code only (keep the self-tests, fix whichever is wrong).', max_tokens=900)
            code = F.code_of(text)
        return int(F.run_py(code + f'\nf = {fn}\n' + test + '\nprint("PASS")\n')), used
    with cf.ThreadPoolExecutor(srv.np) as ex:
        return list(ex.map(one, suite2.TASKS))


# ---------------- esecuzione
def run_all(srv, item, rec, F, budget_min=None):
    budget = (budget_min or item.get('arm_budget_min', 50)) * 60
    t0 = time.time()
    out, items = {}, {}
    gsm = json.load(open(F.DATA / 'tinyGSM8k.json', encoding='utf-8'))
    mcq = F.mcq_items()
    for name in item.get('recipes', list(GSM) + list(MCQ) + ['fixloop']):
        if time.time() - t0 > budget:
            out[name] = {'saltata': 'budget tempo'}
            continue
        s = time.time()
        try:
            if name in GSM:
                with cf.ThreadPoolExecutor(srv.np) as ex:
                    res = list(ex.map(lambda r: GSM[name](srv, r), gsm))
                ok = [int(p is not None and same(p, gold(r))) for (p, _), r in zip(res, gsm)]
                paths = collections.Counter(x[1] for x in res)
                items[name] = [p for p, _ in res]
                out[name] = {'acc': round(100 * sum(ok) / len(ok), 1), 'n': len(ok), 'percorsi': dict(paths)}
            elif name in MCQ:
                with cf.ThreadPoolExecutor(srv.np) as ex:
                    res = list(ex.map(lambda it: MCQ[name](srv, it[1]), mcq))
                ok = [int(p == it[2]) for (p, _), it in zip(res, mcq)]
                items[name] = [p for p, _ in res]
                out[name] = {'acc': round(100 * sum(ok) / len(ok), 1), 'acc_mmlu': round(sum(ok[:100]), 1), 'acc_arc': round(sum(ok[100:]), 1), 'n': len(ok), 'percorsi': dict(collections.Counter(x[1] for x in res))}
            elif name == 'fixloop':
                res = fixloop(srv, F)
                out[name] = {'acc': round(100 * sum(x[0] for x in res) / len(res), 1), 'n': len(res), 'round_usati': sum(x[1] for x in res)}
            out[name]['min'] = round((time.time() - s) / 60, 1)
        except Exception as e:
            out[name] = {'errore': str(e)[:120]}
    json.dump(items, open(LOG / f"{item['name']}-arm-items.json", 'w'))
    out['_base'] = {'gsm': rec.get('gsm'), 'mmlu': rec.get('mmlu'), 'arc': rec.get('arc'), 'code12': rec.get('code12')}
    return out
