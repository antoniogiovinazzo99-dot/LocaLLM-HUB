"""AGENTE-MINI: harness agentico leggero e veloce (6 compiti, ~8-15 min totali) con strumenti reali e test nascosti.
Il modello lavora in una cartella temporanea con 5 strumenti (list_files, read_file, write_file, run_tests, run_python) tramite function calling
OpenAI-compatibile (llama-server --jinja o Strata). Misura: successo (frazione di test nascosti), turni, chiamate di strumento, chiamate non valide, token, secondi.
Controllo positivo: oracle() applica la soluzione di riferimento con gli stessi strumenti e deve dare 100%; senza intervento deve dare 0%."""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, urllib.request

TOOLS = [
    {'type': 'function', 'function': {'name': 'list_files', 'description': 'List all files in the project (relative paths).', 'parameters': {'type': 'object', 'properties': {}}}},
    {'type': 'function', 'function': {'name': 'read_file', 'description': 'Read a text file.', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'write_file', 'description': 'Create or overwrite a text file with the full new content.', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['path', 'content']}}},
    {'type': 'function', 'function': {'name': 'run_tests', 'description': 'Run the visible tests (python test_visible.py) and return their output.', 'parameters': {'type': 'object', 'properties': {}}}},
    {'type': 'function', 'function': {'name': 'run_python', 'description': 'Run a short Python snippet in the project folder and return stdout/stderr.', 'parameters': {'type': 'object', 'properties': {'code': {'type': 'string'}}, 'required': ['code']}}},
]
SYSTEM = ('You are a software engineering agent working in a small project folder. Use the tools to inspect files, edit them and run tests. '
          'Work efficiently: read what you need, make the fix, run the tests, and stop when the task is done by replying with a short final message (no tool call).')

T = []


def task(name, prompt, files, visible, hidden, oracle):
    T.append({'name': name, 'prompt': prompt, 'files': files, 'visible': visible, 'hidden': hidden, 'oracle': oracle})


# ---------------------------------------------------------------- compiti
task('bug_prezzi', 'The visible tests fail. Find the cause and fix it. Do not edit the tests.',
     {'cart.py': 'from pricing import apply_coupon\n\ndef total(items, coupon=None):\n    s = sum(p * q for p, q in items)\n    return apply_coupon(s, coupon) if coupon else s\n',
      'pricing.py': 'def apply_coupon(amount, coupon):\n    kind, value = coupon\n    if kind == "percent":\n        return amount - value\n    if kind == "fixed":\n        return max(0, amount - value)\n    raise ValueError("bad coupon")\n'},
     'from cart import total\nassert total([(100, 2)], ("percent", 10)) == 180, "percent coupon"\nassert total([(50, 1)], ("fixed", 80)) == 0\nprint("OK")\n',
     'from cart import total\nT=[lambda: total([(100,2)],("percent",10))==180, lambda: total([(100,1)],("percent",100))==0, lambda: total([(100,1)],("percent",0))==100,\n lambda: total([(100,1)],("fixed",30))==70, lambda: total([(10,1)],("fixed",30))==0, lambda: total([(100,1)])==100,\n lambda: round(total([(30,1)],("percent",15)),2)==25.5]\nok=0\nfor t in T:\n    try: ok+=1 if t() else 0\n    except Exception: pass\nprint("SCORE",ok,len(T))\n',
     {'pricing.py': 'def apply_coupon(amount, coupon):\n    kind, value = coupon\n    if kind == "percent":\n        return amount * (100 - value) / 100\n    if kind == "fixed":\n        return max(0, amount - value)\n    raise ValueError("bad coupon")\n'})

