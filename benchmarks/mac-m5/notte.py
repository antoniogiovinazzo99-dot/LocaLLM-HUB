#!/usr/bin/env python3
"""Banco di prova notturno: esegue una coda di esperimenti (un server per esperimento, piu test) e scrive
una riga JSON per esperimento in risultati/notte.jsonl.
Uso: notte.py coda.json        (salta gli id gia riusciti; si ferma se la batteria scende sotto il 20%)
Esperimento: {"id", "model" (file in modelli/), "ctx", "spec", "kv", "b", "ub", "extra", "engine", "cmd" (alternativa
completa), "tests": ["speed", "long", "core", "agente", "agentemini", "duro --n=15", "lungo --max=64000"], "load_timeout"}"""
import glob, json, os, re, subprocess, sys, time, urllib.request, uuid

D = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.join(D, '..', 'LocaLLM-HUB')
MP = os.path.join(HUB, 'benchmarks', 'mac-pietro')
PY = os.path.join(D, 'venv', 'bin', 'python')
ENG = {'b12038': os.path.join(D, 'motore', 'llama-b12038', 'llama-server')}
for p in glob.glob(os.path.join(D, 'motore', '*', 'llama-server')):
    ENG.setdefault(os.path.basename(os.path.dirname(p)).replace('llama-', ''), p)
PORT = 8080
URL = f'http://127.0.0.1:{PORT}'
OUT = os.path.join(D, 'risultati', 'notte.jsonl')
LOG = os.path.join(D, 'log')
DRAFT = os.path.join(D, 'modelli', 'Qwen3.5-35B-A3B-DFlash-Q4_K_M.gguf')
CORE = json.load(open(os.path.join(HUB, 'benchmarks', 'core-speed', 'prompts.json')))['prompts']
os.makedirs(LOG, exist_ok=True)
os.makedirs(os.path.dirname(OUT), exist_ok=True)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def battery():
    o = sh('pmset -g batt')
    m = re.search(r'(\d+)%', o)
    return (int(m.group(1)) if m else 100), ('discharging' not in o)


def swap_mb():
    m = re.search(r'used = ([\d.]+)M', sh('sysctl vm.swapusage'))
    return float(m.group(1)) if m else -1


def kill_servers():
    for pat in ('modelli-locali/motore', 'llamacpp-prism', 'strata-engine', 'strata/'):
        subprocess.run(['pkill', '-f', pat])
    time.sleep(3)


def health(timeout, proc):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        for path in ('/health', '/v1/models'):
            try:
                with urllib.request.urlopen(URL + path, timeout=3) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
        time.sleep(2)
    return False


