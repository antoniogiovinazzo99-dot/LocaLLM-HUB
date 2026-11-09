"""Benchmark v2: intelligenza per categoria (percentuali), fedeltà al modello esatto, contesto lungo a più profondità,
e un "harness" opzionale (ragionamento, budget più ampio, verifica, voto a maggioranza).

Uso:
  python3 -I bench2.py ETICHETTA [URL] [--think] [--harness] [--ref] [--cats a,b] [--max N]
    --ref      salva le risposte come riferimento di fedeltà (da usare con il motore esatto)
    --harness  ragionamento + 3 campioni a temperatura 0,6 + voto a maggioranza + risposta mai tagliata
Scrive bench2-risultati.jsonl (una riga per domanda e un riepilogo con percentuali per categoria).
"""
import collections
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "bench2-risultati.jsonl")
REF = os.path.join(HERE, "bench2-riferimento.json")

# (categoria, nome, domanda, risposte accettate)
Q = [
    # aritmetica e algebra
    ("aritmetica", "a1", "Quanto fa 17*23 + 144/12?", ["403"]),
    ("aritmetica", "a2", "Quanto fa 2 elevato alla 15?", ["32768", "32.768"]),
    ("aritmetica", "a3", "Risolvi 3x - 7 = 2x + 5. Quanto vale x?", ["12"]),
    ("aritmetica", "a4", "Qual è il 15% di 240?", ["36"]),
    ("aritmetica", "a5", "Qual è la somma dei numeri interi da 1 a 100?", ["5050", "5.050"]),
    ("aritmetica", "a6", "Qual è il minimo comune multiplo di 12, 18 e 30?", ["180"]),
    ("aritmetica", "a7", "Quanti numeri interi da 1 a 1000 sono divisibili per 3 oppure per 5, ma non per 15?", ["401"]),
    ("aritmetica", "a8", "Qual è la somma delle cifre di 2 elevato alla 20?", ["31"]),
    ("aritmetica", "a9", "Lancio due dadi a sei facce. Qual è la probabilità che la somma sia 8? Scrivila come frazione ridotta.", ["5/36"]),
    ("aritmetica", "a10", "Un prezzo di 80 euro aumenta del 25% e poi diminuisce del 20%. Qual è il prezzo finale in euro?", ["80"]),
    # logica e trabocchetti
    ("logica", "l1", "Sono un maschio e ho 3 fratelli maschi. Ognuno dei miei fratelli ha esattamente 2 sorelle. Quante figlie femmine ci sono nella famiglia?", ["2", "due"]),
    ("logica", "l2", "Tutti i blip sono blop e nessun blop è un blup. Un blip può essere un blup? Rispondi sì o no.", ["no"]),
    ("logica", "l3", "Anna è più alta di Bea e Bea è più alta di Carla. Chi è la più bassa delle tre?", ["carla"]),
    ("logica", "l4", "Se 5 macchine producono 5 pezzi in 5 minuti, quanti minuti servono a 100 macchine per produrre 100 pezzi?", ["5", "cinque"]),
    ("logica", "l5", "Una mazza e una palla costano in tutto 1,10 euro. La mazza costa 1 euro più della palla. Quanti centesimi costa la palla?", ["5", "cinque"]),
    ("logica", "l6", "In una corsa superi il concorrente che è secondo. In che posizione sei adesso? Rispondi con un numero.", ["2", "secondo"]),
    ("logica", "l7", "Un lago ha una macchia di ninfee che raddoppia ogni giorno e copre il lago in 48 giorni. In quanti giorni copre metà lago?", ["47"]),
    ("logica", "l8", "Ho due monete per un totale di 30 centesimi e una delle due non è da 5 centesimi. Quali sono le due monete? Rispondi con i due valori in centesimi separati da una virgola.", ["20, 10", "10, 20", "20,10", "10,20"]),
    ("logica", "l9", "Se oggi è mercoledì, che giorno della settimana sarà tra 100 giorni?", ["venerdì", "venerdi"]),
    ("logica", "l10", "Qual è il prossimo numero della sequenza 2, 6, 12, 20, 30, ...?", ["42"]),
    # lettura di codice
    ("codice", "c1", "Che cosa stampa questo codice Python? print(sum(i*i for i in range(1, 6) if i % 2))", ["35"]),
    ("codice", "c2", "Che cosa restituisce in Python len(set('mississippi'))?", ["4", "quattro"]),
    ("codice", "c3", "Che cosa stampa questo codice Python? x = [1, 2, 3]; y = x; y += [4]; print(len(x))", ["4"]),
    ("codice", "c4", "Che cosa stampa questo codice Python? print(''.join(sorted(set('banana'), key=lambda c: -'banana'.count(c))))", ["anb"]),
    ("codice", "c5", "Che cosa stampa questo codice Python? print([i for i in range(10)][2:8:3])", ["[2, 5]", "[2,5]"]),
    ("codice", "c6", "Che cosa stampa questo codice Python? d = {}; d.setdefault('a', []).append(1); d.setdefault('a', []).append(2); print(d['a'])", ["[1, 2]", "[1,2]"]),
    ("codice", "c7", "Che cosa stampa questo codice JavaScript? console.log([1, 2, 3].map(x => x * 2).filter(x => x > 2).length)", ["2"]),
    ("codice", "c8", "Che cosa stampa questo codice Python? print(int('101', 2) + int('ff', 16))", ["260"]),
    ("codice", "c9", "Che cosa stampa questo codice Python? def f(n): return n if n < 2 else f(n-1) + f(n-2)\nprint(f(10))", ["55"]),
    ("codice", "c10", "Che cosa stampa questo codice Python? print(sorted([3, 1, 2], reverse=True)[0] * 'ab'.count('b'))", ["3"]),
    # conoscenza
    ("conoscenza", "k1", "In che anno è caduto il muro di Berlino?", ["1989"]),
    ("conoscenza", "k2", "Qual è il simbolo chimico dell'oro?", ["au"]),
    ("conoscenza", "k3", "Qual è il pianeta più grande del sistema solare?", ["giove"]),
    ("conoscenza", "k4", "Chi ha scritto 'I promessi sposi'?", ["manzoni"]),
    ("conoscenza", "k5", "Qual è la capitale dell'Australia?", ["canberra"]),
    ("conoscenza", "k6", "Quanti cromosomi ha normalmente una cellula umana somatica?", ["46"]),
    ("conoscenza", "k7", "In che anno è iniziata la Rivoluzione francese?", ["1789"]),
    ("conoscenza", "k8", "Qual è la velocità della luce nel vuoto, in chilometri al secondo, arrotondata alle migliaia?", ["300000", "300.000", "300 000"]),
    # lettere e stringhe
    ("lettere", "s1", "Quante volte compare la lettera r nella parola 'ferrovieri'?", ["3", "tre"]),
    ("lettere", "s2", "Scrivi la parola 'algoritmo' al contrario, lettera per lettera.", ["omtirogla"]),
    ("lettere", "s3", "Quante lettere ha la parola 'precipitevolissimevolmente'?", ["26"]),
    ("lettere", "s4", "Qual è la terza lettera della parola 'Mediterraneo'?", ["d"]),
    ("lettere", "s5", "Quante vocali ci sono nella parola 'aiuola'?", ["5", "cinque"]),
    ("lettere", "s6", "Scrivi in ordine alfabetico le parole: pera, mela, banana, kiwi. Rispondi con le parole separate da virgola.", ["banana, kiwi, mela, pera", "banana,kiwi,mela,pera"]),
    # unità, date, tempo
    ("unita", "u1", "Quanti secondi ci sono in 2 ore e 15 minuti?", ["8100", "8.100"]),
    ("unita", "u2", "Un treno parte alle 14:35 e arriva alle 17:10 dello stesso giorno. Quanti minuti dura il viaggio?", ["155"]),
    ("unita", "u3", "Quanti giorni ci sono dal 1 marzo 2024 al 1 marzo 2025 (escluso il giorno di arrivo)?", ["365"]),
    ("unita", "u4", "Un orologio analogico segna le 3:15. Qual è l'angolo minore, in gradi, tra la lancetta delle ore e quella dei minuti?", ["7.5", "7,5"]),
    ("unita", "u5", "Quanti grammi sono 2,5 chilogrammi?", ["2500", "2.500"]),
    ("unita", "u6", "Il 2028 è un anno bisestile? Rispondi sì o no.", ["sì", "si"]),
    # istruzioni e formato
    ("istruzioni", "i1", "Rispondi solo con il numero, senza parole: quanto fa 6 per 7?", ["42"]),
    ("istruzioni", "i2", "Scrivi la parola CIAO tutta in minuscolo.", ["ciao"]),
    ("istruzioni", "i3", "Dimmi il colore che si ottiene mescolando blu e giallo, in una parola sola.", ["verde"]),
    ("istruzioni", "i4", "Converti 255 in base 2 e dimmi quante cifre 1 contiene.", ["8", "otto"]),
]

