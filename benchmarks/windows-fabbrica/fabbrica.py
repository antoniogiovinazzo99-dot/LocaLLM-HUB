"""Fabbrica LLM v1 (8/11/2026) - scarica, testa, registra, cancella. Un modello alla volta.
Livelli: T0 velocita, T1 rapido (tinyMMLU/ARC/GSM8k 100 ciascuno + codice 12 + sonda parole), T2 profondo (HumanEval 82 + ago 64K, solo se passa il gate).
Uso: python -u fabbrica.py   (legge coda.json, scrive risultati.jsonl e CLASSIFICA.md; quando la coda e vuota chiama lo scout)."""
import random, concurrent.futures as cf, datetime, gzip, hashlib, json, os, pathlib, re, shutil, statistics, subprocess, sys, threading, time, urllib.request

ROOT = pathlib.Path(r'<HOME>\llm\fabbrica'); DATA = ROOT / 'dati'; MOD = ROOT / 'modelli'; LOG = ROOT / 'log'
RES = ROOT / 'risultati.jsonl'; QUEUE = ROOT / 'coda.json'; BOARD = ROOT / 'CLASSIFICA.md'; LOCK = ROOT / 'runner.lock'
LLAMA = r'<HOME>\llm\bin-b10955\llama-server.exe'
NOTTE = pathlib.Path(r'<HOME>\llm\notte-20261105')
PORT = 8095
PREF = ['q4_k_m', 'q4_k_s', 'iq4_xs', 'q4_0', 'q3_k_m', 'iq3_m', 'iq3_xxs', 'q3_k_s', 'iq2_m', 'q2_k']
for d in (MOD, LOG): d.mkdir(exist_ok=True)
sys.path.insert(0, str(NOTTE))
sys.path.insert(0, str(ROOT / 'consulenza'))  # suite3.py
try:
    ENGINE_VER = subprocess.run([LLAMA, '--version'], capture_output=True, text=True, timeout=30).stderr.strip().splitlines()[-1][:120]
except Exception:
    ENGINE_VER = 'b10955?'


def ev(kind, **k):
    print(json.dumps({'event': kind, 't': time.strftime('%H:%M:%S'), **k}, ensure_ascii=False), flush=True)


def hf(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'fabbrica'}), timeout=60))


def free_gb():
    return shutil.disk_usage('C:/').free / 2**30


# ---------------------------------------------------------------- download
def pick_files(repo, pref, cap):
    tree = hf(f'https://huggingface.co/api/models/{repo}/tree/main?recursive=true')
    g = {}
    for f in tree:
        p = f['path'].lower()
        if f['type'] == 'file' and p.endswith('.gguf') and 'mmproj' not in p and 'draft' not in p:
            g.setdefault(re.sub(r'-\d{5}-of-\d{5}', '', f['path']), []).append(f)
    c = [(k, sum(x['size'] for x in v), sorted(v, key=lambda x: x['path'])) for k, v in g.items()]
    c = [x for x in c if x[1] <= cap * 1e9]
    if not c:
        return None

    def rank(x):
        n = x[0].lower()
        for i, t in enumerate(pref):
            if t in n:
                return (i, -x[1])
        return (99, -x[1])
    c.sort(key=rank)
    return c[0]