task('config_loader', 'Read README.md and implement what it asks in config.py so the visible tests pass. Hidden tests will check the edge cases described in the README.',
     {'README.md': 'config.py must define load_config(text, defaults=None) -> dict.\nFormat: one "key = value" per line. Lines starting with # and blank lines are ignored. Inline comments after " #" are stripped.\nValues "true"/"false" (any case) become bool, integers become int, everything else stays str (stripped). Quotes around a string value ("..." or \'...\') are removed and then kept literally (no comment stripping inside quotes).\nA line without "=" raises ValueError(line number). Later keys override earlier ones. defaults is merged under the parsed values.\n',
      'config.py': '# TODO\n'},
     'from config import load_config\nassert load_config("a = 1\\nb = true") == {"a": 1, "b": True}\nassert load_config("# c\\nx = hi # note") == {"x": "hi"}\nprint("OK")\n',
     'from config import load_config\ndef r(f):\n    try: f(); return False\n    except ValueError: return True\nT=[lambda: load_config("a = 1\\nb = true")=={"a":1,"b":True}, lambda: load_config("x = hi # note")=={"x":"hi"}, lambda: load_config("x = \\"a # b\\"")=={"x":"a # b"},\n lambda: load_config("a=1\\na=2")=={"a":2}, lambda: load_config("a=1",{"b":5})=={"a":1,"b":5}, lambda: load_config("b = FALSE")=={"b":False},\n lambda: load_config("n = -7")=={"n":-7}, lambda: load_config("")=={}, lambda: r(lambda: load_config("a=1\\nbad line")), lambda: load_config("s = \'q\'")=={"s":"q"}, lambda: load_config("v = 1.5")=={"v":"1.5"}]\nok=0\nfor t in T:\n    try: ok+=1 if t() else 0\n    except Exception: pass\nprint("SCORE",ok,len(T))\n',
     {'config.py': 'import re\n\ndef _val(v):\n    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\\"\'":\n        return v[1:-1]\n    v = re.split(r"\\s+#", v)[0].strip()\n    if v.lower() == "true": return True\n    if v.lower() == "false": return False\n    if re.fullmatch(r"-?\\d+", v): return int(v)\n    return v\n\ndef load_config(text, defaults=None):\n    out = dict(defaults or {})\n    for n, line in enumerate(text.splitlines(), 1):\n        s = line.strip()\n        if not s or s.startswith("#"):\n            continue\n        if "=" not in s:\n            raise ValueError(n)\n        k, v = s.split("=", 1)\n        out[k.strip()] = _val(v.strip())\n    return out\n'})

task('rinomina', 'Rename the function calc_tax to compute_tax everywhere in the project (definition, imports, calls, and mentions in docs/comments). Behavior must not change. The visible tests use the new name.',
     {'tax.py': 'def calc_tax(amount, rate=0.2):\n    """calc_tax returns the tax on amount."""\n    return round(amount * rate, 2)\n',
      'invoice.py': 'from tax import calc_tax\n\ndef gross(amount):\n    return amount + calc_tax(amount)\n',
      'report.py': 'import tax\n\ndef tax_line(a):\n    return "tax: %.2f" % tax.calc_tax(a, 0.1)\n',
      'NOTES.md': 'Use calc_tax for all tax math.\n'},
     'from invoice import gross\nfrom report import tax_line\nfrom tax import compute_tax\nassert compute_tax(100) == 20\nassert gross(100) == 120\nassert tax_line(100) == "tax: 10.00"\nprint("OK")\n',
     'import re,glob\nfrom invoice import gross\nfrom report import tax_line\nimport tax\nsrc="".join(open(f,encoding="utf-8").read() for f in glob.glob("*.py")+glob.glob("*.md") if not f.startswith(("test_","hidden")))\nT=[lambda: tax.compute_tax(100)==20, lambda: gross(100)==120, lambda: tax_line(100)=="tax: 10.00", lambda: not hasattr(tax,"calc_tax"), lambda: "calc_tax" not in src, lambda: tax.compute_tax(40,0.25)==10]\nok=0\nfor t in T:\n    try: ok+=1 if t() else 0\n    except Exception: pass\nprint("SCORE",ok,len(T))\n',
     {'tax.py': 'def compute_tax(amount, rate=0.2):\n    """compute_tax returns the tax on amount."""\n    return round(amount * rate, 2)\n', 'invoice.py': 'from tax import compute_tax\n\ndef gross(amount):\n    return amount + compute_tax(amount)\n',
      'report.py': 'import tax\n\ndef tax_line(a):\n    return "tax: %.2f" % tax.compute_tax(a, 0.1)\n', 'NOTES.md': 'Use compute_tax for all tax math.\n'})

task('paginazione', 'The visible test crashes. Fix paginate() in pager.py. The README describes the intended behavior; hidden tests cover the edge cases.',
     {'README.md': 'paginate(items, page, size) returns the items of the 1-based page. page < 1 or size < 1 raises ValueError. A page past the end returns []. page_count(n, size) is the number of pages (0 for n == 0).\n',
      'pager.py': 'def paginate(items, page, size):\n    start = page * size\n    return items[start:start + size + 1]\n\ndef page_count(n, size):\n    return n // size\n'},
     'from pager import paginate, page_count\nassert paginate(list(range(10)), 1, 4) == [0, 1, 2, 3]\nassert paginate(list(range(10)), 3, 4) == [8, 9]\nassert page_count(10, 4) == 3\nprint("OK")\n',
     'from pager import paginate, page_count\ndef r(f):\n    try: f(); return False\n    except ValueError: return True\nT=[lambda: paginate(list(range(10)),1,4)==[0,1,2,3], lambda: paginate(list(range(10)),3,4)==[8,9], lambda: paginate(list(range(10)),4,4)==[], lambda: page_count(10,4)==3, lambda: page_count(8,4)==2,\n lambda: page_count(0,4)==0, lambda: r(lambda: paginate([1],0,2)), lambda: r(lambda: paginate([1],1,0)), lambda: paginate([],1,3)==[]]\nok=0\nfor t in T:\n    try: ok+=1 if t() else 0\n    except Exception: pass\nprint("SCORE",ok,len(T))\n',
     {'pager.py': 'def paginate(items, page, size):\n    if page < 1 or size < 1:\n        raise ValueError\n    start = (page - 1) * size\n    return items[start:start + size]\n\ndef page_count(n, size):\n    if size < 1:\n        raise ValueError\n    return -(-n // size)\n'})