# contesto lungo: un registro con fatti nascosti a profondità diverse
def long_doc(rows=700):
    lines = []
    secrets = {}
    for i in range(rows):
        if i in (70, 210, 350, 490, 630):
            code = f"X{(i * 37) % 997:03d}-{chr(65 + i % 26)}"
            secrets[i] = code
            lines.append(f"Riga {i}: NOTA RISERVATA, la chiave della cassaforte {i // 70} è {code}.")
        else:
            lines.append(f"Riga {i}: il magazzino registra l'arrivo del lotto {i * 7} con codice ART-{i:04d}.")
    return "\n".join(lines), secrets


EXTRA = json.loads(os.environ.get("BENCH_EXTRA", "{}") or "{}")   # parametri di campionamento extra (presence_penalty, dry_multiplier...)
STATS = {"chiamate": 0, "troncate": 0}


def ask(url, msgs, think, max_tokens, temp=0.0):
    body = {"model": "local", "messages": msgs, "temperature": temp, "max_tokens": max_tokens, "stream": False,
            "chat_template_kwargs": {"enable_thinking": think}}
    body.update(EXTRA)
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.loads(r.read())
    msg = d["choices"][0]["message"]
    text = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    if not text.strip() and reasoning:
        text = reasoning   # a reply that ended inside its reasoning: score what it reached
    n = d.get("usage", {}).get("completion_tokens", 0)
    STATS["chiamate"] += 1
    STATS["troncate"] += d["choices"][0].get("finish_reason") == "length"
    return text, n, time.time() - t0, d["choices"][0].get("finish_reason")


