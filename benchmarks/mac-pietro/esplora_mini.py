"""ESPLORA-MINI: 3 compiti di esplorazione di una cartella grande (molti file, registri lunghi), stesso formato di agente_mini.py.
Misura quanto pesa la LETTURA (output lunghi dei comandi, molti file) e non la scrittura di codice: e il caso dove un agente locale
e piu lento (sessione reale da 45 minuti). Un comando ingenuo (`cat` del registro, `find` senza filtro) produce decine di migliaia
di token; un comando mirato (`grep -c`, `awk`, `sort | uniq -c`) ne produce dieci. I file sono generati in modo deterministico.
Uso: come agente_mini (T, setup, grade, oracle); con omp_agente.py: `--tasks=esplora`."""
import random

T = []


def task(name, prompt, files, visible, hidden, oracle):
    T.append({'name': name, 'prompt': prompt, 'files': files, 'visible': visible, 'hidden': hidden, 'oracle': oracle})


MODULI = ['auth', 'billing', 'cache', 'db', 'export', 'gateway', 'inventory', 'mailer', 'metrics', 'notify', 'orders', 'payments',
          'queue', 'reports', 'scheduler', 'search', 'sessions', 'storage', 'sync', 'users']
LIVELLI = ['DEBUG'] * 60 + ['INFO'] * 30 + ['WARN'] * 7 + ['ERROR'] * 3
MSG = ['request handled in {} ms', 'cache miss for key k{}', 'retrying operation ({} left)', 'connection pool size {}',
       'payload of {} bytes', 'job {} finished', 'slow query: {} ms', 'user {} not found', 'timeout after {} s', 'wrote {} rows']

# ---------------------------------------------------------------- 1) registro lungo: quale modulo ha piu ERROR
rnd = random.Random(2026)
righe, err = [], {m: 0 for m in MODULI}
for i in range(24000):
    m = rnd.choice(MODULI); lv = rnd.choice(LIVELLI)
    if lv == 'ERROR':
        err[m] += 1
    righe.append(f'2026-11-0{1 + i // 4000} {i % 24:02d}:{(i * 7) % 60:02d}:{(i * 13) % 60:02d} [{lv}] {m}: ' + rnd.choice(MSG).format(rnd.randint(1, 5000)))
# rende il vincitore unico e netto
vinc = max(err, key=err.get); err[vinc] += 25
for _ in range(25):
    k = rnd.randrange(len(righe)); righe.insert(k, f'2026-11-03 12:00:00 [ERROR] {vinc}: ' + rnd.choice(MSG).format(7))
RISPOSTA_LOG = f'{vinc} {err[vinc]}'
task('errori_log', 'The file logs/app.log is large. Find which module produced the most lines at level ERROR (the module is the word '
     'right after the level, before the colon) and how many such lines it has. Write exactly "<module> <count>" (one line, nothing else) to answer.txt.',
     {'logs/app.log': '\n'.join(righe) + '\n', 'logs/README.txt': 'Format: DATE TIME [LEVEL] module: message\n'},
     'import os\nassert os.path.exists("answer.txt"), "answer.txt missing"\nprint("OK")\n',
     'import os\nv=open("answer.txt").read().strip() if os.path.exists("answer.txt") else ""\n'
     f'print("SCORE", 1 if v=={RISPOSTA_LOG!r} else 0, 1)\n',
     {'answer.txt': RISPOSTA_LOG + '\n'})

