"""Benchmark 4 (difficile): bench3 era troppo facile (94,7% già senza aiuti). Domande più dure e varie:
conoscenza meno comune, matematica/combinatoria (risposte calcolate in Python), logica, codice algoritmico con test
nascosti, previsione dell'output di codice insidioso, contesto lungo a TRE passaggi con distrattori.
Uso come bench3: python3 -I bench4.py ETICHETTA [URL] [--tools] [--knowledge] [--cheatsheet=F] [--votes=N] [--esempi=F]
Scrive bench4-risultati.jsonl con l'elenco degli errori."""
import unicodedata, collections, json, math, os, re, subprocess, sys, itertools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench2  # noqa: E402
from bench2 import SYS, TOOLS_SYS, ask, correct, extract  # noqa: E402
import bench3  # noqa: E402
OUT = os.path.join(HERE, "bench4-risultati.jsonl")

K = [("In che anno fu firmata la Pace di Vestfalia?", ["1648"]), ("Qual è la capitale del Kazakistan?", ["astana"]),
     ("Chi ha scritto 'Il Gattopardo'?", ["lampedusa"]), ("Qual è il numero atomico dell'oro?", ["79"]),
     ("Chi ha diretto il film 'La dolce vita'?", ["fellini"]), ("Quale fiume attraversa Budapest?", ["danubio"]),
     ("In che anno fu fondata l'ONU?", ["1945"]), ("Chi ha formulato il principio di indeterminazione in meccanica quantistica?", ["heisenberg"]),
     ("Qual è la capitale del Canada?", ["ottawa"]), ("Chi compose l'opera 'Il barbiere di Siviglia' del 1816?", ["rossini"]),
     ("Chi fu il primo presidente della Repubblica Italiana (capo provvisorio dello Stato dal 1946)?", ["de nicola"]),
     ("Quale enzima della saliva inizia la digestione dell'amido?", ["amilasi", "ptialina"]),
     ("In che anno si combatté la battaglia di Waterloo?", ["1815"]), ("Chi ha scritto 'Cent'anni di solitudine'?", ["márquez", "marquez"]),
     ("Qual è la montagna più alta dell'Africa?", ["kilimangiaro", "kilimanjaro"]), ("Quale linguaggio di programmazione ha creato Guido van Rossum?", ["python"]),
     ("Qual è la capitale della Nuova Zelanda?", ["wellington"]), ("Chi dipinse 'La nascita di Venere'?", ["botticelli"]),
     ("In che anno è entrata in vigore la Costituzione italiana?", ["1948"]), ("Qual è la valuta ufficiale della Svizzera?", ["franco", "franchi"]),
     ("Quale stretto separa la Sicilia dalla Calabria?", ["messina"]), ("Qual è l'unità di misura SI della capacità elettrica?", ["farad"]),
     ("Chi ha scritto 'Le città invisibili'?", ["calvino"]), ("In quale città si trova il Museo del Prado?", ["madrid"]),
     ("Qual è la formula chimica dell'ozono?", ["o3"]), ("Chi è l'autore della 'Critica della ragion pura'?", ["kant"]),
     ("Qual è il capoluogo della Basilicata?", ["potenza"]), ("Quale regione italiana ha per capoluogo Campobasso?", ["molise"]),
     ("Chi ha scoperto la penicillina nel 1928?", ["fleming"]), ("Qual è il secondo elemento più abbondante nella crosta terrestre, dopo l'ossigeno?", ["silicio"])]

def _triangoli(p):
    return sum(1 for a in range(1, p) for b in range(a, p) for c in [p - a - b] if c >= b and a + b > c)
