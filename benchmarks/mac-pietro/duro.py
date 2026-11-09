"""Benchmark DURO e veloce su set standard (con margine, dove Agents-A1 non è al soffitto):
  math  = MATH-500 livelli 4-5, solo risposte numeriche o frazioni semplici (campione fisso)
  aime  = AIME 2025 (30 problemi, risposta intera 0-999)
  code  = HumanEval+ (test estesi di EvalPlus, campione fisso)
  mbpp  = MBPP+ (campione fisso)
  mmlu  = MMLU-Pro (10 opzioni, 14 materie, campione stratificato)
Uso: python3 -I duro.py ETICHETTA [URL] [--sets=math,code,mmlu] [--n=30] [--think] [--budget=4096] [--tools]
     [--votes=N] [--cheatsheet=F] [--sys=FILE]   + parametri di campionamento via env BENCH_EXTRA='{"presence_penalty":1.5}'
Scrive duro-risultati.jsonl con: punteggi, secondi, quota di risposte troncate (indice di loop di ragionamento).
"""
import collections, json, os, random, re, subprocess, sys, tempfile, time, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench2  # noqa: E402
from bench2 import TOOLS_SYS, ask, extract  # noqa: E402
D = os.path.join(HERE, "dati")
OUT = os.path.join(HERE, "duro-risultati.jsonl")
PYV = os.environ.get("PYV", sys.executable)  # Python con numpy, serve ai test di EvalPlus
if any(s_ in " ".join(sys.argv) for s_ in ("code", "mbpp")) or "--sets" not in " ".join(sys.argv):
    if subprocess.run([PYV, "-I", "-c", "import numpy"], capture_output=True).returncode != 0:
        sys.exit(f"duro.py: il Python dei test ({PYV}) non importa numpy con -I (pacchetti utente esclusi): i test di HumanEval+/MBPP+ fallirebbero tutti (0%). "
                 "Installa numpy o indica un altro Python con PYV=/percorso/python")
SYSP = ("Answer the question. Think step by step if useful, then end with one final line in the format: RISPOSTA: <answer>")

NUM = re.compile(r"^-?\d+(\.\d+)?$")
FRAC = re.compile(r"^-?\\frac\{(-?\d+)\}\{(\d+)\}$")


def norm_math(a):
    a = unicodedata.normalize("NFKC", str(a)).strip().strip("$").strip()
    b = re.search(r"\\boxed\{(.+)\}", a)
    if b:
        a = b.group(1)
    a = a.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac").replace("\\left", "").replace("\\right", "")
    a = a.replace(" ", "").replace("\\!", "").replace("^\\circ", "").replace("^{\\circ}", "").replace("\\%", "").rstrip(".")
    a = re.sub(r"\\text\{[^}]*\}", "", a)
    m = FRAC.match(a)
    if m:
        return float(m.group(1)) / float(m.group(2))
    m = re.match(r"^(-?\d+)/(\d+)$", a)
    if m:
        return float(m.group(1)) / float(m.group(2))
    a = a.replace(",", "")
    if NUM.match(a):
        return float(a)
    return a


def math_ok(ans, gold):
    g = norm_math(gold)
    cands = [ans] + re.findall(r"-?\d+(?:\.\d+)?(?:/\d+)?|\\frac\{-?\d+\}\{\d+\}", ans)[-1:]
    for c in cands:
        v = norm_math(c)
        if isinstance(g, float) and isinstance(v, float) and abs(g - v) < 1e-6 * max(1, abs(g)):
            return True
        if v == g:
            return True
    return False


