"""Benchmark 3 (variegato): conoscenza ampia, scrittura di codice con test nascosti, problemi a più passaggi,
italiano, buon senso, vincoli di formato, ragionamento su tabelle, contesto lungo a più passaggi.
Domande nuove, mai usate per regolare i modelli. Percentuali per categoria.

Uso: python3 -I bench3.py ETICHETTA [URL] [--tools] [--cheatsheet=FILE] [--votes=N] [--knowledge]
     --knowledge: nel Python degli strumenti è disponibile `from conoscenza import cerca` (pacchetto di conoscenza)
Scrive bench3-risultati.jsonl.
"""
import collections
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench2  # noqa: E402
from bench2 import SYS, TOOLS_SYS, ask, correct, extract  # noqa: E402

OUT = os.path.join(HERE, "bench3-risultati.jsonl")

K = [  # conoscenza ampia (30)
    ("Quale pianeta del sistema solare ha il giorno più lungo del suo anno?", ["venere"]),
    ("Qual è il gas più abbondante nell'atmosfera terrestre?", ["azoto"]),
    ("Chi ha formulato le tre leggi del moto?", ["newton"]),
    ("Qual è l'unità di misura della resistenza elettrica nel Sistema Internazionale?", ["ohm"]),
    ("Quanti lati ha un esagono?", ["6", "sei"]),
    ("Qual è la catena montuosa più lunga del mondo sulla terraferma?", ["ande"]),
    ("In quale città si trova la Cappella Sistina?", ["vaticano", "città del vaticano", "roma"]),
    ("Chi ha scritto 'Il nome della rosa'?", ["eco"]),
    ("Qual è la lingua ufficiale del Brasile?", ["portoghese"]),
    ("In che anno è stata proclamata la Repubblica Italiana con il referendum?", ["1946"]),
    ("Qual è il più grande oceano della Terra?", ["pacifico"]),
    ("Chi ha composto 'Le quattro stagioni'?", ["vivaldi"]),
    ("Qual è la capitale della Turchia?", ["ankara"]),
    ("Quale scienziato ha proposto la teoria della relatività generale?", ["einstein"]),
    ("Qual è l'osso più lungo del corpo umano?", ["femore"]),
    ("Qual è il simbolo chimico del sodio?", ["na"]),
    ("In quale anno è iniziata la Prima guerra mondiale?", ["1914"]),
    ("Chi ha dipinto 'Guernica'?", ["picasso"]),
    ("Qual è il deserto caldo più grande del mondo?", ["sahara"]),
    ("Quale protocollo usa di norma la porta 443?", ["https"]),
    ("Chi è considerato il fondatore della psicoanalisi?", ["freud"]),
    ("Qual è la moneta ufficiale del Giappone?", ["yen"]),
    ("Quale organello cellulare produce la maggior parte dell'ATP?", ["mitocondri", "mitocondrio"]),
    ("Qual è il lago più grande d'Italia?", ["garda"]),
    ("Chi ha scritto la 'Divina Commedia'?", ["dante"]),
    ("Qual è il punto di ebollizione dell'acqua a livello del mare, in gradi Celsius?", ["100"]),
    ("In quale continente si trova il Kenya?", ["africa"]),
    ("Quale filosofo greco fu maestro di Aristotele?", ["platone"]),
    ("Qual è il nome del primo satellite artificiale lanciato nello spazio?", ["sputnik"]),
    ("Quale elemento ha il simbolo 'K'?", ["potassio"]),
]