M = [("Quanti numeri interi da 1 a 1000 hanno la somma delle cifre uguale a 10?", sum(1 for n in range(1, 1001) if sum(map(int, str(n))) == 10)),
     ("In quanti modi diversi si possono ordinare le lettere della parola BANANA?", len(set(itertools.permutations("BANANA")))),
     ("Qual è il resto della divisione di 7 elevato a 100 per 13?", pow(7, 100, 13)),
     ("Lanciando 4 dadi, qual è la probabilità di ottenere almeno un 6? Scrivila con 3 decimali.", f"{1 - (5 / 6) ** 4:.3f}"),
     ("Con quanti zeri finisce 100 fattoriale?", 24),
     ("Quanti triangoli non congruenti con lati interi hanno perimetro 12?", _triangoli(12)),
     ("Quanti codici di 4 cifre (da 0000 a 9999) hanno tutte le cifre diverse?", 10 * 9 * 8 * 7),
     ("Qual è il minimo comune multiplo di 84, 90 e 126?", math.lcm(84, 90, 126)),
     ("Qual è la somma di tutti i numeri primi minori di 100?", sum(p for p in range(2, 100) if all(p % d for d in range(2, p)))),
     ("Quanti sottoinsiemi di {1,2,...,10} hanno somma degli elementi pari a 15?", sum(1 for r in range(11) for c in itertools.combinations(range(1, 11), r) if sum(c) == 15))]
M = [(q, [str(a)] + ([str(a).replace(".", ",")] if "." in str(a) else [])) for q, a in M]

L = [("Aldo, Bea e Carlo sono un medico, un pittore e un cuoco (uno ciascuno). Aldo non è il medico. Bea non è né il pittore né il medico. Chi è il medico?", ["carlo"]),
     ("Tutti i blip sono blop e alcuni blop sono blup. Ne segue necessariamente che alcuni blip sono blup? Rispondi sì o no.", ["no"]),
     ("Qual è il numero successivo nella sequenza 2, 6, 12, 20, 30, ...?", ["42"]),
     ("Un padre ha 4 volte l'età del figlio; tra 20 anni avrà il doppio dell'età del figlio. Quanti anni ha il figlio oggi?", ["10"]),
     ("Su un'isola i cavalieri dicono sempre il vero e i furfanti mentono sempre. A dice: 'B è un furfante'. B dice: 'A e io siamo dello stesso tipo'. Che cos'è A? Rispondi cavaliere o furfante.", ["cavaliere"]),
     ("Ho due monete che sommate fanno 30 centesimi e una delle due non è da 10 centesimi. Quali sono le monete? Rispondi con i valori in centesimi separati da virgola, dal più grande.", ["20, 10", "20,10"]),
     ("Una lumaca sale di 3 metri di giorno e scivola giù di 2 metri di notte in un pozzo profondo 10 metri. In quale giorno esce dal pozzo?", ["8", "ottavo"]),
     ("In una gara superi chi è in seconda posizione. In che posizione sei adesso? Rispondi con un numero.", ["2", "seconda", "secondo"])]