task('dati_ordini', 'Open data/orders.csv. Count the orders whose status is "paid" and whose total is strictly greater than 100, and write just that integer (nothing else) to answer.txt. Beware of messy rows.',
     {'data/orders.csv': 'id,customer,total,status\n1,ann,150.00,paid\n2,bob,99.99,paid\n3,"smith, jo",100.01,paid\n4,cy,500,refunded\n5,di,100.00,paid\n6,ed,"1,250.50",paid\n7,flo,101,PAID\n8,gus,abc,paid\n9,hal,250,pending\n10,ivy,100.5,paid\n',
      'notes.txt': 'Totals may contain thousands separators inside quotes. Status comparison is case-sensitive in our reports.\n'},
     'import os\nassert os.path.exists("answer.txt"), "answer.txt missing"\nprint("OK")\n',
     'import os\nv=open("answer.txt").read().strip() if os.path.exists("answer.txt") else ""\nprint("SCORE", 1 if v=="4" else 0, 1)\n',
     {'answer.txt': '4'})

task('rapporto', 'Implement build_report(rows) in report.py exactly as README.md specifies and make the visible test pass. Hidden tests check ordering and formatting rules.',
     {'README.md': 'build_report(rows) takes a list of (customer, amount_cents:int). Return a string: one line per customer "name: $X.YY" (amount in dollars with 2 decimals, thousands NOT separated), customers sorted by total descending, ties alphabetical, one final line "TOTAL: $X.YY". Customers with a total of 0 are omitted. Lines are joined with "\\n", no trailing newline. Empty report returns "TOTAL: $0.00".\n',
      'report.py': 'def build_report(rows):\n    raise NotImplementedError\n'},
     'from report import build_report\nout = build_report([("ann", 1050), ("bob", 2000), ("ann", 150)])\nassert out == "bob: $20.00\\nann: $12.00\\nTOTAL: $32.00", out\nprint("OK")\n',
     'from report import build_report\nT=[lambda: build_report([("ann",1050),("bob",2000),("ann",150)])=="bob: $20.00\\nann: $12.00\\nTOTAL: $32.00", lambda: build_report([])=="TOTAL: $0.00", lambda: build_report([("z",100),("a",100)])=="a: $1.00\\nz: $1.00\\nTOTAL: $2.00",\n lambda: build_report([("a",0),("b",5)])=="b: $0.05\\nTOTAL: $0.05", lambda: build_report([("a",123456)])=="a: $1234.56\\nTOTAL: $1234.56", lambda: build_report([("a",100),("a",-100)])=="TOTAL: $0.00"]\nok=0\nfor t in T:\n    try: ok+=1 if t() else 0\n    except Exception: pass\nprint("SCORE",ok,len(T))\n',
     {'report.py': 'def build_report(rows):\n    tot = {}\n    for c, a in rows:\n        tot[c] = tot.get(c, 0) + a\n    items = sorted(((c, a) for c, a in tot.items() if a != 0), key=lambda x: (-x[1], x[0]))\n    f = lambda a: "$%d.%02d" % (a // 100, a % 100)\n    lines = ["%s: %s" % (c, f(a)) for c, a in items] + ["TOTAL: " + f(sum(a for _, a in items))]\n    return "\\n".join(lines)\n'})


# ---------------------------------------------------------------- esecuzione
def _safe_path(ws, p):
    full = os.path.normpath(os.path.join(ws, p))
    if not full.startswith(os.path.normpath(ws)):
        raise ValueError('path outside project')
    return full