CODE = [  # (richiesta, nome funzione, test come lista di (argomenti, atteso))
    ("Scrivi una funzione Python `palindromo(s)` che restituisce True se la stringa è palindroma ignorando spazi e maiuscole.",
     "palindromo", [(("Anna",), True), (("I topi non avevano nipoti",), True), (("ciao",), False)]),
    ("Scrivi una funzione Python `fib(n)` che restituisce l'n-esimo numero di Fibonacci con fib(0)=0 e fib(1)=1.",
     "fib", [((0,), 0), ((1,), 1), ((10,), 55), ((20,), 6765)]),
    ("Scrivi una funzione Python `conta_vocali(s)` che restituisce quante vocali (a, e, i, o, u, maiuscole o minuscole) ci sono in s.",
     "conta_vocali", [(("Ciao",), 3), (("XYZ",), 0), (("AEIOUaeiou",), 10)]),
    ("Scrivi una funzione Python `primi_fino(n)` che restituisce la lista dei numeri primi minori o uguali a n.",
     "primi_fino", [((10,), [2, 3, 5, 7]), ((2,), [2]), ((1,), [])]),
    ("Scrivi una funzione Python `appiattisci(lista)` che appiattisce una lista di liste annidate a qualsiasi profondità.",
     "appiattisci", [(([1, [2, [3, [4]]]],), [1, 2, 3, 4]), (([],), []), (([[1, 2], 3],), [1, 2, 3])]),
    ("Scrivi una funzione Python `romano(n)` che converte un intero da 1 a 3999 in numero romano.",
     "romano", [((4,), "IV"), ((1994,), "MCMXCIV"), ((3999,), "MMMCMXCIX")]),
    ("Scrivi una funzione Python `anagrammi(a, b)` che restituisce True se le due parole sono anagrammi (ignorando le maiuscole).",
     "anagrammi", [(("Roma", "amor"), True), (("ciao", "cibo"), False)]),
    ("Scrivi una funzione Python `media_mobile(xs, k)` che restituisce la lista delle medie di ogni finestra di k elementi consecutivi.",
     "media_mobile", [(([1, 2, 3, 4], 2), [1.5, 2.5, 3.5]), (([5, 5, 5], 3), [5.0])]),
    ("Scrivi una funzione Python `parentesi_ok(s)` che restituisce True se le parentesi (), [], {} nella stringa sono bilanciate.",
     "parentesi_ok", [(("([]{})",), True), (("([)]",), False), (("((",), False), (("",), True)]),
    ("Scrivi una funzione Python `parole_frequenti(testo, n)` che restituisce le n parole più frequenti (minuscole), a parità ordinate alfabeticamente.",
     "parole_frequenti", [(("a b a c b a", 2), ["a", "b"]), (("x y z", 2), ["x", "y"])]),
]

MULTI = [  # problemi a più passaggi (10)
    ("Un negozio vende penne a 1,20 euro l'una e quaderni a 2,50 euro. Luca compra 7 penne e 4 quaderni e paga con 30 euro. Quanti euro di resto riceve?", ["11.6", "11,6", "11.60", "11,60"]),
    ("Un treno viaggia a 90 km/h per 2 ore e poi a 120 km/h per 1 ora e mezza. Qual è la velocità media sull'intero viaggio in km/h?", ["102.86", "102,86", "102.9", "102,9"]),
    ("Una vasca si riempie in 6 ore con un rubinetto e in 3 ore con un altro. Aperti insieme, in quante ore la riempiono?", ["2", "due"]),
    ("Il 30% degli studenti di una scuola gioca a calcio, il 20% a pallavolo e il 10% a entrambi. Che percentuale non pratica nessuno dei due sport?", ["60", "60%"]),
    ("Un capitale di 1000 euro è investito al 5% annuo con interesse composto. Quanti euro vale dopo 3 anni, arrotondato al centesimo?", ["1157.63", "1157,63", "1157.62", "1157,62"]),
    ("Anna ha il triplo delle figurine di Bruno. Se Anna ne dà 12 a Bruno, ne hanno lo stesso numero. Quante figurine aveva Anna all'inizio?", ["36"]),
    ("Un rettangolo ha perimetro 40 cm e un lato lungo il triplo dell'altro. Qual è la sua area in centimetri quadrati?", ["75"]),
    ("In una classe di 25 alunni la media dei voti è 7. Se si aggiunge un alunno con voto 10, qual è la nuova media arrotondata al centesimo?", ["7.12", "7,12"]),
    ("Un ciclista percorre 12 km in 40 minuti. Mantenendo la stessa velocità, quanti km percorre in 2 ore e mezza?", ["45"]),
    ("Un prodotto costa 80 euro dopo uno sconto del 20%. Qual era il prezzo prima dello sconto, in euro?", ["100"]),
]

ITA = [  # italiano (6)
    ("Qual è il plurale di 'uovo'?", ["uova"]),
    ("Coniuga il verbo 'andare' alla prima persona singolare del passato remoto.", ["andai"]),
    ("Qual è il contrario di 'generoso'?", ["avaro", "egoista", "tirchio"]),
    ("Nella frase 'Marco legge il libro', qual è il complemento oggetto?", ["il libro", "libro"]),
    ("Qual è il femminile di 'attore'?", ["attrice"]),
    ("Quante sillabe ha la parola 'aereo'?", ["4", "quattro"]),
]

