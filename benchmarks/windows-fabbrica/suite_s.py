"""SUITE S ("seria"): benchmark piu duro e non saturo, pensato per misurare l'intelligenza *utile* e separare i modelli forti dai deboli.
Parti (campioni fissi e stratificati, seed costante):
  math   MATH-500, 100 problemi, 20 per livello 1-5, risposta confrontata dopo normalizzazione
  bbh    BIG-Bench Hard, 5 per ciascuno dei 27 compiti (135), match esatto
  mmlupro MMLU-Pro 200 (10 opzioni) dal pacchetto notte-20261105
  hep    HumanEval+ (test estesi), 82 problemi
  mbpp   MBPP+ (test estesi), 100 problemi
  lcb    LiveCodeBench lite (test6, piu recente), 30 problemi AtCoder/Codeforces medio-difficili, test pubblici+privati, stdin/stdout
  lavori 8 lavori reali con test nascosti e credito parziale (serio_lavori.py)
  lungo  tracciamento variabili in 1 testo da ~20K token (3 semi)
Ogni parte ritorna per-domanda un punteggio 0..1 (salvato per confronti appaiati e cascate). INDICE_USO pesa le parti come l'uso reale."""
import base64, collections, concurrent.futures as cf, io, json, os, pathlib, pickle, random, re, subprocess, sys, tempfile, time, zlib

ROOT = pathlib.Path(r'<HOME>\llm\fabbrica')
D = ROOT / 'dati' / 'serio'
NOTTE = pathlib.Path(r'<HOME>\llm\notte-20261105')
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'consulenza'))

PESI = {'math': 15, 'bbh': 10, 'mmlupro': 10, 'hep': 10, 'mbpp': 5, 'lcb': 15, 'lavori': 25, 'lungo': 10}  # somma 100: codice/agente pesa di piu


# ---------------------------------------------------------------- esecuzione sicura di codice
def run_code(src, stdin='', timeout=30):
    d = tempfile.mkdtemp(prefix='serio_')
    p = os.path.join(d, 't.py')
    open(p, 'w', encoding='utf-8').write(src)
    try:
        r = subprocess.run([sys.executable, '-I', p], input=stdin, capture_output=True, text=True, timeout=timeout, cwd=d)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -9, '', 'timeout'
    except Exception as e:
        return -1, '', str(e)
    finally:
        try:
            os.remove(p); os.rmdir(d)
        except Exception:
            pass


def code_of(t):
    ms = re.findall(r'```(?:python|py)?\s*\n(.*?)```', t, re.S)
    if ms:
        return max(ms, key=len)
    m = re.search(r'```(?:python|py)?\s*\n(.*)$', t, re.S)  # blocco non chiuso (troncato)
    return m.group(1) if m else t


# ---------------------------------------------------------------- normalizzazione risposte matematiche
def _strip_math(s):
    s = s.strip().strip('$').strip()
    s = re.sub(r'\\boxed\{(.*)\}', r'\1', s)
    s = re.sub(r'\\text\{([^}]*)\}', r'\1', s)
    for a, b in (('\\dfrac', '\\frac'), ('\\tfrac', '\\frac'), ('\\left', ''), ('\\right', ''), ('\\!', ''), ('\\,', ''), ('\\ ', ''), ('^\\circ', ''), ('^{\\circ}', ''), ('\\%', ''), ('%', ''), ('\\$', ''), ('$', '')):
        s = s.replace(a, b)
    s = re.sub(r'\s+', '', s).rstrip('.')
    s = re.sub(r'^(x|y|n|a|b|k|m)=', '', s) if re.fullmatch(r'[a-z]=.+', s) and ',' not in s else s
    s = re.sub(r'\\frac(\d)(\d)', r'\\frac{\1}{\2}', s)
    s = re.sub(r'(\d),(\d{3})(?!\d)', r'\1\2', s)
    return s


def _num(s):
    m = re.fullmatch(r'(-?)\\frac\{(-?\d+)\}\{(\d+)\}', s)
    if m:
        v = int(m.group(2)) / int(m.group(3))
        return -v if m.group(1) else v
    m = re.fullmatch(r'(-?\d+)/(\d+)', s)
    if m:
        return int(m.group(1)) / int(m.group(2))
    try:
        return float(s)
    except Exception:
        return None


def same_math(pred, gold):
    if pred is None:
        return False
    a, b = _strip_math(pred), _strip_math(gold)
    if a == b:
        return True
    x, y = _num(a), _num(b)
    return x is not None and y is not None and abs(x - y) < 1e-6 * max(1, abs(y))


def last_answer(t):
    m = re.findall(r'ANSWER:\s*(.+)', t)
    if m:
        return m[-1].strip()
    b = re.findall(r'\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}', t)
    return b[-1] if b else None


# ---------------------------------------------------------------- math
def load_math(n_per=20, seed=11):
    rows = [json.loads(l) for l in open(D / 'math500.jsonl', encoding='utf-8')]
    rng = random.Random(seed); out = []
    for lv in range(1, 6):
        c = [r for r in rows if r['level'] == lv]
        out += rng.sample(c, min(n_per, len(c)))
    return out


