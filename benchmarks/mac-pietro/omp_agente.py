"""OMP reale sui 6 compiti di agente-mini (benchmarks/windows-fabbrica/agente_mini.py), versione Mac.
Misura per ogni compito: successo sui test nascosti (credito parziale), tempo, numero di passi del modello e token.
Serve a capire cosa rende lento un agente locale: impostazioni di OMP (ragionamento, strumenti, istruzioni) e del server.

Uso: python3 -I omp_agente.py ETICHETTA [--model=llama.cpp/agents-a1] [--thinking=off] [--snello] [--solo=bug_prezzi,...]
     [--timeout=900] [--extra="--altro-flag-omp"] [--tasks=esplora]
  --snello : solo gli strumenti utili ai compiti (read, edit, write, bash, grep, glob), niente LSP, skills, regole,
             estensioni, file di contesto e titolo automatico (che chiama un modello cloud).
Richiede un server gia avviato e omp nel PATH. Scrive omp-agente-risultati.jsonl accanto a se.
"""
import glob, json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "windows-fabbrica"))
sys.path.insert(0, HERE)  # con python -I la cartella dello script non e nel path
import agente_mini as A  # noqa: E402
if any(a == "--tasks=esplora" for a in sys.argv):
    import esplora_mini as E  # noqa: E402
    A.T = E.T  # stessi setup/grade, compiti di esplorazione (benchmarks/mac-pietro/esplora_mini.py)

opt = lambda k, d=None: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), d)
LAB = sys.argv[1]
MODEL = opt("model", "llama.cpp/agents-a1")
THINK = opt("thinking")
SNELLO = "--snello" in sys.argv
SOLO = opt("solo", "").split(",") if opt("solo") else None
TIMEOUT = int(opt("timeout", "900"))
EXTRA = (opt("extra", "") or "").split()
OUT = os.path.join(HERE, "omp-agente-risultati.jsonl")
EXTRA_PROMPT = ("\n\nWork only inside the current folder. When done, make sure `python3 test_visible.py` prints OK "
                "(if it applies), then stop with a one-line summary.")


def passi(sessdir):
    """Conta i passi del modello e i token dalla sessione salvata da omp."""
    n, tin, tout, tcache, altri, pensiero = 0, 0, 0, 0, set(), 0
    for f in glob.glob(os.path.join(sessdir, "**", "*.jsonl"), recursive=True):
        for line in open(f, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") or {}
            if m.get("role") == "assistant":
                n += 1
                if m.get("provider") and m.get("provider") != "llama.cpp":
                    altri.add(f'{m.get("provider")}/{m.get("model")}')
                for x in m.get("content") or []:
                    if isinstance(x, dict) and x.get("type") == "thinking":
                        pensiero += len(x.get("thinking", ""))
                u = m.get("usage") or {}
                tin += u.get("input") or 0
                tout += u.get("output") or 0
                tcache += u.get("cacheRead") or 0
    return n, tin, tout, tcache, sorted(altri), pensiero


def run_one(t):
    ws = A.setup(t)
    sessdir = ws + "-sess"
    cmd = ["omp", "-p", "--cwd", ws, "--model", MODEL, "--session-dir", sessdir]
    if THINK:
        cmd += ["--thinking", THINK]
    if SNELLO:
        cmd += ["--tools", "read,edit,write,bash,grep,glob", "--no-lsp", "--no-skills", "--no-rules", "--no-extensions",
                "--no-context-files", "--no-title"]
    cmd += EXTRA + [t["prompt"] + EXTRA_PROMPT]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=TIMEOUT)
        rc, coda = r.returncode, (r.stdout + r.stderr)[-300:]
    except subprocess.TimeoutExpired:
        rc, coda = -9, "timeout"
    sec = round(time.time() - t0, 1)
    g = A.grade(ws, t)
    n, tin, tout, tcache, altri, pensiero = passi(sessdir)
    shutil.rmtree(ws, ignore_errors=True)
    shutil.rmtree(sessdir, ignore_errors=True)
    return {"nome": t["name"], "successo": round(g, 3), "pieno": int(g > 0.999), "sec": sec, "passi": n,
            "token_in": tin, "token_out": tout, "token_cache": tcache, "car_pensiero": pensiero, "modelli_non_locali": altri, "rc": rc, "coda": coda}


res = []
for t in A.T:
    if SOLO and t["name"] not in SOLO:
        continue
    r = run_one(t)
    res.append(r)
    print(json.dumps({k: r[k] for k in ("nome", "successo", "sec", "passi", "token_out", "car_pensiero", "modelli_non_locali", "rc")}, ensure_ascii=False), flush=True)
n = len(res)
summ = {"label": LAB, "summary": True, "tasks": "esplora" if "--tasks=esplora" in sys.argv else "agente-mini", "model": MODEL, "thinking": THINK, "snello": SNELLO,
        "pieno_pct": round(100 * sum(r["pieno"] for r in res) / n, 1), "parziale_pct": round(100 * sum(r["successo"] for r in res) / n, 1),
        "sec_totali": round(sum(r["sec"] for r in res)), "sec_mediana": sorted(r["sec"] for r in res)[n // 2],
        "passi_medi": round(sum(r["passi"] for r in res) / n, 1),
        "modelli_non_locali": sorted({m for r in res for m in r["modelli_non_locali"]}), "token_out_totali": sum(r["token_out"] for r in res), "dettaglio": res}
open(OUT, "a").write(json.dumps(summ, ensure_ascii=False) + "\n")
print(json.dumps({k: v for k, v in summ.items() if k != "dettaglio"}, ensure_ascii=False))