def _run(ws, args, timeout=20):
    try:
        r = subprocess.run([sys.executable, '-B'] + args, capture_output=True, text=True, timeout=timeout, cwd=ws, env={**os.environ, 'PYTHONPATH': ws})
        return (r.stdout + r.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        return 'timeout'


def call_tool(ws, name, args):
    if name == 'list_files':
        out = []
        for root, _, fs in os.walk(ws):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f), ws).replace('\\', '/')
                if not rel.startswith(('hidden', '__pycache__')) and '__pycache__' not in rel:
                    out.append(rel)
        return '\n'.join(sorted(out))
    if name == 'read_file':
        return open(_safe_path(ws, args['path']), encoding='utf-8').read()[:6000]
    if name == 'write_file':
        p = _safe_path(ws, args['path']); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8').write(args['content'])
        return 'written %d chars' % len(args['content'])
    if name == 'run_tests':
        return _run(ws, ['test_visible.py'])
    if name == 'run_python':
        return _run(ws, ['-c', args['code']])
    raise KeyError(name)


def grade(ws, t):
    open(os.path.join(ws, 'hidden.py'), 'w', encoding='utf-8').write(t['hidden'])
    out = _run(ws, ['hidden.py'], timeout=30)
    m = re.search(r'SCORE (\d+) (\d+)', out)
    return int(m.group(1)) / int(m.group(2)) if m else 0.0


def setup(t):
    ws = tempfile.mkdtemp(prefix='agm_')
    for p, c in t['files'].items():
        os.makedirs(os.path.dirname(os.path.join(ws, p)), exist_ok=True)
        open(os.path.join(ws, p), 'w', encoding='utf-8').write(c)
    open(os.path.join(ws, 'test_visible.py'), 'w', encoding='utf-8').write(t['visible'])
    return ws


def oracle(t, apply=True):
    ws = setup(t)
    try:
        if apply:
            for p, c in t['oracle'].items():
                call_tool(ws, 'write_file', {'path': p, 'content': c})
        return grade(ws, t)
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def _post(port, body, timeout=900):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def run_task(port, t, think=False, max_turns=10, model='x', seed=1234, deadline=None):
    ws = setup(t); st = {'turni': 0, 'chiamate': 0, 'non_valide': 0, 'token': 0, 'errori_tool': 0}; t0 = time.time()
    msgs = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': t['prompt']}]
    try:
        for _ in range(max_turns):
            if deadline and time.time() > deadline:
                break
            st['turni'] += 1
            d = _post(port, {'model': model, 'messages': msgs, 'tools': TOOLS, 'tool_choice': 'auto', 'temperature': 0.2, 'top_p': 0.95, 'seed': seed, 'max_tokens': 2500 if think else 1500,
                             'chat_template_kwargs': {'enable_thinking': think}})
            m = d['choices'][0]['message']; st['token'] += (d.get('usage') or {}).get('completion_tokens', 0)
            msgs.append({k: v for k, v in m.items() if k in ('role', 'content', 'tool_calls') and v is not None})
            calls = m.get('tool_calls') or []
            if not calls:
                break
            for c in calls:
                st['chiamate'] += 1
                try:
                    args = json.loads(c['function']['arguments'] or '{}')
                    res = call_tool(ws, c['function']['name'], args)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    st['non_valide'] += 1; res = 'ERROR invalid tool call: %s' % str(e)[:150]
                except Exception as e:
                    st['errori_tool'] += 1; res = 'ERROR %s' % str(e)[:150]
                msgs.append({'role': 'tool', 'tool_call_id': c.get('id', ''), 'content': res})
        g = grade(ws, t)
        return {'nome': t['name'], 'successo': round(g, 3), 'pieno': int(g > 0.999), 'sec': round(time.time() - t0, 1), **st}
    except Exception as e:
        return {'nome': t['name'], 'successo': 0.0, 'sec': round(time.time() - t0, 1), 'errore': str(e)[:150], **st}
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def run_all(port, think=False, log=print, budget_min=6, **k):
    out = []; t0 = time.time(); B = budget_min * 60
    for i, t in enumerate(T):
        left = B - (time.time() - t0)
        if left <= 0:
            break
        r = run_task(port, t, think=think, deadline=time.time() + max(left, 30), **k); out.append(r); log(r['nome'], r['successo'], r.get('turni'), r['sec'])
    n = len(out)
    return {'agente_mini': round(100 * sum(r.get('pieno', 0) for r in out) / n, 1), 'parziale': round(100 * sum(r['successo'] for r in out) / n, 1), 'compiti_fatti': n,
            'turni_medi': round(sum(r['turni'] for r in out) / n, 1), 'non_valide': sum(r['non_valide'] for r in out),
            'sec_totali': round(sum(r['sec'] for r in out)), 'dettaglio': out}


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'control':
        for t in T:
            print(t['name'], 'senza intervento', oracle(t, apply=False), '| con soluzione', oracle(t, apply=True))
    else:
        print(json.dumps(run_all(int(sys.argv[1])), indent=1))
