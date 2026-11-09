"""Benchmark ufficiale: Flash Next contro Agents-A1 potenziato.
Domande NUOVE (seme 2026, mai usate per regolare i modelli né per le memorie di strategie), risposte verificate
calcolandole o eseguendo il codice. 9 categorie, percentuali per categoria, tempi.

Uso: python3 -I bench_ufficiale.py ETICHETTA [URL] [--think] [--tools] [--cheatsheet=FILE] [--votes=3]
Scrive ufficiale-risultati.jsonl.
"""
import collections
import datetime
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench2 import SYS, TOOLS_SYS, ask, correct, extract, run_python, solve_with_tools  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ufficiale-risultati.jsonl")
R = random.Random(2026)


def gen():
    Q = []
    # aritmetica e algebra (10, generate)
    for _ in range(4):
        a, b, c = R.randint(101, 999), R.randint(11, 99), R.randint(3, 19)
        Q.append(("aritmetica", f"Quanto fa {a}*{b} + {c}^3?", [str(a * b + c ** 3)]))
    for _ in range(3):
        x = R.randint(-20, 40); k = R.randint(2, 9); m = R.randint(1, 30)
        Q.append(("aritmetica", f"Risolvi {k}x + {m} = {k * x + m}. Quanto vale x?", [str(x)]))
    for _ in range(3):
        n = R.randint(30, 90)
        Q.append(("aritmetica", f"Qual è la somma dei numeri primi minori di {n}?",
                  [str(sum(p for p in range(2, n) if all(p % d for d in range(2, int(p ** 0.5) + 1))))]))
    # codice (10, generate e verificate eseguendo)
    progs = [
        "x = [3, 1, 4, 1, 5, 9, 2, 6]\nprint(sorted(x)[{a}] + x[-{b}])",
        "s = '{w}'\nprint(s[::{a}].upper()[:{b}])",
        "d = {{}}\nfor c in '{w}': d[c] = d.get(c, 0) + 1\nprint(max(d.values()) * {a})",
        "print(sum(i * i for i in range({a}) if i % {b} == 1))",
        "f = lambda n: 1 if n < 2 else n * f(n - 1)\nprint(f({a}) % {c})",
    ]
    words = ["programmazione", "bicicletta", "gelateria", "cassapanca", "lampadario", "sottomarino"]
    for i in range(10):
        t = progs[i % 5].format(a=R.randint(2, 6), b=R.randint(2, 5), c=R.randint(7, 97), w=R.choice(words))
        out = run_python(t).strip()
        Q.append(("codice", "Che cosa stampa questo codice Python?\n" + t, [out]))
    # lettere (8, generate)
    lw = ["trasportatore", "inaspettatamente", "ipotenusa", "melagrana", "costituzione", "parallelismo", "assassinare", "cocomeraio"]
    for i, w in enumerate(lw):
        if i % 2 == 0:
            ch = sorted(set(w), key=lambda c: -w.count(c))[0]
            Q.append(("lettere", f"Quante volte compare la lettera '{ch}' nella parola '{w}'?", [str(w.count(ch))]))
        else:
            Q.append(("lettere", f"Scrivi la parola '{w}' al contrario, lettera per lettera.", [w[::-1]]))
    # date e unità (8, generate)
    for _ in range(4):
        d1 = datetime.date(2026, R.randint(1, 12), R.randint(1, 28)); d2 = d1 + datetime.timedelta(days=R.randint(30, 500))
        Q.append(("date", f"Quanti giorni ci sono dal {d1.day}/{d1.month}/{d1.year} al {d2.day}/{d2.month}/{d2.year} (escluso il giorno di arrivo)?", [str((d2 - d1).days)]))
    for _ in range(2):
        d = datetime.date(2026, R.randint(1, 12), R.randint(1, 28))
        g = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"][d.weekday()]
        Q.append(("date", f"Che giorno della settimana è il {d.day}/{d.month}/{d.year}? Rispondi con il nome del giorno.", [g, g.replace("ì", "i")]))
    Q.append(("date", "Quanti minuti ci sono in 3 giorni e mezzo?", ["5040", "5.040"]))
    Q.append(("date", "Una gara inizia alle 22:45 e dura 3 ore e 50 minuti. A che ora finisce? Rispondi nel formato HH:MM.", ["02:35", "2:35"]))
    # logica (8, scritte a mano)
    Q += [
        ("logica", "Marco ha il doppio dell'età di Luca. Tra 10 anni Marco avrà 1,5 volte l'età di Luca. Quanti anni ha Luca oggi?", ["10"]),
        ("logica", "In una stanza ci sono 3 interruttori e una lampadina in un'altra stanza. Puoi entrare nella stanza della lampadina una sola volta. Quante volte al minimo devi entrare nella stanza della lampadina per sapere quale interruttore la accende?", ["1", "una"]),
        ("logica", "Se tutti i gatti sono animali e alcuni animali sono neri, è sicuro che almeno un gatto sia nero? Rispondi sì o no.", ["no"]),
        ("logica", "Un orologio guadagna 2 minuti ogni ora. Se lo metti all'ora giusta a mezzogiorno, quanti minuti di anticipo avrà a mezzanotte?", ["24"]),
        ("logica", "Ho dei calzini: 10 neri e 10 bianchi, mescolati al buio. Quanti calzini devo prendere al minimo per essere sicuro di avere un paio dello stesso colore?", ["3", "tre"]),
        ("logica", "Una ragazza ha tanti fratelli quante sorelle; ogni fratello ha il doppio di sorelle rispetto ai fratelli. Quanti figli ci sono in tutto nella famiglia?", ["7", "sette"]),
        ("logica", "Quanti quadrati ci sono in una scacchiera 3x3 contando quadrati di ogni dimensione?", ["14"]),
        ("logica", "Se 3 gatti catturano 3 topi in 3 minuti, quanti gatti servono per catturare 100 topi in 100 minuti?", ["3", "tre"]),
    ]
    # conoscenza (8, scritte a mano)
    Q += [
        ("conoscenza", "Qual è l'elemento chimico con numero atomico 26?", ["ferro", "fe"]),
        ("conoscenza", "Chi ha dipinto 'La nascita di Venere'?", ["botticelli"]),
        ("conoscenza", "Qual è il fiume più lungo d'Italia?", ["po"]),
        ("conoscenza", "In quale anno l'uomo è sbarcato per la prima volta sulla Luna?", ["1969"]),
        ("conoscenza", "Quale organo del corpo umano produce l'insulina?", ["pancreas"]),
        ("conoscenza", "Qual è la formula chimica dell'acqua ossigenata?", ["h2o2"]),
        ("conoscenza", "Quale linguaggio di programmazione ha creato Guido van Rossum?", ["python"]),
        ("conoscenza", "Qual è la capitale del Canada?", ["ottawa"]),
    ]
    # istruzioni e formato (6)
    Q += [
        ("istruzioni", "Rispondi solo con un oggetto JSON con le chiavi \"nome\" (valore \"Anna\") ed \"eta\" (valore 30). Poi la riga RISPOSTA: ok", ["ok"]),
        ("istruzioni", "Scrivi in maiuscolo la terza parola della frase 'il gatto nero dorme sul divano'.", ["nero"]),
        ("istruzioni", "Conta le parole della frase 'oggi piove ma domani forse esce il sole' e rispondi solo con il numero.", ["8", "otto"]),
        ("istruzioni", "Ordina dal più piccolo al più grande: 0,5; 1/3; 0,45; 2/5. Rispondi con i valori separati da punto e virgola, come scritti.", ["1/3; 2/5; 0,45; 0,5", "1/3;2/5;0,45;0,5"]),
        ("istruzioni", "Rispondi con una sola parola: il contrario di 'pesante'.", ["leggero"]),
        ("istruzioni", "Quale numero viene dopo nella sequenza 1, 1, 2, 3, 5, 8, 13? Rispondi solo con il numero.", ["21"]),
    ]
    return Q