CODE = [("Scrivi `lcs(a, b)` che restituisce la lunghezza della più lunga sottosequenza comune tra due stringhe.", "lcs",
         [(("ABCBDAB", "BDCABA"), 4), (("", "abc"), 0), (("abc", "abc"), 3)]),
        ("Scrivi `unisci_intervalli(xs)` che unisce intervalli [a, b] sovrapposti (anche se si toccano) e restituisce la lista ordinata.", "unisci_intervalli",
         [(([[1, 3], [2, 6], [8, 10], [15, 18]],), [[1, 6], [8, 10], [15, 18]]), (([[1, 4], [4, 5]],), [[1, 5]]), (([],), [])]),
        ("Scrivi `isole(g)` che conta le isole di 1 (adiacenza solo orizzontale e verticale) in una griglia di 0 e 1.", "isole",
         [(([[1, 1, 0], [0, 1, 0], [1, 0, 1]],), 3), (([[0]],), 0), (([[1, 0, 1, 0, 1]],), 3)]),
        ("Scrivi `cammino_minimo(g, s, t)` che restituisce il costo del cammino minimo da s a t in un grafo pesato dato come dizionario di dizionari (g[u][v] = peso), o None se non esiste.", "cammino_minimo",
         [(({"a": {"b": 1, "c": 4}, "b": {"c": 2, "d": 5}, "c": {"d": 1}, "d": {}}, "a", "d"), 4), (({"a": {}, "b": {}}, "a", "b"), None)]),
        ("Scrivi `rle(s)` che comprime una stringa con run-length: 'aaabcc' -> 'a3b1c2'.", "rle",
         [(("aaabcc",), "a3b1c2"), (("",), ""), (("z",), "z1")]),
        ("Scrivi `cesare(s, k)` che sposta le lettere a-z e A-Z di k posizioni (con giro), lasciando invariati gli altri caratteri.", "cesare",
         [(("Ciao, Zeta!", 3), "Fldr, Chwd!"), (("abc", -1), "zab")]),
        ("Scrivi `regine(n)` che restituisce il numero di soluzioni del problema delle n regine.", "regine",
         [((4,), 2), ((6,), 4), ((8,), 92)]),
        ("Scrivi `in_base(n, b)` che converte un intero non negativo n nella base b (2-36) con cifre 0-9 e A-Z maiuscole.", "in_base",
         [((255, 16), "FF"), ((0, 2), "0"), ((35, 36), "Z"), ((10, 2), "1010")]),
        ("Scrivi `valuta(e)` che calcola il valore di un'espressione con interi, + - * / e parentesi, rispettando le precedenze (/ è divisione reale).", "valuta",
         [(("2+3*4",), 14), (("(2+3)*4",), 20), (("10/4-1",), 1.5)]),
        ("Scrivi `top_k_frequenti(xs, k)` che restituisce i k elementi più frequenti, a parità di frequenza in ordine crescente.", "top_k_frequenti",
         [(([3, 1, 1, 2, 2, 3, 3], 2), [3, 1]), (([5], 1), [5])])]

OUTQ = ["def f(x, l=[]):\n    l.append(x)\n    return len(l)\nf(1); f(2)\nprint(f(3))",
        "print([i * j for i in range(4) for j in range(i)])",
        "a = [1, 2, 3]\nb = a\nb += [4]\nprint(len(a))",
        "print(sum(x for x in range(20) if x % 3 == 0 and x % 2))",
        "s = 'programmazione'\nprint(s[::3], s.count('m'))",
        "x = 10\ndef g():\n    x = 5\n    return x * 2\nprint(g() + x)",
        "d = {}\nfor w in 'il gatto e il cane e il topo'.split():\n    d[w] = d.get(w, 0) + 1\nprint(max(d, key=d.get), d['e'])",
        "print(int('101', 2) + int('ff', 16) // 5)"]

def _out(code):
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=10).stdout.strip()
OUTQ = [(f"Cosa stampa esattamente questo programma Python?\n```\n{c}\n```", [_out(c).lower()]) for c in OUTQ]

def long_doc3(rows=2600):
    lines = [f"Riga {i}: consegna {i * 13 % 997} al deposito D{i % 31}, firmata dal tecnico T{i % 53}." for i in range(rows)]
    facts = [("Orione", "Bari"), ("Cometa", "Udine"), ("Faro", "Siena"), ("Mirto", "Cagliari")]
    out = []
    for k, (cod, citta) in enumerate(facts):
        a, b, c = 300 + 557 * k, 1100 + 431 * k, 2000 + 137 * k
        g, r = f"squadra S{k + 3}", ["Neri", "Gallo", "Fabbri", "Monti"][k]
        lines[a] = f"Riga {a}: il progetto {cod} è stato assegnato alla {g}."
        lines[b] = f"Riga {b}: la {g} è coordinata dall'ingegnera {r}."
        lines[c] = f"Riga {c}: l'ingegnera {r} ha l'ufficio a {citta}."
        lines[(c + 41) % rows] = f"Riga {(c + 41) % rows}: l'ingegnere {r}i, omonimo quasi, ha l'ufficio a Pavia."  # distrattore
        lines[(a + 77) % rows] = f"Riga {(a + 77) % rows}: il progetto {cod}-bis è stato assegnato alla squadra S{k + 13}."  # distrattore
        out.append((cod, citta))
    return "\n".join(lines), out

