"""HARNESS REALI: gli stessi 6 compiti di agente_mini.py, ma guidati da agenti veri (Claude Code, opencode, omp) invece del mio mini-harness.
Serve a capire quanto il *contenitore* conta: stesso modello e stessi compiti, harness diverso -> risultati diversi.
Uso:  python harness_reali.py <claude|opencode|omp> <porta> [nome_modello] [compito,compito]
Requisiti: un server locale gia avviato su <porta> con contesto >= 65536 (Claude Code apre ogni sessione con 16-27K token di istruzioni).
Claude Code parla il protocollo Anthropic (/v1/messages): llama-server b12141 e Strata lo espongono; opencode e omp usano quello OpenAI.
Stato: claude e opencode scritti da documentazione/--help (da provare al primo server a 64K); omp richiede che il provider locale punti alla porta giusta."""
import json, os, pathlib, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, r'<HOME>\llm\fabbrica')
import agente_mini as A

PROMPT_EXTRA = '\n\nWork only inside the current folder. When done, make sure `python test_visible.py` prints OK (if it applies), then stop with a one-line summary.'


def cmd_claude(ws, port, model, prompt):
    env = {**os.environ, 'ANTHROPIC_BASE_URL': f'http://127.0.0.1:{port}', 'ANTHROPIC_AUTH_TOKEN': 'local', 'ANTHROPIC_API_KEY': '', 'ANTHROPIC_MODEL': model,
           'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}
    return ['claude', '-p', prompt, '--bare', '--dangerously-skip-permissions', '--output-format', 'json'], env


def cmd_opencode(ws, port, model, prompt):
    cfg = {'$schema': 'https://opencode.ai/config.json', 'provider': {'local': {'npm': '@ai-sdk/openai-compatible', 'name': 'local', 'options': {'baseURL': f'http://127.0.0.1:{port}/v1'},
           'models': {model: {'name': model, 'limit': {'context': 65536, 'output': 8192}}}}}, 'model': f'local/{model}'}
    p = os.path.join(ws, '.opencode-test.json'); json.dump(cfg, open(p, 'w'))
    return ['opencode', 'run', '--model', f'local/{model}', '--auto', '--format', 'json', prompt], {**os.environ, 'OPENCODE_CONFIG': p}


def cmd_omp(ws, port, model, prompt):
    # il provider "strata-local" e definito nella configurazione globale di omp (porta di produzione): per provare un altro server va ripuntato
    return ['omp', '-p', '--no-session', '--auto-approve', '--cwd', ws, '--model', f'strata-local/{model}', prompt], dict(os.environ)


ADAPT = {'claude': cmd_claude, 'opencode': cmd_opencode, 'omp': cmd_omp}


def run_one(harness, port, model, t, timeout=900):
    ws = A.setup(t); t0 = time.time()
    try:
        cmd, env = ADAPT[harness](ws, port, model, t['prompt'] + PROMPT_EXTRA)
        try:
            r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=timeout, shell=(os.name == 'nt'))
            tail = (r.stdout + r.stderr)[-300:]; rc = r.returncode
        except subprocess.TimeoutExpired:
            tail, rc = 'timeout', -9
        g = A.grade(ws, t)
        return {'nome': t['name'], 'harness': harness, 'successo': round(g, 3), 'pieno': int(g > 0.999), 'sec': round(time.time() - t0, 1), 'rc': rc, 'coda': tail}
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def run_all(harness, port, model='m', only=None, log=print):
    out = []
    for t in A.T:
        if only and t['name'] not in only:
            continue
        r = run_one(harness, port, model, t); out.append(r); log(r['nome'], r['successo'], r['sec'], r['rc'])
    n = len(out)
    return {'harness': harness, 'pieno_pct': round(100 * sum(r['pieno'] for r in out) / n, 1), 'parziale_pct': round(100 * sum(r['successo'] for r in out) / n, 1),
            'sec_totali': round(sum(r['sec'] for r in out)), 'dettaglio': out}


if __name__ == '__main__':
    h, port = sys.argv[1], int(sys.argv[2]); model = sys.argv[3] if len(sys.argv) > 3 else 'm'
    only = sys.argv[4].split(',') if len(sys.argv) > 4 else None
    res = run_all(h, port, model, only)
    pathlib.Path(r'<HOME>\llm\fabbrica\log').joinpath(f'harness-{h}-{port}-{int(time.time())}.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k != 'dettaglio'}))