SENSO = [  # buon senso (6)
    ("Se metto un cubetto di ghiaccio in un bicchiere d'acqua a 25 gradi, dopo un'ora il ghiaccio sarà più grande, uguale o più piccolo (o sciolto)? Rispondi con una parola.", ["piccolo", "sciolto", "sciolto."]),
    ("Pesa di più un chilo di piume o un chilo di ferro? Rispondi 'piume', 'ferro' o 'uguale'.", ["uguale"]),
    ("Se oggi è il 31 dicembre, che mese sarà domani?", ["gennaio"]),
    ("Un uomo guarda una foto e dice: 'Non ho fratelli né sorelle, ma il padre di quest'uomo è il figlio di mio padre'. Chi è l'uomo nella foto rispetto a lui? Rispondi con una parola.", ["figlio"]),
    ("Se una candela si accorcia di 2 cm ogni ora ed è alta 10 cm, dopo quante ore si consuma del tutto?", ["5", "cinque"]),
    ("Se lanci una moneta equilibrata e esce testa 5 volte di seguito, qual è la probabilità che al lancio successivo esca testa? Scrivila come frazione.", ["1/2"]),
]

FORMAT = [  # vincoli di formato, verificati da codice (6)
    ("Scrivi esattamente tre colori separati da virgola, tutto in minuscolo, nella riga RISPOSTA.",
     lambda a: len([x for x in a.split(",") if x.strip()]) == 3 and a == a.lower()),
    ("Nella riga RISPOSTA scrivi una frase di esattamente 5 parole sul mare.",
     lambda a: len(re.findall(r"[A-Za-zÀ-ù']+", a)) == 5),
    ("Nella riga RISPOSTA scrivi solo un numero intero pari compreso tra 41 e 47.",
     lambda a: a.strip().isdigit() and 41 < int(a) < 47 and int(a) % 2 == 0),
    ("Nella riga RISPOSTA scrivi una parola italiana che inizia per 'z' e finisce per 'o'.",
     lambda a: bool(re.fullmatch(r"z[a-zà-ù]*o", a.strip().lower()))),
    ("Nella riga RISPOSTA scrivi le cifre da 1 a 5 in ordine inverso, separate da trattini.",
     lambda a: a.replace(" ", "") == "5-4-3-2-1"),
    ("Nella riga RISPOSTA scrivi il tuo risultato come oggetto JSON con la chiave \"somma\" e valore 2+2.",
     lambda a: (lambda m: bool(m) and json.loads(m.group(0)).get("somma") == 4)(re.search(r"\{.*\}", a))),
]

TABLE = ("Tabella delle vendite trimestrali (in migliaia di euro):\n"
         "| Regione | T1 | T2 | T3 | T4 |\n|---|---|---|---|---|\n"
         "| Nord | 120 | 135 | 128 | 150 |\n| Centro | 90 | 85 | 110 | 95 |\n| Sud | 70 | 88 | 92 | 101 |\n")
TAB_Q = [("Qual è il totale annuale della regione Centro?", ["380"]),
         ("Quale regione ha avuto la crescita maggiore da T1 a T4? Rispondi con il nome.", ["sud"]),
         ("Qual è la media del T3 tra le tre regioni, arrotondata all'intero?", ["110"]),
         ("In quale trimestre il totale delle tre regioni è stato più alto? Rispondi T1, T2, T3 o T4.", ["t4"])]


def long_doc(rows=2200):
    lines = [f"Voce {i}: spedizione {i * 17} verso il magazzino {i % 23} registrata dall'operatore {i % 41}." for i in range(rows)]
    facts = [("Ferro", "Ravenna", 431), ("Vela", "Trieste", 817), ("Aquila", "Lecce", 1207), ("Nube", "Aosta", 1690)]
    out = []
    for k, (cod, citta, a) in enumerate(facts):
        b = (a + 700) % rows
        lines[a] = f"Voce {a}: il progetto {cod} è affidato al gruppo G{k + 7}."
        lines[b] = f"Voce {b}: il gruppo G{k + 7} lavora nella sede di {citta}."
        out.append((cod, citta))
    return "\n".join(lines), out


def _solo_definizioni(code):
    """Tiene import, funzioni, classi e assegnazioni: toglie le prove d'uso a livello di modulo (print, assert, input)
    che, se sbagliate, farebbero fallire anche una funzione giusta."""
    import ast
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    keep = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign)
    tree.body = [n for n in tree.body if isinstance(n, keep)]
    return ast.unparse(tree)


def run_tests(code, fname, tests):
    code = _solo_definizioni(code)
    harness = code + "\n\nimport json\nres = []\n"
    for args, exp in tests:
        harness += f"try:\n    res.append({fname}(*{args!r}) == {exp!r})\nexcept Exception:\n    res.append(False)\n"
    harness += "print(json.dumps(res))\n"
    with tempfile.TemporaryDirectory() as d:
        try:
            r = subprocess.run([sys.executable, "-I", "-c", harness], cwd=d, capture_output=True, text=True, timeout=10)
            res = json.loads(r.stdout.strip().splitlines()[-1])
            return all(res)
        except Exception:
            return False