SYS = "Rispondi in italiano. Ragiona brevemente se serve, poi termina con una riga nel formato: RISPOSTA: <valore>"
TOOLS_SYS = ("Puoi eseguire codice Python per calcolare o verificare: scrivi un solo blocco ```python ... ``` e fermati; "
             "ti restituirò l'output. Usalo per conti, conteggi di lettere, date e per eseguire il codice delle domande. "
             "Quando sei sicuro, termina con la riga RISPOSTA: <valore>.")


KNOWLEDGE_DIR = None


def run_python(code):
    import subprocess, tempfile
    if KNOWLEDGE_DIR:
        code = f"import sys; sys.path.insert(0, {KNOWLEDGE_DIR!r})\n" + code
    with tempfile.TemporaryDirectory() as d:
        try:
            r = subprocess.run([sys.executable, "-I", "-c", code], cwd=d, capture_output=True, text=True, timeout=15)
            out = (r.stdout + r.stderr)[-1500:]
        except subprocess.TimeoutExpired:
            out = "tempo scaduto (15 s)"
    return out or "(nessun output)"


def esempi_msgs(question, bank, k=2):
    """Few-shot dinamico: i k esempi risolti più simili alla domanda (sovrapposizione di parole), come turni di chat."""
    w = set(re.findall(r"\w+", question.lower()))
    scored = sorted(bank, key=lambda e: -len(w & set(re.findall(r"\w+", e["q"].lower()))))[:k]
    out = []
    for e in scored:
        res = run_python(e["code"]).strip() if "conoscenza" in e["code"] and KNOWLEDGE_DIR else e["out"]
        if "conoscenza" in e["code"] and not KNOWLEDGE_DIR:
            continue
        out += [{"role": "user", "content": e["q"]},
                {"role": "assistant", "content": "```python\n" + e["code"] + "\n```"},
                {"role": "user", "content": "Output:\n" + res[:900]},
                {"role": "assistant", "content": "RISPOSTA: " + e["ans"]}]
    return out


def solve_with_tools(url, msgs, think, budget, temp=0.0):
    toks = secs = 0
    text = ""
    for _ in range(4):
        t, n, s, fr = ask(url, msgs, think, budget, temp)
        toks += n
        secs += s
        text += t + "\n"
        m = re.search(r"```python\s*(.+?)```", t, re.S)
        if not m:
            break
        # always run the code: a reply that wrote code AND an answer in one go guessed the output
        out = run_python(m.group(1))
        follow = "Output:\n" + out
        if re.search(r"RISPOSTA\s*:", t, re.I):
            follow += "\nQuesto è l'output reale. Se la tua RISPOSTA non coincide, correggila; poi scrivi solo la riga RISPOSTA: <valore>."
        msgs = msgs + [{"role": "assistant", "content": t}, {"role": "user", "content": follow}]
    return text, toks, secs


def extract(text):
    m = re.findall(r"RISPOSTA\s*:\s*(.+)", text, re.I)
    ans = (m[-1] if m else (text.strip().splitlines() or [""])[-1]).strip().lower()
    return re.sub(r"[*_`]+", "", ans).strip().rstrip(".")


def correct(ans, ok):
    a = ans.lower()
    return any(re.search(r"(^|[^0-9a-zà-ù])" + re.escape(o.lower()) + r"($|[^0-9a-zà-ù])", a) for o in ok)