def math_one(srv, r, think=False):
    q = r['problem'] + '\n\nSolve it. Keep the reasoning short. End with a final line exactly: ANSWER: <final answer in simplest form, LaTeX allowed>'
    t, tim, _ = srv.chat(q, max_tokens=6000 if think else 1800, temp=0.0, think=think, timeout=3600)
    return float(same_math(last_answer(t), r['answer'])), tim


# ---------------------------------------------------------------- bbh
def load_bbh(n_per=5, seed=5):
    import pandas as pd
    rng = random.Random(seed); out = []
    for f in sorted((D / 'bbh').glob('*.parquet')):
        df = pd.read_parquet(f)
        idx = sorted(rng.sample(range(len(df)), min(n_per, len(df))))
        for i in idx:
            out.append({'task': f.stem, 'input': df.iloc[i]['input'], 'target': str(df.iloc[i]['target'])})
    return out


def _bbh_norm(s):
    s = s.strip().strip('.').strip()
    m = re.fullmatch(r'\(?([A-R])\)?', s)
    if m:
        return m.group(1)
    return re.sub(r'\s+', ' ', s).lower()


def bbh_one(srv, r, think=False):
    q = r['input'] + '\n\nThink step by step briefly. End with a final line exactly: ANSWER: <answer only>' + (' (for multiple choice give only the option letter)' if '(A)' in r['input'] else '')
    t, tim, _ = srv.chat(q, max_tokens=5000 if think else 1200, temp=0.0, think=think, timeout=3600)
    a = last_answer(t)
    return float(a is not None and _bbh_norm(a) == _bbh_norm(r['target'])), tim


# ---------------------------------------------------------------- HumanEval+ / MBPP+
def load_hep(n=82, seed=3):
    import pandas as pd
    df = pd.read_parquet(D / 'humanevalplus.parquet')
    idx = sorted(random.Random(seed).sample(range(len(df)), n))
    return [df.iloc[i].to_dict() for i in idx]


def hep_one(srv, r, think=False):
    q = 'Complete the following Python function. Return the complete function (with any imports) in one ```python block, nothing else.\n\n' + r['prompt']
    t, tim, _ = srv.chat(q, max_tokens=5000 if think else 1500, temp=0.0, think=think, timeout=3600)
    code = code_of(t)
    src = code + '\n\n' + r['test'] + f"\n\ncheck({r['entry_point']})\nprint('PASS')\n"
    rc, out, err = run_code(src, timeout=60)
    return float(rc == 0 and out.strip().endswith('PASS')), tim


def load_mbpp(n=100, seed=4):
    import pandas as pd
    df = pd.read_parquet(D / 'mbppplus.parquet')
    idx = sorted(random.Random(seed).sample(range(len(df)), n))
    return [df.iloc[i].to_dict() for i in idx]


def _mbpp_fn(r):
    m = re.findall(r'assertion\((\w+)\(', str(r['test']))
    return m[-1] if m else None


def mbpp_one(srv, r, think=False):
    ex = r['test_list'][0]
    q = f"{r['prompt']}\nThe function must be named as in this example test: {ex}\nReturn only the code in one ```python block."
    t, tim, _ = srv.chat(q, max_tokens=5000 if think else 1200, temp=0.0, think=think, timeout=3600)
    imports = '\n'.join(r['test_imports']) if len(r['test_imports']) else ''
    src = imports + '\n' + code_of(t) + '\n\n' + r['test'] + "\nprint('PASS')\n"
    rc, out, err = run_code(src, timeout=60)
    return float(rc == 0 and out.strip().endswith('PASS')), tim