def main():
    a_ = sys.argv
    label = a_[1]
    url = next((a for a in a_[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    tools, knowledge = "--tools" in a_, "--knowledge" in a_
    votes = int(next((a.split("=", 1)[1] for a in a_ if a.startswith("--votes=")), "1"))
    sheet = next((open(a.split("=", 1)[1]).read().strip() for a in a_ if a.startswith("--cheatsheet=")), "")
    bank = next((json.load(open(a.split("=", 1)[1])) for a in a_ if a.startswith("--esempi=")), [])
    tsys = TOOLS_SYS
    if knowledge:
        bench2.KNOWLEDGE_DIR = os.path.join(HERE, "conoscenza")
        tsys += (" Hai anche un pacchetto di conoscenza (Wikipedia): nel blocco Python usa `from conoscenza import cerca` e "
                 "`print(cerca('parole chiave'))` per leggere i passaggi pertinenti prima di rispondere a domande di fatti, nomi, date e luoghi.")
    sysmsg = SYS + ("\n" + tsys if tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet else "")
    per, errori = collections.defaultdict(lambda: [0, 0]), []
    st = {"s": 0.0, "t": 0}

    def answer(user, n=votes, budget=1000):
        shots = bench2.esempi_msgs(user, bank) if bank and tools and len(user) < 4000 else []
        msgs = [{"role": "system", "content": sysmsg}] + shots + [{"role": "user", "content": user}]
        c, first = collections.Counter(), ""
        for v in range(n):
            if tools:
                t, k, s = bench2.solve_with_tools(url, msgs, False, budget, 0.0 if v == 0 else 0.6)
            else:
                t, k, s, _ = ask(url, msgs, False, budget, 0.0 if v == 0 else 0.6)
            st["s"] += s; st["t"] += k; c[extract(t)] += 1; first = first or t
        return c.most_common(1)[0][0], first

    def score(cat, ok, q, a):
        per[cat][0] += bool(ok); per[cat][1] += 1
        if not ok: errori.append({"cat": cat, "q": q[-90:], "a": str(a)[:80]})

    for cat, items in (("conoscenza", K), ("matematica", M), ("logica", L), ("output_codice", OUTQ)):
        for q, ok in items:
            a, _ = answer(q); a = unicodedata.normalize("NFKC", a); score(cat, correct(a, ok) or a.strip() == ok[0], q, a)
    for q, fn, tests in CODE:
        _, text = answer(q + " Usa Python; scrivi il codice completo in un blocco ```python```; nella riga RISPOSTA scrivi solo: fatto.", 1, 1500)
        blocks = re.findall(r"```python\s*(.+?)```", text, re.S)
        score("codice", any(bench3.run_tests(b, fn, tests) for b in blocks), q, text[-80:])
    doc, facts = long_doc3()
    for cod, citta in facts:
        nota = ""
        if "--doc-file" in a_ and tools:
            fp = os.path.join(HERE, "documento-lungo.txt")
            open(fp, "w").write(doc)
            nota = (f"\n(Il registro completo è anche nel file {fp}: con Python puoi leggerlo e cercare le righe che contengono una parola, "
                    "per seguire la catena un passo alla volta.)")
        a, text = answer(f"Ecco un registro.\n\n{doc}\n\nIn quale città ha l'ufficio chi coordina la squadra a cui è assegnato il progetto {cod} (non {cod}-bis)? Rispondi con il nome della città.{nota}", 1)
        score("contesto_3passi", citta.lower() in a.lower(), cod, a)
    ok, tot = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    summ = {"label": label, "summary": True, "totale_pct": round(100 * ok / tot, 1), "corrette": f"{ok}/{tot}",
            "per_categoria_pct": {c: round(100 * v[0] / v[1], 1) for c, v in sorted(per.items())},
            "secondi": round(st["s"], 1), "secondi_per_domanda": round(st["s"] / tot, 1), "token": st["t"],
            "tools": tools, "knowledge": knowledge, "cheatsheet": bool(sheet), "votes": votes, "esempi": bool(bank), "errori": errori}
    open(OUT, "a").write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(json.dumps(summ, ensure_ascii=False)[:600])

if __name__ == "__main__":
    main()