# ---------------------------------------------------------------- 2) 80 file di configurazione: una chiave scritta male
rnd = random.Random(7)
SERV = [f'svc-{a}{b}' for a in 'abcdefghij' for b in range(8)]  # 80 servizi
CHIAVI = ['name', 'port', 'replicas', 'timeout_s', 'retries', 'log_level', 'memory_mb', 'healthcheck']
SBAGLIATO = 'svc-f5'
cfg = {}
for s in SERV:
    r = [f'name = {s}', f'port = {rnd.randint(1000, 9999)}', f'replicas = {rnd.randint(1, 6)}', f'timeout_s = {rnd.choice([5, 10, 30, 60])}',
         f'retries = {rnd.randint(0, 5)}', f'log_level = {rnd.choice(["info", "warn", "debug"])}', f'memory_mb = {rnd.choice([256, 512, 1024])}',
         f'healthcheck = /health']
    if s == SBAGLIATO:
        r[3] = r[3].replace('timeout_s', 'timeuot_s')
    cfg[f'config/services/{s}.conf'] = '# service configuration\n' + '\n'.join(r) + '\n'
cfg['config/SCHEMA.md'] = 'Every service file must contain exactly these keys: ' + ', '.join(CHIAVI) + '\n'
task('chiave_config', 'The folder config/services has one .conf file per service. Exactly one file has a key name that does not match '
     'config/SCHEMA.md (a typo). Find that service and write its name (the value of its "name" key, nothing else) to answer.txt.',
     cfg,
     'import os\nassert os.path.exists("answer.txt"), "answer.txt missing"\nprint("OK")\n',
     'import os\nv=open("answer.txt").read().strip() if os.path.exists("answer.txt") else ""\n'
     f'print("SCORE", 1 if v=={SBAGLIATO!r} else 0, 1)\n',
     {'answer.txt': SBAGLIATO + '\n'})

# ---------------------------------------------------------------- 3) 120 moduli: un import rotto da trovare e correggere
rnd = random.Random(11)
src = {'src/pkg/__init__.py': '', 'src/pkg/util.py': 'def parse_date(s):\n    y, m, d = s.split("-")\n    return int(y), int(m), int(d)\n\n\ndef slug(s):\n    return s.lower().replace(" ", "-")\n'}
NOMI = [f'mod_{i:03d}' for i in range(120)]
ROTTO = 'mod_087'
for n in NOMI:
    dep = rnd.choice(['parse_date', 'slug'])
    if n == ROTTO:
        dep = 'parse_dtae'
    src[f'src/pkg/{n}.py'] = (f'"""Module {n}."""\nfrom pkg.util import {dep}\n\n\ndef run(x):\n    return {dep}(x) if isinstance(x, str) else None\n\n\n'
                             f'CONST_{n.upper()} = {rnd.randint(1, 999)}\n')
src['src/check_imports.py'] = ('import importlib, pkgutil, sys\nsys.path.insert(0, "src")\nimport pkg\nbad = []\nfor m in pkgutil.iter_modules(pkg.__path__):\n'
                               '    try:\n        importlib.import_module("pkg." + m.name)\n    except Exception as e:\n        bad.append((m.name, str(e)))\n'
                               'print("BAD", bad)\n')
task('import_rotto', 'Running `python3 src/check_imports.py` reports a module of src/pkg that fails to import. Find it, fix the import '
     '(the intended function exists in pkg/util.py under a slightly different name) with a minimal edit, and make the check print "BAD []".',
     src,
     'import subprocess, sys\nout = subprocess.run([sys.executable, "src/check_imports.py"], capture_output=True, text=True).stdout\nassert "BAD []" in out, out\nprint("OK")\n',
     'import subprocess, sys, os\nout = subprocess.run([sys.executable, "src/check_imports.py"], capture_output=True, text=True).stdout\n'
     f'ok1 = "BAD []" in out\nsrc = open("src/pkg/{ROTTO}.py").read() if os.path.exists("src/pkg/{ROTTO}.py") else ""\n'
     'ok2 = "parse_date" in src and "parse_dtae" not in src\n'
     'ok3 = all(open(f"src/pkg/mod_{i:03d}.py").read().count("CONST_") == 1 for i in range(120))\n'
     'print("SCORE", int(ok1) + int(ok2) + int(ok3), 3)\n',
     {f'src/pkg/{ROTTO}.py': src[f'src/pkg/{ROTTO}.py'].replace('parse_dtae', 'parse_date')})