def main():
    label = sys.argv[1]
    url = next((a for a in sys.argv[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    tools = "--tools" in sys.argv
    knowledge = "--knowledge" in sys.argv
    votes = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--votes=")), "1"))
    sheet = ""
    for a in sys.argv:
        if a.startswith("--cheatsheet="):
            sheet = open(a.split("=", 1)[1]).read().strip()
    tsys = TOOLS_SYS
    if knowledge:
        tsys += (" Hai anche un pacchetto di conoscenza (Wikipedia): nel blocco Python usa "
                 "`from conoscenza import cerca` e `print(cerca('parole chiave'))` per leggere i passaggi pertinenti prima di "
                 "rispondere a domande di fatti, nomi, date e luoghi.")
        bench2.KNOWLEDGE_DIR = os.path.join(HERE, "conoscenza")
    bank = []
    for a in sys.argv:
        if a.startswith("--esempi="):
            bank = json.load(open(a.split("=", 1)[1]))
    sysmsg = SYS + ("\n" + tsys if tools else "") + ("\n\nStrategie apprese:\n" + sheet if sheet else "")
    per = collections.defaultdict(lambda: [0, 0])
    secs = toks = 0

    def answer(user, n_votes=votes, budget=900):
        nonlocal secs, toks
        shots = bench2.esempi_msgs(user, bank) if bank and len(user) < 4000 else []
        msgs = [{"role": "system", "content": sysmsg}] + shots + [{"role": "user", "content": user}]
        c = collections.Counter()
        first = ""
        for v in range(n_votes):
            temp = 0.0 if v == 0 else 0.6
            if tools:
                t, n, s = bench2.solve_with_tools(url, msgs, False, budget, temp)
            else:
                t, n, s, _ = ask(url, msgs, False, budget, temp)
            secs += s
            toks += n
            c[extract(t)] += 1
            first = first or t
        return c.most_common(1)[0][0], first

    errori = []

    def score(cat, ok, q="", a=""):
        if not ok:
            errori.append({"cat": cat, "q": q[-90:], "a": str(a)[:80]})
        per[cat][0] += ok
        per[cat][1] += 1

    for q, ok in K:
        a, _ = answer(q)
        score("conoscenza", correct(a, ok), q, a)
    for q, fname, tests in CODE:
        msgs_q = q + " Scrivi il codice completo in un blocco ```python```; nella riga RISPOSTA scrivi solo: fatto."
        _, text = answer(msgs_q, 1, 1200)
        blocks = re.findall(r"```python\s*(.+?)```", text, re.S)
        good = any(run_tests(b, fname, tests) for b in reversed(blocks)) if blocks else False
        score("codice", good, q, text[-80:])
    for q, ok in MULTI:
        a, _ = answer(q)
        score("piu_passaggi", correct(a, ok), q, a)
    for q, ok in ITA:
        a, _ = answer(q)
        score("italiano", correct(a, ok), q, a)
    for q, ok in SENSO:
        a, _ = answer(q)
        score("buon_senso", correct(a, ok), q, a)
    for q, check in FORMAT:
        a, _ = answer(q, 1)
        try:
            score("formato", bool(check(a)), q, a)
        except Exception:
            score("formato", False)
    for q, ok in TAB_Q:
        a, _ = answer(TABLE + "\n" + q)
        score("tabelle", correct(a, ok), q, a)
    doc, facts = long_doc()
    for cod, citta in facts:
        nota = ""
        if "--doc-file" in sys.argv and tools:
            fp = os.path.join(HERE, "documento-lungo.txt")
            open(fp, "w").write(doc)
            nota = (f"\n(Il registro completo è anche nel file {fp}: con Python puoi leggerlo e cercare le righe che contengono una parola, "
                    "per seguire la catena un passo alla volta.)")
        a, text = answer(f"Ecco un registro.\n\n{doc}\n\nIn quale città lavora il gruppo a cui è affidato il progetto {cod}? Rispondi con il nome della città.{nota}", 1)
        score("contesto_lungo", citta.lower() in (a + " " + text[-200:]).lower(), cod, a)
    tot_ok, tot = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    summ = {"label": label, "summary": True, "totale_pct": round(100 * tot_ok / tot, 1), "corrette": f"{tot_ok}/{tot}",
            "per_categoria_pct": {c: round(100 * v[0] / v[1], 1) for c, v in sorted(per.items())},
            "secondi": round(secs, 1), "secondi_per_domanda": round(secs / tot, 1), "token": toks,
            "tools": tools, "knowledge": knowledge, "cheatsheet": bool(sheet), "votes": votes, "esempi": bool(bank), "errori": errori}
    with open(OUT, "a") as f:
        f.write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