# ---------------------------------------------------------------- LiveCodeBench
class _NoGlobals(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError('globali vietati')


def _decode_private(s):
    try:
        raw = zlib.decompress(base64.b64decode(s))
        return json.loads(_NoGlobals(io.BytesIO(raw)).load())
    except Exception:
        return []


def load_lcb(n=30, seed=6):
    cand = []
    with open(D / 'lcb_test6.jsonl', encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r['platform'] not in ('atcoder', 'codeforces') or r['difficulty'] not in ('medium', 'hard'):
                continue
            pub = json.loads(r['public_test_cases'])
            if not pub or any(t['testtype'] != 'stdin' for t in pub) or r['starter_code'].strip():
                continue
            cand.append({'id': r['question_id'], 'title': r['question_title'], 'q': r['question_content'], 'diff': r['difficulty'], 'pub': pub, 'priv': r['private_test_cases']})
    rng = random.Random(seed); rng.shuffle(cand)
    return cand[:n]


def lcb_one(srv, r, think=False):
    q = r['q'] + '\n\nWrite a complete Python 3 program that reads from standard input and prints to standard output. It must be efficient. Return only the code in one ```python block.'
    t, tim, _ = srv.chat(q, max_tokens=8000 if think else 3000, temp=0.0, think=think, timeout=3600)
    code = code_of(t)
    tests = list(r['pub']) + _decode_private(r['priv'])[:10]
    ok = 0
    for tc in tests:
        rc, out, err = run_code(code, stdin=tc['input'], timeout=8)
        if rc == 0 and out.split() == tc['output'].split():
            ok += 1
        else:
            break  # primo fallimento: problema non risolto
    return float(ok == len(tests) and len(tests) > 0), tim


# ---------------------------------------------------------------- lavori reali
def lavoro_one(srv, t, think=False):
    import serio_lavori as L
    x, tim, _ = srv.chat(t['prompt'], max_tokens=6000 if think else 2500, temp=0.0, think=think, timeout=3600)
    rc, out, err = run_code(L.grade_src(code_of(x), t), timeout=40)
    m = re.search(r'SCORE (\d+) (\d+)', out)
    return (int(m.group(1)) / int(m.group(2)) if m else 0.0), tim


# ---------------------------------------------------------------- contesto lungo
def lungo_one(srv, seed, think=False):
    import suite3
    ok, tim = suite3.var_track(srv, n_lines=1000, hops=6, seed=seed)
    return float(ok), tim


# ---------------------------------------------------------------- orchestrazione
LITE = {'math': 6, 'bbh': 2, 'hep': 30, 'lcb': 8}  # dimensioni nel modo rapido; lavori sempre interi; lungo = 1 seme; mbpp e mmlupro saltati
PESI_LITE = {'math': 15, 'bbh': 10, 'hep': 10, 'lcb': 15, 'lavori': 25, 'lungo': 10}


def parti(lite=False):
    import serio_lavori as L
    if lite:
        return {
            'math': (lambda: load_math(n_per=LITE['math']), math_one), 'bbh': (lambda: load_bbh(n_per=LITE['bbh']), bbh_one),
            'hep': (lambda: load_hep(n=LITE['hep']), hep_one), 'lcb': (lambda: load_lcb(n=LITE['lcb']), lcb_one),
            'lavori': (lambda: L.TASKS, lavoro_one), 'lungo': (lambda: [101], lungo_one),
        }
    return {
        'math': (load_math, math_one), 'bbh': (load_bbh, bbh_one), 'hep': (load_hep, hep_one), 'mbpp': (load_mbpp, mbpp_one),
        'lcb': (load_lcb, lcb_one), 'lavori': (lambda: L.TASKS, lavoro_one), 'lungo': (lambda: [101, 202, 303], lungo_one),
    }


SHARE = {'math': 0.2, 'bbh': 0.15, 'hep': 0.15, 'mbpp': 0.1, 'lcb': 0.15, 'lavori': 0.2, 'lungo': 0.15}


def run(srv, think=False, only=None, workers=None, log=print, lite=None, budget_min=10):
    if lite is None:
        lite = not os.path.exists(ROOT / 'serio_full.flag')  # di default modo RAPIDO; crea serio_full.flag per il modo completo
    P = parti(lite); res = {'modo': 'rapido' if lite else 'completo'}; tims = []
    w = workers or srv.np
    B = budget_min * 60 if lite else None
    for name, (load, one) in P.items():
        if only and name not in only:
            continue
        t0 = time.time(); items = load()
        random.Random(21).shuffle(items)  # campione casuale se scatta il budget
        dl = (t0 + B * SHARE.get(name, 0.15)) if B else None

        def wrap(it, one=one, dl=dl):
            if dl and time.time() > dl:
                return None
            return _safe(one, srv, it, think)
        with cf.ThreadPoolExecutor(1 if name == 'lungo' else w) as ex:
            out = [o for o in ex.map(wrap, items) if o is not None]
        if not out:
            continue
        sc = [o[0] for o in out]; tims += [o[1] for o in out if o[1]]
        res[name] = {'acc': round(100 * sum(sc) / len(sc), 1), 'n': len(sc), 'n_tot': len(items), 'items': sc, 'min': round((time.time() - t0) / 60, 1)}
        log(name, res[name]['acc'], '%d/%d' % (len(sc), len(items)), res[name]['min'])
    if (not lite) and (not only or 'mmlupro' in only):
        import suite3
        t0 = time.time()
        with cf.ThreadPoolExecutor(w) as ex:
            mp = suite3.mmlu_pro(srv, ex, think=think)
        sc = [float(x[0]) for x in mp]; tims += [x[1] for x in mp]
        res['mmlupro'] = {'acc': round(100 * sum(sc) / len(sc), 1), 'n': len(sc), 'items': sc, 'min': round((time.time() - t0) / 60, 1)}
    res['indice_uso'] = indice(res, PESI_LITE if lite else PESI)
    return res, tims


ERRORI = []


def _safe(one, srv, it, think):
    try:
        return one(srv, it, think)
    except Exception as e:
        ERRORI.append(str(e)[:120])  # un errore non deve sembrare una risposta sbagliata: viene contato a parte
        return 0.0, None


def indice(res, pesi=None):
    num = den = 0
    for k, w in (pesi or PESI).items():
        if k in res and isinstance(res[k], dict):
            num += w * res[k]['acc']; den += w
    return round(num / den, 1) if den else None