def fast_download(url, out, size, streams=16, piece=64 << 20):
    """Download a pezzi in parallelo (Range) con ripresa tramite file .parts: ~100 MB/s contro ~40 di un flusso solo."""
    out.parent.mkdir(parents=True, exist_ok=True)
    st = out.with_name(out.name + '.parts')
    full = out.exists() and out.stat().st_size == size
    done = set(json.loads(st.read_text())) if (full and st.exists()) else set()
    if not full:
        with open(out, 'wb') as f:
            f.truncate(size)
    lock = threading.Lock()

    def get(p):
        i, a, b = p
        for _ in range(5):
            try:
                req = urllib.request.Request(url, headers={'Range': f'bytes={a}-{b}', 'User-Agent': 'fabbrica'})
                with urllib.request.urlopen(req, timeout=120) as r, open(out, 'r+b') as f:
                    f.seek(a)
                    pos = a
                    while True:
                        c = r.read(1 << 20)
                        if not c:
                            break
                        f.write(c)
                        pos += len(c)
                if pos == b + 1:
                    with lock:
                        done.add(i)
                        st.write_text(json.dumps(sorted(done)))
                    return True
            except Exception:
                time.sleep(3)
        return False
    pieces = [(i, i * piece, min(size, (i + 1) * piece) - 1) for i in range((size + piece - 1) // piece) if i not in done]
    with cf.ThreadPoolExecutor(streams) as ex:
        ok = all(ex.map(get, pieces))
    if ok:
        try:
            st.unlink()
        except Exception:
            pass
    return ok and out.stat().st_size == size


def download(repo, files, dest):
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        out = dest / pathlib.Path(f['path']).name
        url = f"https://huggingface.co/{repo}/resolve/main/{f['path']}"
        ok = False
        for _ in range(3):
            if fast_download(url, out, f['size']):
                ok = True
                break
        if not ok:
            return False
        oid = (f.get('lfs') or {}).get('oid')
        if oid:
            h = hashlib.sha256()
            with open(out, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 24), b''):
                    h.update(chunk)
            if h.hexdigest() != oid:
                return False
    return True


# ---------------------------------------------------------------- server
def gpu_info():
    try:
        o = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,clocks.gr,temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15).stdout.strip().split(',')
        return {'gpu': o[0].strip(), 'vram_other_MiB': int(o[1]), 'clk': int(o[2]), 'temp': int(o[3])}
    except Exception:
        return {}


PROD_PORTS = (8090, 8091)  # launcher di produzione Flash-Next (proxy + motore): la Fabbrica non deve mai ucciderli


def prod_busy():
    """True se il launcher di produzione e attivo (porta 8090/8091 in ascolto)."""
    import socket
    for p in PROD_PORTS:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            if s.connect_ex(('127.0.0.1', p)) == 0:
                return True
        finally:
            s.close()
    return False


def wait_gpu_free(max_wait_s=6 * 3600):
    """Aspetta che produzione sia spenta e che la VRAM occupata da altri sia < 1,5 GB (misure di velocita pulite)."""
    t0 = time.time()
    while time.time() - t0 < max_wait_s:
        g = gpu_info()
        if not prod_busy() and g.get('vram_other_MiB', 0) < 1500:
            return True
        ev('attesa_gpu', prod=prod_busy(), vram_other=g.get('vram_other_MiB'))
        time.sleep(300)
    return False