def main():
    label = sys.argv[1]
    url = next((a for a in sys.argv[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    think = ("--think" in sys.argv or "--harness" in sys.argv) and "--no-think" not in sys.argv
    harness = "--harness" in sys.argv
    make_ref = "--ref" in sys.argv
    tools = "--tools" in sys.argv
    sheet = ""
    for a in sys.argv:
        if a.startswith("--cheatsheet="):
            sheet = open(a.split("=", 1)[1]).read().strip()
    sysmsg = SYS + ("\n" + TOOLS_SYS if tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet else "")
    cats = None
    for a in sys.argv:
        if a.startswith("--cats="):
            cats = set(a.split("=", 1)[1].split(","))
    qs = [q for q in Q if not cats or q[0] in cats]
    ref = json.load(open(REF)) if os.path.exists(REF) and not make_ref else {}
    newref = {}
    per = collections.defaultdict(lambda: [0, 0])
    fid = []
    toks = secs = 0
    budget = 2400 if think else 600
    for cat, name, q, ok in qs:
        msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": q}]
        if tools and not harness:
            text, n, s = solve_with_tools(url, msgs, think, budget)
            ans = extract(text)
            toks += n
            secs += s
        elif harness:
            votes = collections.Counter()
            texts = []
            for k in range(3):
                if tools:   # harness + tools: each sample may run Python
                    t, n, s = solve_with_tools(url, msgs, think, budget, 0.0 if k == 0 else 0.6)
                    fr = None
                else:
                    t, n, s, fr = ask(url, msgs, think, budget, 0.0 if k == 0 else 0.6)
                if fr == "length":   # recovery: the answer was cut, ask for the final line only
                    msgs2 = msgs + [{"role": "assistant", "content": t[-3000:]},
                                    {"role": "user", "content": "Concludi ora: scrivi solo la riga RISPOSTA: <valore>."}]
                    t2, n2, s2, _ = ask(url, msgs2, False, 60)
                    t, n, s = t + "\n" + t2, n + n2, s + s2
                votes[extract(t)] += 1
                texts.append(t)
                toks += n
                secs += s
            ans = votes.most_common(1)[0][0]
            text = texts[0]
        else:
            text, n, s, fr = ask(url, msgs, think, budget)
            ans = extract(text)
            toks += n
            secs += s
        right = correct(ans, ok)
        per[cat][0] += right
        per[cat][1] += 1
        if make_ref:
            newref[name] = text
        elif name in ref and not think:
            a, b = ref[name], text
            k = 0
            while k < min(len(a), len(b)) and a[k] == b[k]:
                k += 1
            fid.append(k / max(1, len(a)))
        row = {"label": label, "cat": cat, "q": name, "ok": right, "answer": ans[:80], "think": think, "harness": harness,
               "tools": tools, "cheatsheet": bool(sheet)}
        print(json.dumps(row, ensure_ascii=False), flush=True)
        with open(OUT, "a") as f:
            f.write(json.dumps({**row, "text": text[-300:]}, ensure_ascii=False) + "\n")
    # long context: the same document, five depths, prefix reuse after the first
    doc, secrets = long_doc()
    if not cats or "contesto" in cats:
        for i, code in secrets.items():
            msgs = [{"role": "system", "content": SYS},
                    {"role": "user", "content": f"Ecco un registro.\n\n{doc}\n\nQual è la chiave della cassaforte {i // 70}?"}]
            text, n, s, fr = ask(url, msgs, False, 120)
            right = code.lower() in text.lower()
            per["contesto"][0] += right
            per["contesto"][1] += 1
            toks += n
            secs += s
            row = {"label": label, "cat": "contesto", "q": f"profondita-{i}", "ok": right, "answer": extract(text)[:40], "s": round(s, 1)}
            print(json.dumps(row, ensure_ascii=False), flush=True)
            with open(OUT, "a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if make_ref:
        json.dump(newref, open(REF, "w"), ensure_ascii=False, indent=0)
    tot_ok = sum(v[0] for v in per.values())
    tot = sum(v[1] for v in per.values())
    summary = {"label": label, "summary": True, "totale_pct": round(100 * tot_ok / max(1, tot), 1), "corrette": f"{tot_ok}/{tot}",
               "per_categoria_pct": {c: round(100 * v[0] / v[1], 1) for c, v in sorted(per.items())},
               "fedelta_pct": round(100 * sum(fid) / len(fid), 1) if fid else None,
               "token": toks, "secondi": round(secs, 1), "think": think, "harness": harness,
               "tools": tools, "cheatsheet": bool(sheet)}
    print(json.dumps(summary, ensure_ascii=False))
    with open(OUT, "a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