def chat(msgs, max_tokens, extra=None, timeout=1800):
    body = {'model': 'locale', 'messages': msgs, 'max_tokens': max_tokens, 'temperature': 0, 'seed': 1, 'stream': False}
    body.update(extra or {})
    req = urllib.request.Request(URL + '/v1/chat/completions', json.dumps(body).encode(), {'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    el = time.time() - t0
    t = d.get('timings') or {}
    if not t.get('predicted_per_second'):  # motori senza timings: stima a orologio
        n = (d.get('usage') or {}).get('completion_tokens') or 0
        t = {'predicted_per_second': n / el if el else 0, 'predicted_n': n, 'prompt_n': (d.get('usage') or {}).get('prompt_tokens'), 'stima': True}
    return t, el, d


def t_speed(exp, args):
    """Scrittura su testo nuovo: i 4 prompt di core-speed una volta sola (niente ripetizioni per ngram-mod).
    --rip=N ripete il giro N volte (solo per config senza ngram-mod: a temperatura 0 il testo e lo stesso) e da media, min, max."""
    rip = int(next((a.split('=')[1] for a in args if a.startswith('--rip=')), 1))
    chat([{'role': 'user', 'content': 'Say hi.'}], 8)
    giri, r, dn, da = [], {}, 0, 0
    for g in range(rip):
        rg = {}
        for k, q in CORE.items():
            t, _, _ = chat([{'role': 'user', 'content': q}], 300)
            rg[k] = round(t.get('predicted_per_second', 0), 1)
            dn += t.get('draft_n') or 0
            da += t.get('draft_n_accepted') or 0
        giri.append(round(sum(rg.values()) / len(rg), 1))
        for k, v in rg.items():
            r.setdefault(k, []).append(v)
    r = {k: round(sum(v) / len(v), 1) for k, v in r.items()}
    out = {'tps': round(sum(giri) / len(giri), 1), 'per_tipo': r}
    if rip > 1:
        out.update({'giri': giri, 'min': min(giri), 'max': max(giri)})
    if dn:
        out['acc'] = round(100 * da / dn, 1)
    return out


LONG_TASKS = {
    'prosa': 'Riassumi il testo sopra in cinque frasi, in italiano.',
    'json': 'Estrai dal testo sopra 8 misure numeriche (nome del modello o della configurazione, valore, unita) e restituiscile come array JSON. Solo JSON.',
    'codice': 'Scrivi una funzione Python che legge un file JSON di risultati come quelli descritti sopra e stampa una classifica per token al secondo. Solo codice.',
}


def t_long(exp, args):
    """Prompt lungo stile agente (~15k token): velocita di lettura, poi scrittura su 3 compiti con il prefisso in cache."""
    nchar = int(next((a.split('=')[1] for a in args if a.startswith('--char=')), 44000))
    testo = ''.join(open(f, encoding='utf-8').read() for f in sorted(glob.glob(os.path.join(HUB, 'docs', '*.md'))))
    testo = f'[{uuid.uuid4()}]\n' + (testo * 30)[:nchar]
    out, dn, da = {}, 0, 0
    for i, (k, q) in enumerate(LONG_TASKS.items()):
        t, _, _ = chat([{'role': 'user', 'content': testo + '\n\n' + q}], 200)
        if i == 0:
            out['token'] = t.get('prompt_n')
            out['lettura_tps'] = round(t.get('prompt_per_second') or 0, 1)
        out[k] = round(t.get('predicted_per_second', 0), 1)
        dn += t.get('draft_n') or 0
        da += t.get('draft_n_accepted') or 0
    out['tps'] = round((out['prosa'] + out['json'] + out['codice']) / 3, 1)
    if dn:
        out['acc'] = round(100 * da / dn, 1)
    return out


def run_script(cmd, logname, timeout, env=None):
    e = dict(os.environ)
    e.update(env or {})
    lf = os.path.join(LOG, logname)
    t0 = time.time()
    with open(lf, 'w') as f:
        try:
            rc = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env=e).returncode
        except subprocess.TimeoutExpired:
            rc = 'timeout'
    txt = open(lf, errors='replace').read()
    last = None
    for line in txt.splitlines():
        if line.startswith('{'):
            try:
                last = json.loads(line)
            except Exception:
                pass
    return rc, txt, last, round(time.time() - t0)


def t_core(exp, args):
    od = os.path.join(D, 'risultati', 'core')
    cmd = ['python3', os.path.join(HUB, 'tools', 'speedtest.py'), '--platform', 'mac', '--author', 'Lan', '--title', exp['id'], '--model-name', 'locale',
           '--engine-version', exp.get('engine', 'b12038'), '--chip', 'Apple M5', '--ram-gb', '24', '--os', 'macOS 26.2', '--category', 'speculative', '--out-dir', od]
    rc, txt, _, sec = run_script(cmd, exp['id'] + '.core.log', 1200)
    f = sorted(glob.glob(os.path.join(od, '*' + re.sub(r'[^a-z0-9._-]+', '-', exp['id'].lower()).strip('-') + '.json')))
    if not f:
        return {'errore': txt[-200:]}
    m = json.load(open(f[-1]))['metrics']
    return {'tps': m.get('tps_media'), 'mediana': m.get('decode_tps_1'), 'acc': m.get('draft_acceptance_pct')}


def t_agente(exp, args):
    rc, txt, last, sec = run_script([PY, '-I', os.path.join(MP, 'agente.py'), exp['id'], URL] + args, exp['id'] + '.agente.log', 1800)
    if not last:
        return {'errore': txt[-200:]}
    return {'pct': last.get('totale_pct'), 'corrette': last.get('corrette'), 'sec_compito': last.get('secondi_per_compito'), 'sec': sec}


def t_duro(exp, args, script=None):
    script = script or os.path.join(MP, 'duro.py')
    tag = re.sub(r'[^a-z0-9]+', '', ''.join(args).lower())[:40]
    tmo = int(next((a.split('=')[1] for a in args if a.startswith('--timeout=')), 5400))
    a2 = [a for a in args if not a.startswith('--timeout=')]
    if not any(a.startswith('--sets=') for a in a2):
        a2.append('--sets=math,code,mbpp,mmlu')
    if not any(a.startswith('--jobs=') for a in a2):
        a2.append('--jobs=1')
    env = {'PYV': PY}
    if exp.get('bench_extra'):
        env['BENCH_EXTRA'] = json.dumps(exp['bench_extra'])
    rc, txt, last, sec = run_script([PY, '-I', script, exp['id'], URL] + a2, f"{exp['id']}.{'dev' if 'duro_dev' in script else 'duro'}-{tag}.log", tmo, env)
    if last and last.get('summary') and last.get('errori'):
        json.dump(last['errori'], open(os.path.join(LOG, f"{exp['id']}.{'dev' if 'duro_dev' in script else 'duro'}-{tag}.errori.json"), 'w'), ensure_ascii=False, indent=1)
    seq = {}
    for m in re.finditer(r'^(math|aime|code|mbpp|mmlu) (ok|NO)', txt, re.M):
        seq.setdefault(m.group(1), []).append('1' if m.group(2) == 'ok' else '0')
    seq = {k: ''.join(v) for k, v in seq.items()}
    n = sum(len(v) for v in seq.values())
    ok = sum(v.count('1') for v in seq.values())
    out = {'pct': round(100 * ok / n, 1) if n else None, 'ok': ok, 'n': n, 'seq': seq, 'sec': sec, 'rc': rc}
    if last and last.get('summary'):
        out.update({'cat': last.get('per_categoria_pct'), 'sec_domanda': last.get('secondi_per_domanda'), 'token_medi': last.get('token_medi'), 'troncate': last.get('troncate_pct')})
    elif not n:
        out['errore'] = txt[-200:]
    return out


def t_agentemini(exp, args):
    budget = next((a.split('=')[1] for a in args if a.startswith('--budget=')), '20')
    think = '1' if '--think' in args else '0'
    rc, txt, last, sec = run_script([PY, '-I', os.path.join(D, 'am.py'), str(PORT), budget, think], exp['id'] + '.agentemini.log', int(float(budget) * 60) + 900)
    if not last:
        return {'errore': txt[-200:]}
    return {'pieni_pct': last.get('agente_mini'), 'parziale_pct': last.get('parziale'), 'fatti': last.get('compiti_fatti'), 'turni': last.get('turni_medi'),
            'non_valide': last.get('non_valide'), 'sec': last.get('sec_totali'), 'dettaglio': {r['nome']: [r['successo'], r['sec']] for r in last.get('dettaglio', [])}}


def t_lungo(exp, args):
    rc, txt, last, sec = run_script([PY, '-I', os.path.join(MP, 'lungo.py'), exp['id'], URL] + args, exp['id'] + '.lungo.log', 3 * 3600)
    if not last:
        return {'errore': txt[-300:]}
    last.pop('label', None)
    last['sec'] = sec
    return last


def t_bench(name):
    """bench2/bench3/bench4/ufficiale degli amici (suite usate per il confronto con Flash-Next). Legge il riepilogo dal loro file .jsonl."""
    def f(exp, args):
        script = {'ufficiale': 'bench_ufficiale.py'}.get(name, name + '.py')
        outf = os.path.join(MP, name + '-risultati.jsonl')
        tag = re.sub(r'[^a-z0-9]+', '', ''.join(a for a in args if not a.startswith('--timeout=')).lower())[:40]
        tmo = int(next((a.split('=')[1] for a in args if a.startswith('--timeout=')), 3 * 3600))
        a2 = [a for a in args if not a.startswith('--timeout=')]
        label = exp['id'] + ('-' + tag if tag else '')
        off = os.path.getsize(outf) if os.path.exists(outf) else 0
        rc, txt, last, sec = run_script([PY, '-I', os.path.join(MP, script), label, URL] + a2, f"{exp['id']}.{name}-{tag}.log", tmo, {'PYV': PY})
        summ = None
        if os.path.exists(outf):
            with open(outf, errors='replace') as fh:
                fh.seek(off)
                for line in fh:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if r.get('summary') and r.get('label') == label:
                        summ = r
        summ = summ or (last if last and last.get('summary') else None)
        if not summ:
            return {'errore': txt[-300:], 'rc': rc, 'sec': sec}
        if summ.get('errori'):
            json.dump(summ['errori'], open(os.path.join(LOG, f"{exp['id']}.{name}-{tag}.errori.json"), 'w'), ensure_ascii=False, indent=1)
        return {'pct': summ.get('totale_pct'), 'corrette': summ.get('corrette'), 'cat': summ.get('per_categoria_pct'),
                'sec_domanda': summ.get('secondi_per_domanda'), 'token': summ.get('token'), 'sec': sec, 'rc': rc}
    return f


def t_hermes(exp, args):
    """Hermes vero (profilo lo-zio-tom, hermes -z): N domande una dopo l'altra, ognuna un processo nuovo. Misura i secondi a
    domanda e quanti token di prompt il server ha dovuto rileggere ogni volta (dal registro del server)."""
    qs = ['Quanto fa 17 per 23? Rispondi solo con il numero.', "Qual e la capitale dell'Australia? Rispondi con una parola.",
          'Scrivi una frase di cinque parole sul mare.', 'Quanti giorni ha febbraio in un anno bisestile? Solo il numero.']
    out = {'sec': [], 'risposte': []}
    for q in qs:
        t0 = time.time()
        try:
            r = subprocess.run([os.path.expanduser('~/.local/bin/lo-zio-tom'), '-z', q], capture_output=True, text=True, timeout=900)
            out['risposte'].append(r.stdout.strip()[-80:])
        except subprocess.TimeoutExpired:
            out['risposte'].append('TIMEOUT')
        out['sec'].append(round(time.time() - t0, 1))
    txt = open(os.path.join(LOG, exp['id'] + '.server.log'), errors='replace').read()
    out['prompt_letti'] = [int(x) for x in re.findall(r'prompt eval time =\s+[\d.]+ ms /\s+(\d+) tokens', txt)]
    out['cache_scartata'] = len(re.findall('removing oldest entry', txt))
    out['cache_saltata'] = len(re.findall('exceeds cache size limit', txt))
    return out


TESTS = {'hermes': t_hermes, 'durodev': lambda e, a: t_duro(e, a, os.path.join(D, 'duro_dev.py')), 'ufficiale': t_bench('ufficiale'), 'bench2': t_bench('bench2'), 'bench3': t_bench('bench3'), 'bench4': t_bench('bench4'), 'speed': t_speed, 'long': t_long, 'core': t_core, 'agente': t_agente, 'duro': t_duro, 'agentemini': t_agentemini, 'lungo': t_lungo}


def server_cmd(exp):
    if exp.get('cmd'):
        c = exp['cmd'] if isinstance(exp['cmd'], list) else exp['cmd'].split()
        return [x.replace('{D}', D).replace('{HOME}', os.path.expanduser('~')) for x in c]
    kv = exp.get('kv', 'q4_0')
    c = [ENG[exp.get('engine', 'b12038')], '-m', os.path.join(D, 'modelli', exp['model']), '--alias', 'locale', '--host', '127.0.0.1', '--port', str(PORT),
         '-ngl', str(exp.get('ngl', 99)), '-fa', 'on', '--jinja', '--parallel', '1', '--cache-ram', str(exp.get('cache_ram', 512)),
         '-c', str(exp.get('ctx', 65536)), '-ctk', kv, '-ctv', kv, '-b', str(exp.get('b', 512)), '-ub', str(exp.get('ub', 256))]
    spec = exp.get('spec', 'draft-dflash,ngram-mod')
    if spec != 'none':
        c += ['--spec-type', spec]
        if 'dflash' in spec:
            c += ['-md', exp.get('draft', DRAFT) if os.path.isabs(exp.get('draft', DRAFT)) else os.path.join(D, 'modelli', exp['draft']), '-ngld', '99']
    return c + exp.get('extra', '').split()


def run(exp):
    rec = {'id': exp['id'], 'ts': time.strftime('%m-%d %H:%M'), 'cfg': {k: v for k, v in exp.items() if k not in ('id', 'tests')}, 'tests': {}}
    kill_servers()
    if exp.get('pre'):
        t0 = time.time()
        with open(os.path.join(LOG, exp['id'] + '.pre.log'), 'w') as f:
            try:
                rc = subprocess.run(exp['pre'].replace('{D}', D).replace('{HOME}', os.path.expanduser('~')), shell=True, stdout=f, stderr=subprocess.STDOUT,
                                    timeout=exp.get('pre_timeout', 4 * 3600), cwd=D).returncode
            except subprocess.TimeoutExpired:
                rc = 'timeout'
        rec['pre'] = {'rc': rc, 'sec': round(time.time() - t0)}
        if rc != 0:
            rec['errore'] = 'pre fallito: ' + open(os.path.join(LOG, exp['id'] + '.pre.log'), errors='replace').read()[-300:]
            return rec
    sw0 = swap_mb()
    slog = os.path.join(LOG, exp['id'] + '.server.log')
    t0 = time.time()
    with open(slog, 'w') as f:
        proc = subprocess.Popen(server_cmd(exp), stdout=f, stderr=subprocess.STDOUT, env=dict(os.environ, **exp.get('env', {})))
    try:
        if not health(exp.get('load_timeout', 600), proc):
            rec['errore'] = 'server non pronto: ' + open(slog, errors='replace').read()[-400:]
            return rec
        rec['load_s'] = round(time.time() - t0)
        for spec in exp.get('tests', ['speed']):
            name, *args = spec.split()
            if proc.poll() is not None:
                rec['errore'] = 'server morto prima di ' + spec
                break
            try:
                rec['tests'][spec] = TESTS[name](exp, args)
            except Exception as e:
                rec['tests'][spec] = {'errore': str(e)[:200]}
            print('   ', spec, json.dumps({k: v for k, v in rec['tests'][spec].items() if k not in ('seq', 'dettaglio', 'per_tipo')}, ensure_ascii=False)[:300], flush=True)
        txt = open(slog, errors='replace').read()
        rec['mem'] = {'swap_prima': sw0, 'swap_dopo': swap_mb(), 'oom_gpu': len(re.findall('OutOfMemory', txt))}
        rec['ok'] = True
    finally:
        proc.terminate()
        try:
            proc.wait(20)
        except Exception:
            proc.kill()
        kill_servers()
    return rec


def attesa_batteria():
    """Sotto il 20% a batteria: spegne i server e aspetta la corrente (o il 30%) invece di uscire."""
    detto = False
    while True:
        pct, ac = battery()
        if ac or pct > 20:
            return
        if not detto:
            kill_servers()
            print(f'PAUSA: batteria {pct}%, aspetto il caricatore [{time.strftime("%H:%M")}]', flush=True)
            detto = True
        time.sleep(60)


def visti():
    ok, tent = set(), {}
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                r = json.loads(line)
            except Exception:
                continue
            tent[r['id']] = tent.get(r['id'], 0) + 1
            if r.get('ok'):
                ok.add(r['id'])
    return ok, tent


def esegui(exp):
    attesa_batteria()
    pct, ac = battery()
    print(f"== {exp['id']} [{time.strftime('%H:%M')}] batteria {pct}%{' in carica' if ac else ''}", flush=True)
    caf = subprocess.Popen(['caffeinate', '-ims'])   # sveglio solo durante l'esperimento: in pausa il Mac puo dormire
    try:
        rec = run(exp)
    finally:
        caf.terminate()
    with open(OUT, 'a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    if rec.get('errore'):
        print('   ERRORE', rec['errore'][-300:].replace('\n', ' | '), flush=True)


def main():
    if sys.argv[1] == '--dir':
        # coda continua: esegue in ordine alfabetico i file code/*.json, li rilegge dopo ogni esperimento (si possono
        # aggiungere o modificare file mentre gira), non riprova gli id falliti, si ferma all'ora limite o con il file STOP
        d = sys.argv[2]
        fine = next((a.split('=')[1] for a in sys.argv if a.startswith('--fino=')), '12:00')
        giorno0 = time.strftime('%d')
        while sh("pgrep -f 'notte.py code/'").strip():
            if 'q-apex' in visti()[1]:      # il vecchio banco ha finito la parte utile: lo fermo
                subprocess.run(['pkill', '-f', 'notte.py code/']); kill_servers()
            time.sleep(10)          # aspetta che finisca un altro banco gia in corso
        vuoto = 0
        while True:
            if os.path.exists(os.path.join(D, 'STOP')):
                print('STOP richiesto'); break
            if time.strftime('%d') != giorno0 or time.strftime('%H:%M') >= fine:
                if time.strftime('%H:%M') >= fine and time.strftime('%H') < '18':
                    print('ora limite raggiunta', time.strftime('%H:%M')); break
            ok, tent = visti()
            prossimo = None
            for f in sorted(glob.glob(os.path.join(d, '*.json'))):
                try:
                    coda = json.load(open(f))
                except Exception as e:
                    print('coda illeggibile', os.path.basename(f), str(e)[:80]); continue
                for exp in coda:
                    if exp['id'] not in ok and tent.get(exp['id'], 0) < exp.get('tentativi', 1):
                        prossimo = (f, exp); break
                if prossimo:
                    break
            if not prossimo:
                if vuoto == 0:
                    print('coda vuota', time.strftime('%H:%M'), flush=True)
                    open(os.path.join(D, 'risultati', 'CODA-VUOTA'), 'w').write(time.strftime('%H:%M'))
                vuoto += 1
                time.sleep(60)
                continue
            vuoto = 0
            esegui(prossimo[1])
            open(os.path.join(D, 'risultati', 'ULTIMO'), 'w').write(prossimo[1]['id'] + ' ' + time.strftime('%H:%M'))
        kill_servers()
        return
    coda = json.load(open(sys.argv[1]))
    ok, _ = visti()
    for exp in coda:
        if exp['id'] in ok and '--rifai' not in sys.argv:
            print('salto', exp['id'])
            continue
        esegui(exp)
    print('coda finita', time.strftime('%H:%M'), 'batteria', battery())


if __name__ == '__main__':
    main()