PASSAGE = ("Nel 1887 l'ingegnere Lucia Ferri progettò a Torino un ponte sospeso lungo 214 metri. "
           "Il ponte fu inaugurato tre anni dopo, ma nel 1902 una piena del fiume ne danneggiò il pilone nord. "
           "La ricostruzione, guidata dal nipote di Lucia, Andrea Ferri, durò quattro anni e allungò il ponte di 18 metri. "
           "Oggi il ponte è pedonale e viene illuminato ogni sera con 640 lampade a basso consumo.")
COMPR = [("In che anno fu inaugurato il ponte?", ["1890"]), ("Quanto è lungo oggi il ponte, in metri?", ["232"]),
         ("Chi guidò la ricostruzione?", ["andrea"]), ("In che anno finì la ricostruzione, se iniziò subito dopo la piena?", ["1906"])]


def long_doc(rows=1100):
    r = random.Random(77)
    lines, facts = [], {}
    stanze = ["biblioteca", "cantina", "serra", "soffitta", "officina"]
    for i in range(rows):
        if i in (120, 380, 640, 900, 1050):
            k = len(facts)
            facts[k] = (f"C{k}{r.randint(10, 99)}", r.randint(100, 999), stanze[k])
        lines.append(f"Voce {i}: consegna del pacco {i * 13} registrata dal reparto {i % 17}.")
    out = []
    for k, (cass, num, st) in facts.items():
        pass
    # due fatti per chiave, lontani tra loro: la chiave è nel cassetto X; il cassetto X è nella stanza Y
    for k, (cass, num, st) in facts.items():
        a = 120 + 230 * k if 120 + 230 * k < rows else rows - 30 - k
        lines[a] = f"Voce {a}: la chiave numero {num} è custodita nel cassetto {cass}."
        b = (a + 400) % rows
        lines[b] = f"Voce {b}: il cassetto {cass} si trova nella {st}."
    return "\n".join(lines), facts