def kill_servers():
    # solo i server della Fabbrica (porta 8095): mai taskkill /IM globale, che spegnerebbe anche la produzione
    subprocess.run(['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'llama-server.exe' -and $_.CommandLine -match '--port 8095') -or ($_.Name -eq 'strata.exe' -and $_.CommandLine -match 'fabbrica|max-context 32768') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
    subprocess.run(['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'server\\.py' -and $_.CommandLine -match '--port 8095' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"], capture_output=True)
    time.sleep(2)


class Server:
    def __init__(self, item, model_path=None, ctx=32768, np_=4):
        self.item, self.path, self.ctx, self.np = item, model_path, ctx, np_
        self.proc = None
        self.name = 'm'

    def start(self, log):
        kill_servers()
        lg = open(log, 'w', encoding='utf-8', errors='replace')
        if self.item.get('backend') == 'strata':
            cfg = json.loads(pathlib.Path(self.item['config']).read_text(encoding='utf-8'))
            cfg['port'] = PORT
            a = cfg['args']
            for k, v in (('--max-context', '32768'), ('--kv-resident', '32768')):
                if k in a:
                    a[a.index(k) + 1] = v
            if '--kv-resident' in a:  # il pin della KV fallisce con 16 GB e altre app aperte ("cannot pin 0.26 GiB")
                i = a.index('--kv-resident')
                del a[i:i + 2]
            cfg.setdefault('env', {}).update(self.item.get('env', {}))
            cfg['log'] = str(LOG / f"{self.item['name']}-engine.log")
            cp = LOG / f"{self.item['name']}-strata.json"
            cp.write_text(json.dumps(cfg, indent=1), encoding='utf-8')
            ctl = pathlib.Path(cfg['cwd'])
            self.name = cfg['model_name']
            self.np = 1
            cmd = [str(ctl / 'python' / 'python.exe'), '-u', str(ctl / 'serve' / 'server.py'), '--engine', 'strata', '--config', str(cp), '--port', str(PORT), '--offline']
            self.proc = subprocess.Popen(cmd, cwd=ctl, stdout=lg, stderr=subprocess.STDOUT)
        else:
            cmd = [self.item.get('llama', LLAMA), '-m', str(self.path), '--host', '127.0.0.1', '--port', str(PORT), '-c', str(self.ctx), '-np', str(self.np), '-fa', 'on', '--cache-ram', '0', '--jinja'] + [str(x) for x in self.item.get('args', [])]
            if self.ctx > 40000:
                cmd += ['-ctk', 'q8_0', '-ctv', 'q8_0']
            self.proc = subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT)
        t0 = time.time()
        while time.time() - t0 < 1500:
            if self.proc.poll() is not None:
                raise RuntimeError('server uscito in avvio')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=3) as r:
                    d = json.loads(r.read() or b'{}')
                    if self.item.get('backend') != 'strata' or d.get('loaded'):
                        return round(time.time() - t0, 1)
            except Exception:
                pass
            time.sleep(3)
        raise RuntimeError('timeout avvio')

    def stop(self):
        try:
            if self.item.get('backend') == 'strata':
                urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{PORT}/unload', data=b'{}', headers={'Content-Type': 'application/json'}), timeout=60)
        except Exception:
            pass
        kill_servers()

    def chat(self, content, max_tokens=300, temp=0.0, think=False, timeout=1800, seed=1234):
        body = {'model': self.name, 'messages': [{'role': 'user', 'content': content}], 'max_tokens': max_tokens, 'temperature': temp, 'stream': False,
                'seed': seed, 'chat_template_kwargs': {'enable_thinking': think, 'reasoning_effort': 'low'}}
        if temp > 0:
            body.update(top_p=0.95, presence_penalty=1.1)
        req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        m = d['choices'][0]['message']
        text = re.sub(r'<think>.*?</think>', '', m.get('content') or '', flags=re.S).strip()
        return text, d.get('timings') or {}, bool(m.get('reasoning_content'))


# ---------------------------------------------------------------- test
L = 'ABCDEFGH'


def mcq_items():
    out = []
    for r in json.load(open(DATA / 'tinyMMLU.json', encoding='utf-8')):
        q = f"The following is a multiple choice question about {r['subject'].replace('_', ' ')}.\n\n{r['question']}\n" + '\n'.join(f'{L[i]}. {c}' for i, c in enumerate(r['choices'])) + '\n\nAnswer with only the letter of the correct option.'
        out.append(('mmlu', q, L[int(r['answer'])]))
    for r in json.load(open(DATA / 'tinyAI2_arc.json', encoding='utf-8')):
        ch = r['choices']
        labels = list(ch['label'])
        q = f"{r['question']}\n" + '\n'.join(f'{L[i]}. {t}' for i, t in enumerate(ch['text'])) + '\n\nAnswer with only the letter of the correct option.'
        out.append(('arc', q, L[labels.index(str(r['answerKey']))]))
    return out


def run_mcq(srv, it):
    kind, q, gold = it
    text, tim, _ = srv.chat(q, max_tokens=400)
    m = re.search(r'\b([A-H])\b', text.strip()[:200])
    return kind, int(bool(m) and m.group(1) == gold), tim, (m.group(1) if m else None)


def run_gsm(srv, r):
    text, tim, _ = srv.chat(r['question'] + '\nReason step by step briefly, then end with a final line exactly: ANSWER: <number>', max_tokens=900, temp=0.6)
    m = re.findall(r'ANSWER:\s*\$?\s*(-?[\d,]*\.?\d+)', text)
    gold = r['answer'].split('####')[-1].strip().replace(',', '')
    try:
        ok = bool(m) and abs(float(m[-1].replace(',', '')) - float(gold)) < 1e-6
    except ValueError:
        ok = False
    return int(ok), tim, (m[-1] if m else None)


def code_of(text):
    m = re.search(r'```(?:python)?\n(.*?)```', text, re.S)
    return (m.group(1) if m else re.sub(r'^```(?:python)?\s*|\s*```$', '', text.strip()))


def run_py(src):
    p = LOG / '_t.py'
    p = LOG / f'_t{os.getpid()}_{int(time.time()*1000)%100000}.py'
    p.write_text(src, encoding='utf-8')
    try:
        r = subprocess.run([sys.executable, '-I', str(p)], capture_output=True, text=True, timeout=25)
        return r.stdout.strip().endswith('PASS')
    except Exception:
        return False
    finally:
        try:
            p.unlink()
        except Exception:
            pass


def run_code12(srv):
    import suite2
    def one(t):
        desc, test, fn = t
        text, tim, _ = srv.chat(suite2.PROMPT.format(desc), max_tokens=700)
        return int(run_py(code_of(text) + f'\nf = {fn}\n' + test + '\nprint("PASS")\n')), tim
    with cf.ThreadPoolExecutor(srv.np) as ex:
        r = list(ex.map(one, suite2.TASKS))
    return r


def run_he(srv):
    he = [json.loads(l) for l in gzip.open(NOTTE / 'dati' / 'HumanEval.jsonl.gz', 'rt')][::2]
    def one(t):
        text, tim, _ = srv.chat('Complete the following Python function. Reply with the complete function (including imports and signature) as plain Python code only.\n\n' + t['prompt'], max_tokens=700)
        head = t['prompt'].split('def ' + t['entry_point'])[0]
        return int(run_py(head + '\n' + code_of(text) + '\n' + t['test'] + f"\ncheck({t['entry_point']})\nprint('PASS')\n")), tim
    with cf.ThreadPoolExecutor(srv.np) as ex:
        return list(ex.map(one, he))


def probe_words(srv):
    text, tim, _ = srv.chat('Scrivi un tutorial in italiano di circa 800 parole su come costruire un backtest onesto di una strategia di trading: dati, costi, look-ahead, survivorship, walk-forward, metriche.', max_tokens=1300, temp=0.6)
    try:
        from wordfreq import zipf_frequency as z
    except ImportError:
        return None, tim, text
    w = [x for x in re.findall(r"[A-Za-zÀ-ÿ]+", text) if len(x) >= 4]
    bad = [x for x in w if z(x.lower(), 'it') == 0 and z(x.lower(), 'en') == 0]
    return round(100 * len(bad) / max(1, len(w)), 2), tim, text


def needle(srv, rows=2900):
    r = [f'Voce {i:05d}: etichetta archivio, contenuto ordinario di prova.' for i in range(rows)]
    for fr, t in [(0.03, 'CHIAVE_INIZIO = AMBRA-4917'), (.49, 'CHIAVE_CENTRO = CORALLO-8263'), (.97, 'CHIAVE_FINE = INDACO-3059')]:
        r[int(rows * fr)] += '\n' + t
    text, tim, _ = srv.chat('\n'.join(r) + '\n\nRiporta esattamente i valori di CHIAVE_INIZIO, CHIAVE_CENTRO e CHIAVE_FINE, separati da virgola, senza altro testo.', max_tokens=60, timeout=5400)
    return int(all(k in text for k in ('AMBRA-4917', 'CORALLO-8263', 'INDACO-3059'))), tim


def med(xs):
    xs = [x for x in xs if x]
    return round(statistics.median(xs), 1) if xs else None


def pct(xs):
    return round(100 * sum(xs) / len(xs), 1) if xs else None


def bmap(ex, fn, items, deadline):
    """map con scadenza: gli elementi non iniziati entro la scadenza restano None (campione casuale, nessun bias)."""
    def w(it):
        if deadline and time.time() > deadline:
            return None
        return fn(it)
    return list(ex.map(w, items))


def speed_of(tims):
    return (med([t.get('predicted_per_second') for t in tims if (t.get('predicted_n') or 0) >= 40]), med([t.get('prompt_per_second') for t in tims if (t.get('prompt_n') or 0) >= 100]))


def evaluate(item, srv, rec, tier2_gate):
    t0 = time.time()
    tims = []
    s1 = []
    for _ in range(3):
        _, tm, _r = srv.chat('Write a Python class implementing an LRU cache with get and put, with docstrings and three usage examples.', max_tokens=350)
        s1.append(tm)
    rec['decode_tps_1'] = speed_of(s1)[0]
    if item.get('speed_only'):  # velocita per tipo di prompt + accettazione del drafter: ~2-3 minuti, nessun test di qualita
        tipi = {
            'codice': 'Write a Python module with a class Graph (add_edge, bfs, dijkstra) and full docstrings.',
            'storia': 'Write a vivid 300 word story about a lighthouse keeper who finds a message in a bottle.',
            'ragionamento': 'A train leaves at 9:10 at 80 km/h, another at 9:40 at 100 km/h on the same track. When does the second catch up? Show every step.',
            'json': 'Return a JSON array of 8 objects with keys id, name, email, tags (array of 3 strings). JSON only.',
        }
        out = {}
        for k, q in tipi.items():
            tp, dn, da = [], 0, 0
            for sd in (1, 2):
                _, tm, _r = srv.chat(q, max_tokens=300, seed=sd)
                if (tm.get('predicted_n') or 0) >= 40:
                    tp.append(tm.get('predicted_per_second'))
                dn += tm.get('draft_n') or 0; da += tm.get('draft_n_accepted') or 0
            out[k] = {'tps': round(statistics.median(tp), 1) if tp else None, 'accettazione': round(100 * da / dn, 1) if dn else None}
        rec['tps_tipi'] = out
        v = [x['tps'] for x in out.values() if x['tps']]
        rec['tps_media'] = round(sum(v) / len(v), 1) if v else None
        rec['q_medio'] = None; rec['tier'] = 0; rec['note'] = 'solo velocita'
        return
    mc = list(mcq_items()); random.Random(7).shuffle(mc)
    gs = list(json.load(open(DATA / 'tinyGSM8k.json', encoding='utf-8'))); random.Random(8).shuffle(gs)
    B = item.get('budget_min', 4) * 60  # budget di tempo per mcq+gsm: se il modello e lento si valuta un campione casuale
    st = time.time()
    with cf.ThreadPoolExecutor(srv.np) as ex:
        a = [x for x in bmap(ex, lambda i: run_mcq(srv, i), mc, st + 0.45 * B) if x]
        g = [x for x in bmap(ex, lambda r: run_gsm(srv, r), gs, st + B) if x]
    rec['n_t1'] = {'mcq': len(a), 'gsm': len(g)}
    tims += [x[2] for x in a] + [x[1] for x in g]
    rec['mmlu'] = pct([x[1] for x in a if x[0] == 'mmlu'])
    rec['arc'] = pct([x[1] for x in a if x[0] == 'arc'])
    rec['gsm'] = pct([x[0] for x in g])
    c = run_code12(srv)
    rec['code12'] = pct([x[0] for x in c])
    tims += [x[1] for x in c]
    json.dump({'mcq': [(x[0], x[1], x[3]) for x in a], 'gsm': [(x[0], x[2]) for x in g], 'code12': [x[0] for x in c]}, open(LOG / f"{item['name']}-items.json", 'w'))
    inv, tp, txt = probe_words(srv)
    tims.append(tp)
    rec['parole_inventate_pct'] = inv
    (LOG / f"{item['name']}-testo.txt").write_text(txt, encoding='utf-8')
    rec['decode_tps'], rec['prompt_tps'] = speed_of(tims)
    qs = [rec[k] for k in ('mmlu', 'arc', 'gsm', 'code12') if rec.get(k) is not None]
    rec['q_medio'] = round(sum(qs) / len(qs), 1) if qs else None
    # Q pesato per numero di domande (codice12 = 12 item non deve pesare quanto 100 domande)
    w = {'mmlu': 100, 'arc': 100, 'gsm': 100, 'code12': 12}
    rec['q_pesato'] = round(sum(rec[k] * n for k, n in w.items() if rec.get(k) is not None) / sum(n for k, n in w.items() if rec.get(k) is not None), 1) if qs else None
    if item.get('t1b'):
        import suite3
        with cf.ThreadPoolExecutor(srv.np) as ex:
            mp = suite3.mmlu_pro(srv, ex, think=bool(item.get('think')))
            mg = suite3.math_gen(srv, 60, ex=ex)
        rec['mmlu_pro'] = pct([x[0] for x in mp])
        rec['math_gen'] = pct([x[0] for x in mg])
        tims += [x[1] for x in mp] + [x[1] for x in mg]
        json.dump({'mmlu_pro': [x[0] for x in mp], 'math_gen': [x[0] for x in mg]}, open(LOG / f"{item['name']}-items-t1b.json", 'w'))
    if item.get('serio'):  # SUITE S: benchmark serio (math, bbh, mmlu-pro, he+, mbpp+, lcb, lavori reali, contesto lungo)
        import suite_s
        sres, stims = suite_s.run(srv, think=bool(item.get('think')), only=item.get('serio_parts'), budget_min=item.get('serio_budget_min', 8), log=lambda *a_: ev('serio', parte=a_[0], acc=a_[1], n=a_[2], min=a_[3]))
        rec['serio'] = {k: {kk: vv for kk, vv in v.items() if kk != 'items'} for k, v in sres.items() if isinstance(v, dict)}
        rec['indice_uso'] = sres.get('indice_uso')
        json.dump({k: v['items'] for k, v in sres.items() if isinstance(v, dict)}, open(LOG / f"{item['name']}-items-serio.json", 'w'))
        tims += stims
    if item.get('serio') or item.get('agente'):  # AGENTE-MINI: 6 compiti agentici con strumenti e test nascosti (~10 min)
        import agente_mini
        ag = agente_mini.run_all(PORT, think=bool(item.get('think')), model=srv.name, budget_min=item.get('agente_budget_min', 5), log=lambda *a_: ev('agente', compito=a_[0], ok=a_[1], turni=a_[2], sec=a_[3]))
        rec['agente'] = {k: v for k, v in ag.items() if k != 'dettaglio'}
        rec['agente_dettaglio'] = ag['dettaglio']
    rec['t1_min'] = round((time.time() - t0) / 60, 1)
    rec['tier'] = 1
    if tier2_gate(rec) and not item.get('serio'):  # con la Suite S niente HumanEval T2 (c'e HumanEval+ nella suite)
        t1 = time.time()
        h = run_he(srv)
        rec['humaneval'] = pct([x[0] for x in h])
        rec['t2_he_min'] = round((time.time() - t1) / 60, 1)
        rec['tier'] = 2


# ---------------------------------------------------------------- risultati
def load_results():
    out = []
    if RES.exists():
        for l in RES.read_text(encoding='utf-8').splitlines():
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def gate(rec):
    ref = [r for r in load_results() if r.get('ref') and r.get('q_medio') is not None]
    if not ref:
        return (rec.get('q_medio') or 0) >= 55
    # velocita a flusso singolo per entrambi: decode_tps e per-richiesta con 4 slot su llama.cpp ma con 1 slot su Strata (non confrontabili)
    rq, rs = ref[-1]['q_medio'], ref[-1].get('decode_tps_1') or ref[-1].get('decode_tps') or 1
    q, s = rec.get('q_medio') or 0, rec.get('decode_tps_1') or 0
    return q >= rq - 8 or (s >= 1.5 * rs and q >= rq - 15)


def board():
    rs = [r for r in load_results() if r.get('q_medio') is not None]
    last = {}
    for r in rs:
        last[r['name']] = r
    rows = sorted(last.values(), key=lambda r: -(r.get('q_medio') or 0))
    L_ = ['# Classifica Fabbrica LLM', f'Aggiornata {time.strftime("%d/%m %H:%M")} - RTX 3060 12 GB / 16 GB RAM. Percentuali su 100 domande tiny (rumore +-3); velocita su prompt da 300+ token.', '',
          '| modello | quant/GB | t/s 1 flusso | t/s x4 | prompt t/s | MMLU | ARC | GSM | codice12 | HumanEval | Q medio | parole inv.% | ago64K | note |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|']
    for r in rows:
        L_.append(f"| {r['name']}{' (rif.)' if r.get('ref') else ''} | {r.get('file', '-')[:28]} {r.get('size_gb', '')} | {r.get('decode_tps_1')} | {r.get('decode_tps')} | {r.get('prompt_tps')} | {r.get('mmlu')} | {r.get('arc')} | {r.get('gsm')} | {r.get('code12')} | {r.get('humaneval', '-')} | **{r.get('q_medio')}** | {r.get('parole_inventate_pct')} | {r.get('ago64k', '-')} | {r.get('note', '')} |")
    fails = [r for r in load_results() if r.get('q_medio') is None and not r.get('tps_tipi')]
    if fails:
        L_ += ['', '## Falliti / saltati'] + [f"- {r['name']}: {r.get('errore', '?')}" for r in fails[-20:]]
    BOARD.write_text('\n'.join(L_), encoding='utf-8')
    sp = {}
    for r in load_results():
        if r.get('tps_tipi'):
            sp[r['name']] = r
    if sp:
        V = ['codice', 'storia', 'ragionamento', 'json']
        S2 = ['# Classifica VELOCITA (solo decode, 300 token, 2 semi per tipo)', 'Aggiornata ' + time.strftime('%d/%m %H:%M') + '. Accettazione = % token proposti dal drafter e accettati.', '',
              '| configurazione | t/s medio | ' + ' | '.join(V) + ' | accettazione (codice) |', '|---|---:|' + '---:|' * len(V) + '---:|']
        for r in sorted(sp.values(), key=lambda r: -(r.get('tps_media') or 0)):
            t_ = r['tps_tipi']
            S2.append('| ' + r['name'] + ' | **' + str(r.get('tps_media')) + '** | ' + ' | '.join(str(t_.get(k_, {}).get('tps')) for k_ in V) + ' | ' + str(t_.get('codice', {}).get('accettazione')) + ' |')
        (ROOT / 'CLASSIFICA-VELOCITA.md').write_text('\n'.join(S2), encoding='utf-8')
    rs2 = {}
    for r in load_results():
        if r.get('indice_uso') is not None:
            rs2[r['name']] = r
    if rs2:
        P = ['math', 'bbh', 'mmlupro', 'hep', 'mbpp', 'lcb', 'lavori', 'lungo']
        S_ = ['# Classifica SERIA (Suite S)', 'Aggiornata ' + time.strftime('%d/%m %H:%M') + '. Indice uso = media pesata (lavori reali 25, math 15, lcb 15, bbh/mmlupro/hep/lungo 10, mbpp 5). Parti non eseguite = -.', '',
              '| modello | indice uso | t/s 1 flusso | ' + ' | '.join(P) + ' |', '|---|---:|---:|' + '---:|' * len(P)]
        for r in sorted(rs2.values(), key=lambda r: -(r.get('indice_uso') or 0)):
            sv = r.get('serio', {})
            S_.append('| ' + r['name'] + ' | **' + str(r['indice_uso']) + '** | ' + str(r.get('decode_tps_1')) + ' | ' + ' | '.join(str(sv.get(p_, {}).get('acc', '-')) for p_ in P) + ' |')
        (ROOT / 'CLASSIFICA-SERIA.md').write_text('\n'.join(S_), encoding='utf-8')


# ---------------------------------------------------------------- un modello
def run_item(item):
    name = item['name']
    wait_gpu_free()
    rec = {'name': name, 'repo': item.get('repo'), 'ref': bool(item.get('ref')), 'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'hw': gpu_info(),
           'item': {k: v for k, v in item.items() if k not in ('name', 'repo')}, 'engine': ENGINE_VER}
    d = MOD / name
    srv = None
    try:
        path = None
        if item.get('repo'):
            try:
                rec['revision'] = hf(f"https://huggingface.co/api/models/{item['repo']}").get('sha')  # commit HF esatto: riproducibilita
            except Exception:
                pass
        if item.get('backend') != 'strata':
            sel = pick_files(item['repo'], [q.lower() for q in item.get('quant', PREF)], item.get('cap', 22))
            if not sel:
                raise RuntimeError('nessun file GGUF entro il limite di dimensione')
            key, size, files = sel
            rec.update(file=pathlib.Path(key).name, size_gb=round(size / 1e9, 1))
            if item.get('local'):
                path = item['local']
            else:
                if free_gb() < size / 2**30 + 8:
                    raise RuntimeError(f'spazio insufficiente ({free_gb():.0f} GB liberi)')
                ev('download', name=name, gb=rec['size_gb'])
                if not download(item['repo'], files, d):
                    raise RuntimeError('download o SHA256 falliti')
                path = d / pathlib.Path(files[0]['path']).name
        srv = Server(item, path)
        rec['load_s'] = srv.start(LOG / f'{name}-server.log')
        ev('avviato', name=name, load_s=rec['load_s'])
        rec['hw_dopo_carico'] = gpu_info()
        evaluate(item, srv, rec, gate)
        if rec['hw'].get('vram_other_MiB', 0) > 1500:
            rec['note'] = (rec.get('note', '') + ' velocita sporca: VRAM occupata da altre app').strip()
        if item.get('arm'):
            import armature
            rec['arm'] = armature.run_all(srv, item, rec, sys.modules[__name__])
        if item.get('needle') or (rec['tier'] == 2 and item.get('needle') is not False):  # "needle": false lo salta (es. 27B denso: KV 64K non entra)
            srv.stop()
            if item.get('backend') != 'strata':
                srv = Server(item, path, ctx=72000, np_=1)
                srv.start(LOG / f'{name}-server-ago.log')
                rec['ago64k'], tim = needle(srv)
                rec['ago64k_prompt_tps'] = med([tim.get('prompt_per_second')])
    except Exception as e:
        rec['errore'] = str(e)[:200]
    finally:
        try:
            if srv:
                srv.stop()
        except Exception:
            pass
        if not item.get('keep') and d.exists():
            shutil.rmtree(d, ignore_errors=True)
    with open(RES, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    board()
    ev('fatto', name=name, q=rec.get('q_medio'), tps=rec.get('decode_tps'), tier=rec.get('tier'), err=rec.get('errore'), liberi_gb=round(free_gb()))


def main():
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip())
            if str(pid) in subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], capture_output=True, text=True).stdout:
                ev('gia_in_esecuzione', pid=pid)
                return
        except Exception:
            pass
    LOCK.write_text(str(os.getpid()))
    idle = 0
    while True:
        done = {r['name'] for r in load_results()}
        todo = [i for i in json.loads(QUEUE.read_text(encoding='utf-8')) if i['name'] not in done]
        if not todo:
            try:
                import scout
                n = scout.refill()
            except Exception as e:
                n = 0
                ev('scout_errore', err=str(e)[:120])
            ev('scout', aggiunti=n)
            if n == 0:
                idle += 1
                if idle > 6:
                    ev('coda_vuota')
                    return
                time.sleep(1800)
            continue
        idle = 0
        run_item(todo[0])


if __name__ == '__main__':
    main()