def load(sets, n):
    r = random.Random(2026)
    items = []
    if "math" in sets:
        m = [x for x in json.load(open(f"{D}/math500.json")) if x["level"] >= 4 and isinstance(norm_math(x["answer"]), float)]
        for x in r.sample(m, min(n, len(m))):
            items.append(("math", x["problem"], x["answer"]))
    if "aime" in sets:
        for x in json.load(open(f"{D}/aime2025.json"))[:n]:
            items.append(("aime", x["problem"] + "\n(The answer is an integer from 0 to 999.)", str(x["answer"])))
    if "code" in sets:
        h = json.load(open(f"{D}/humanevalplus.json"))
        for x in r.sample(h, min(n, len(h))):
            items.append(("code", x, None))
    if "mbpp" in sets:
        h = json.load(open(f"{D}/mbppplus.json"))
        for x in r.sample(h, min(n, len(h))):
            items.append(("mbpp", x, None))
    if "mmlu" in sets:
        mm = json.load(open(f"{D}/mmlupro.json"))
        by = collections.defaultdict(list)
        for x in mm:
            by[x["category"]].append(x)
        per = max(1, n // len(by))
        for c in sorted(by):
            for x in r.sample(by[c], per):
                opts = "\n".join(f"{'ABCDEFGHIJ'[i]}. {o}" for i, o in enumerate(x["options"]))
                items.append(("mmlu", f"{x['question']}\n\n{opts}\n\nRispondi con la sola lettera dell'opzione corretta.", x["answer"]))
    return items


def run_code(code, timeout=30):
    with tempfile.TemporaryDirectory() as d:
        try:
            r = subprocess.run([PYV, "-I", "-c", code], cwd=d, capture_output=True, text=True, timeout=timeout)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False


def code_ok(kind, x, text):
    blocks = re.findall(r"```(?:python)?\s*\n(.+?)```", text, re.S)
    for b in reversed(blocks):
        if kind == "code":
            # il prompt porta import (typing) e funzioni di supporto: lo teniamo sempre, con un corpo provvisorio;
            # la funzione del modello, definita dopo, sostituisce quella provvisoria
            prog = x["prompt"] + "\n" + b if f"def {x['entry_point']}" not in b else x["prompt"] + "    pass\n\n" + b
            prog += "\n\n" + x["test"] + f"\n\ncheck({x['entry_point']})\n"
        else:
            prog = b + "\n\n" + (x.get("test_imports") and "\n".join(x["test_imports"]) or "") + "\n" + x["test"] + "\n"
        if run_code(prog):
            return True
    return False


def visible_check(kind, x, code):
    """Esegue SOLO i test visibili (esempi >>> del docstring per HumanEval, il primo assert mostrato per MBPP).
    Restituisce '' se passano, altrimenti il messaggio d'errore. I test nascosti (EvalPlus) restano nascosti."""
    if kind == "code":
        import ast
        doc = ""
        try:
            for node in ast.walk(ast.parse(x["prompt"] + "\n    pass\n")):
                if isinstance(node, ast.FunctionDef) and node.name == x["entry_point"]:
                    doc = ast.get_docstring(node) or ""
        except SyntaxError:
            pass
        if ">>>" not in doc:
            return ""
        prog = (x["prompt"] + "\n" + code if f"def {x['entry_point']}" not in code else x["prompt"] + "    pass\n\n" + code)
        prog += ("\n\nimport doctest, sys\nD = " + repr(doc) + "\nt = doctest.DocTestParser().get_doctest(D, globals(), 'esempi', None, 0)"
                 "\nr = doctest.DocTestRunner(verbose=False).run(t)\nsys.exit(1 if r.failed else 0)\n")
    else:
        prog = code + "\n" + "\n".join(x.get("test_imports") or []) + "\n" + x["test_list"][0] + "\n"
    with tempfile.TemporaryDirectory() as d:
        try:
            r = subprocess.run([PYV, "-I", "-c", prog], cwd=d, capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return "timeout (20 s): probabile ciclo infinito o codice troppo lento"
    return "" if r.returncode == 0 else (r.stdout + r.stderr)[-1200:]


def ripetizione(t):
    """Quota di frasi ripetute nel testo (0 = nessuna, ~1 = loop): distingue i loop dai ragionamenti solo lunghi."""
    fr = [x.strip().lower() for x in re.split(r"[.\n!?]+", t) if len(x.strip()) > 15]
    return round(1 - len(set(fr)) / len(fr), 2) if fr else 0.0


def _blocchi(t):
    return re.findall(r"```(?:python)?\s*\n(.+?)```", t, re.S)


def arex_codice(url, msgs, t, kind, x, rounds, think, budget):
    """Ciclo AREX-2 (prova-controlla-correggi, arXiv 2609.38288) per il codice: a ogni round il modello conosce il budget
    rimasto, scrive test PROPRI con casi limite, li esegue insieme agli esempi visibili; i tentativi falliti restano nel
    contesto. I test nascosti non vengono mai usati."""
    secs = toks = 0
    hist = msgs + [{"role": "assistant", "content": t}]
    best = t
    for r in range(rounds):
        sol = (_blocchi(best) or [""])[-1]
        err = visible_check(kind, x, sol) if sol else "nessun blocco di codice"
        ask_tests = (f"Round {r + 1} di {rounds}. Scrivi 5-8 assert Python con casi limite (input vuoti, estremi, tipi particolari, "
                     "esempi del testo) per la tua funzione, in un solo blocco ```python``` che contenga SOLO gli assert.")
        tt, k1, s1, _ = ask(url, hist + [{"role": "user", "content": ask_tests}], False, 600, 0.0)
        secs += s1; toks += k1
        tests = (_blocchi(tt) or [""])[-1]
        if tests and not err:
            with tempfile.TemporaryDirectory() as d:
                prog = (x["prompt"] + "    pass\n\n" if kind == "code" else "") + sol + "\n\n" + tests
                try:
                    rr = subprocess.run([PYV, "-I", "-c", prog], cwd=d, capture_output=True, text=True, timeout=20)
                    err = "" if rr.returncode == 0 else (rr.stdout + rr.stderr)[-1000:]
                except subprocess.TimeoutExpired:
                    err = "timeout: ciclo infinito o troppo lento"
        if not err:
            break
        hist = hist + [{"role": "user", "content": ask_tests}, {"role": "assistant", "content": tt},
                       {"role": "user", "content": f"Esecuzione (soluzione + test): FALLISCE\n{err}\nSe sbaglia la funzione, correggila; se sbaglia "
                        f"un tuo test, ignoralo. Restano {rounds - r - 1} round. Riscrivi la funzione completa in un blocco ```python```, poi RISPOSTA: fatto."}]
        t2, k2, s2, _ = ask(url, hist, think, budget, 0.0)
        secs += s2; toks += k2
        hist = hist + [{"role": "assistant", "content": t2}]
        if _blocchi(t2):
            best = t2
    return best, secs, toks


def arex_verifica(url, msgs, t, rounds, think, budget):
    """Ciclo AREX-2 per le domande con risposta: il modello verifica la propria risposta con un programma indipendente
    (sostituzione, forza bruta su casi piccoli, calcolo alternativo) e la rivede se il controllo fallisce."""
    secs = toks = 0
    a0 = extract(t)
    hist = msgs + [{"role": "assistant", "content": t}]
    for r in range(rounds):
        q = (f"Round di verifica {r + 1} di {rounds}. La tua risposta attuale è: {a0}. Controllala con un metodo DIVERSO da quello usato "
             "(sostituzione, forza bruta su casi piccoli, calcolo alternativo in Python). Se il controllo conferma, scrivi di nuovo "
             "RISPOSTA: <la stessa>; se no, correggi e scrivi RISPOSTA: <nuova>.")
        t2, k2, s2 = bench2.solve_with_tools(url, hist + [{"role": "user", "content": q}], think, budget, 0.0)
        secs += s2; toks += k2
        a1 = extract(t2)
        hist = hist + [{"role": "user", "content": q}, {"role": "assistant", "content": t2}]
        t = t2
        if a1 == a0:
            break
        a0 = a1
    return t, secs, toks


CLASSI = ["CALCOLO", "CODICE", "CONOSCENZA", "AGENTE", "ALTRO"]


def classifica(url, user):
    q = ("Classifica la richiesta in UNA categoria: CALCOLO (matematica, conti, problemi numerici, fisica con numeri), "
         "CODICE (scrivere o capire programmi), CONOSCENZA (fatti, concetti, scelta multipla di cultura o scienza senza conti), "
         "AGENTE (agire su calendario, email, file, attività), ALTRO. Rispondi con la sola parola.\n\nRichiesta:\n" + user[:1500])
    t, _, s, _ = ask(url, [{"role": "user", "content": q}], False, 6, 0.0)
    w = re.sub(r"[^A-Z]", "", t.upper())
    return next((c for c in CLASSI if c in w), "ALTRO"), s


def main():
    av = sys.argv
    label = av[1]
    url = next((a for a in av[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    opt = lambda k, d: next((a.split("=", 1)[1] for a in av if a.startswith(f"--{k}=")), d)
    sets = opt("sets", "math,code,mmlu").split(",")
    n = int(opt("n", "30"))
    think = "--think" in av
    tools = "--tools" in av
    budget = int(opt("budget", "4096" if think else "1500"))
    votes = int(opt("votes", "1"))
    selfdebug = "--selfdebug" in av
    forza = "--forza" in av
    arex = int(opt("arex", "0"))
    jobs = int(opt("jobs", "1"))
    rip, forzate = [], 0
    sheet = open(opt("cheatsheet", "")).read().strip() if opt("cheatsheet", "") else ""
    sysmsg = open(opt("sys", "")).read().strip() if opt("sys", "") else SYSP
    sysbase = sysmsg
    politica = json.load(open(opt("politica", ""))) if opt("politica", "") else None
    classi = collections.Counter()
    sysmsg += ("\n" + TOOLS_SYS if tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet else "")
    per, errs = collections.defaultdict(lambda: [0, 0]), []
    secs = toks = 0
    import threading, concurrent.futures
    lock = threading.Lock()
    acc = {"secs": 0.0, "toks": 0, "forzate": 0}
    def fai(item):
        kind, x, gold = item
        secs = toks = 0
        forzate = 0
        if kind == "code":
            user = ("Complete this Python function. Write the full function (with any imports) in one ```python``` block, "
                    "then end with the line RISPOSTA: fatto.\n\n```python\n" + x["prompt"] + "```")
        elif kind == "mbpp":
            fname = (re.search(r"assert\s+(?:not\s+)?\(?\s*(?:set\()?(?:math\.isclose\()?(\w+)\(", x["test_list"][0]) or [None, "?"])[1]
            user = (x["prompt"] + f"\nThe function must be named exactly `{fname}`. It must pass tests like: {x['test_list'][0]}\n"
                    "Write the full function in one ```python``` block, then end with the line RISPOSTA: fatto.")
        else:
            user = x
        it_tools, it_votes, it_sd, it_sys = tools, votes, selfdebug, sysmsg
        it_think, it_budget = think, budget
        if politica:
            # "modello decisore": A1 classifica la richiesta con una chiamata brevissima, poi una politica imparata
            # dai nostri test sceglie la strategia (strumenti, voti, auto-correzione) per quella classe
            classe, sc = classifica(url, user)
            secs += sc
            pol = politica.get(classe, politica.get("ALTRO", {}))
            it_tools, it_votes, it_sd = pol.get("tools", False), pol.get("votes", 1), pol.get("selfdebug", False)
            if "think" in pol:
                it_think, it_budget = pol["think"], pol.get("budget", budget)
            it_sys = sysbase + ("\n" + TOOLS_SYS if it_tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet and pol.get("cheatsheet") else "")
            classi[(kind, classe)] += 1
        msgs = [{"role": "system", "content": it_sys}, {"role": "user", "content": user}]
        c, texts = collections.Counter(), []
        for v in range(it_votes if kind in ("math", "aime", "mmlu") else 1):
            temp = 0.0 if v == 0 else 0.7
            if it_think and politica and v == 0:
                temp = 0.6
            fr = None
            if it_tools:
                t, k, s = bench2.solve_with_tools(url, msgs, it_think, it_budget, temp)
            else:
                t, k, s, fr = ask(url, msgs, it_think, it_budget, temp)
            if fr == "length":
                rip.append(ripetizione(t))
            if forza and fr == "length" and kind in ("math", "aime", "mmlu"):
                # budget forcing (s1): il ragionamento è finito il tempo; si chiede la risposta dai propri appunti
                m3 = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user + "\n\nI tuoi appunti di ragionamento (interrotti):\n" + t[-2500:]
                      + "\n\nIl tempo per ragionare è finito. Scrivi subito solo la riga finale RISPOSTA: <risposta>."}]
                t2, k2, s2, _ = ask(url, m3, False, 200, 0.0)
                s += s2; k += k2; t = t2; forzate += 1
            secs += s
            toks += k
            if it_sd and kind in ("code", "mbpp"):
                for _ in range(2):
                    bl = re.findall(r"```(?:python)?\s*\n(.+?)```", t, re.S)
                    err = visible_check(kind, x, bl[-1]) if bl else "nessun blocco di codice"
                    if not err:
                        break
                    m2 = msgs + [{"role": "assistant", "content": t}, {"role": "user", "content":
                          "I test di esempio falliscono:\n" + err + "\nCorreggi: riscrivi la funzione completa in un blocco ```python```, poi RISPOSTA: fatto."}]
                    t2, k2, s2, _ = ask(url, m2, think, budget, 0.0)
                    secs += s2; toks += k2; t = t2
            if arex and kind in ("code", "mbpp"):
                t, sx, kx = arex_codice(url, msgs, t, kind, x, arex, think, budget)
                secs += sx; toks += kx
            elif arex and kind in ("math", "aime", "mmlu"):
                t, sx, kx = arex_verifica(url, msgs, t, arex, think, budget)
                secs += sx; toks += kx
            texts.append(t)
            c[extract(t)] += 1
            nv = it_votes if kind in ("math", "aime", "mmlu") else 1
            if nv > 1 and c.most_common(1)[0][1] > nv // 2:
                break   # voto adattivo: la maggioranza è già decisa, gli altri campioni non la cambierebbero
        a = c.most_common(1)[0][0]
        if kind in ("math", "aime"):
            ok = math_ok(a, gold)
        elif kind == "mmlu":
            m = re.search(r"\b([A-J])\b", a.upper())
            ok = bool(m) and m.group(1) == gold
        else:
            ok = code_ok(kind, x, texts[0])
        per[kind][0] += ok
        per[kind][1] += 1
        if not ok:
            errs.append({"cat": kind, "gold": gold if isinstance(gold, str) or gold is None else str(gold), "a": a[:60],
                         **({"codice": (re.findall(r"```(?:python)?\s*\n(.+?)```", texts[0], re.S) or [texts[0][-1500:]])[-1][:3000], "testo": texts[0][:1500]} if kind in ("code", "mbpp") else {})})
        print(kind, "ok" if ok else "NO", round(secs), flush=True)
        with lock:
            acc["secs"] += secs; acc["toks"] += toks; acc["forzate"] += forzate
    t_wall = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        list(ex.map(fai, load(sets, n)))
    secs, toks, forzate = acc["secs"], acc["toks"], acc["forzate"]
    wall = time.time() - t_wall
    tot_ok, tot = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    summ = {"label": label, "summary": True, "totale_pct": round(100 * tot_ok / tot, 1), "corrette": f"{tot_ok}/{tot}",
            "per_categoria_pct": {k: round(100 * v[0] / v[1], 1) for k, v in sorted(per.items())},
            "secondi_per_domanda": round(secs / tot, 1), "secondi_muro": round(wall, 1), "jobs": jobs, "token_medi": round(toks / max(1, bench2.STATS["chiamate"])),
            "troncate_pct": round(100 * bench2.STATS["troncate"] / max(1, bench2.STATS["chiamate"]), 1),
            "think": think, "tools": tools, "votes": votes, "budget": budget, "selfdebug": selfdebug, "politica": opt("politica", ""), "classi": {f"{a}->{b}": n for (a, b), n in classi.items()}, "forza": forza, "arex": arex, "forzate": forzate, "ripetizione_troncate": round(sum(rip) / len(rip), 2) if rip else None, "extra": bench2.EXTRA,
            "sys": opt("sys", ""), "cheatsheet": bool(sheet), "errori": errs[:40]}
    open(OUT, "a").write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in summ.items() if k != "errori"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