def main():
    label = sys.argv[1]
    url = next((a for a in sys.argv[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    think, tools = "--think" in sys.argv, "--tools" in sys.argv
    votes = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--votes=")), "1"))
    sheet = ""
    for a in sys.argv:
        if a.startswith("--cheatsheet="):
            sheet = open(a.split("=", 1)[1]).read().strip()
    tsys = TOOLS_SYS
    if "--knowledge" in sys.argv:
        import bench2
        bench2.KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conoscenza")
        tsys += (" Hai anche un pacchetto di conoscenza (Wikipedia): nel blocco Python usa "
                 "`from conoscenza import cerca` e `print(cerca('parole chiave'))` per leggere i passaggi pertinenti prima di "
                 "rispondere a domande di fatti, nomi, date e luoghi.")
    sysmsg = SYS + ("\n" + tsys if tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet else "")
    budget = 2400 if think else 700
    per = collections.defaultdict(lambda: [0, 0])
    toks = secs = 0

    def answer(user, n_votes):
        nonlocal toks, secs
        msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}]
        c = collections.Counter()
        last = ""
        for v in range(n_votes):
            temp = 0.0 if v == 0 else 0.6
            if tools:
                t, n, s = solve_with_tools(url, msgs, think, budget, temp)
            else:
                t, n, s, _ = ask(url, msgs, think, budget, temp)
            toks += n
            secs += s
            c[extract(t)] += 1
            last = last or t
        return c.most_common(1)[0][0], last

    rows = []
    for cat, q, ok in gen():
        ans, text = answer(q, votes)
        if cat == "istruzioni" and "JSON" in q:   # also the JSON itself must parse
            m = re.search(r"\{.*?\}", text, re.S)
            try:
                j = json.loads(m.group(0)) if m else None
                good = bool(j) and j.get("nome") == "Anna" and int(j.get("eta")) == 30
            except Exception:
                good = False
            right = good
        else:
            right = correct(ans, ok)
        per[cat][0] += right
        per[cat][1] += 1
        rows.append({"label": label, "cat": cat, "ok": right, "answer": ans[:60], "q": q[:70]})
    for q, ok in COMPR:
        ans, _ = answer(f"Leggi il testo e rispondi.\n\n{PASSAGE}\n\nDomanda: {q}", votes)
        right = correct(ans, ok)
        per["comprensione"][0] += right
        per["comprensione"][1] += 1
        rows.append({"label": label, "cat": "comprensione", "ok": right, "answer": ans[:60], "q": q})
    doc, facts = long_doc()
    for k, (cass, num, st) in facts.items():
        ans, text = answer(f"Ecco un registro.\n\n{doc}\n\nIn quale stanza si trova la chiave numero {num}? Rispondi con il nome della stanza.", 1)
        right = st in (ans + " " + text[-200:]).lower()
        per["contesto"][0] += right
        per["contesto"][1] += 1
        rows.append({"label": label, "cat": "contesto", "ok": right, "answer": ans[:60], "q": f"chiave {num}"})
    with open(OUT, "a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tot_ok, tot = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    summ = {"label": label, "summary": True, "totale_pct": round(100 * tot_ok / tot, 1), "corrette": f"{tot_ok}/{tot}",
            "per_categoria_pct": {c: round(100 * v[0] / v[1], 1) for c, v in sorted(per.items())},
            "secondi": round(secs, 1), "secondi_per_domanda": round(secs / max(1, tot), 1), "token": toks,
            "think": think, "tools": tools, "cheatsheet": bool(sheet), "votes": votes}
    with open(OUT, "a") as f:
        f.write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
