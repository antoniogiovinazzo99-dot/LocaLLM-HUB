"""Benchmark AGENTE: gestione del lavoro personale con chiamate di funzione native (calendario, attività, note,
contatti, email simulate). Ogni compito parte da uno stato noto; il punteggio controlla lo STATO FINALE
(e la risposta, quando è una domanda). Oggi = lunedì 9 novembre 2026.
Uso: python3 -I agente.py ETICHETTA [URL] [--votes ignorato] [--sys=FILE]  (+ BENCH_EXTRA per il campionamento)
Scrive agente-risultati.jsonl."""
import copy, datetime, json, os, re, sys, time, urllib.request
HERE = r'C:\Users\motti\Desktop\claude sept 2026\LocaLLM-HUB\benchmarks\mac-pietro'
sys.path.insert(0, HERE)
import bench2  # noqa: E402
OUT = r"C:\Users\motti\Desktop\claude sept 2026\LocaLLM-HUB\benchmarks\windows-fabbrica\agente-risultati.jsonl"
OGGI = datetime.date(2026, 11, 9)

BASE = {
    "events": [
        {"id": 1, "title": "Stand-up team", "date": "2026-11-09", "start": "09:00", "end": "09:30"},
        {"id": 2, "title": "Riunione clienti", "date": "2026-11-09", "start": "13:00", "end": "14:00"},
        {"id": 3, "title": "Palestra", "date": "2026-11-11", "start": "18:30", "end": "19:30"},
        {"id": 4, "title": "Dentista", "date": "2026-11-12", "start": "09:00", "end": "10:00"},
        {"id": 5, "title": "Call fornitori", "date": "2026-11-12", "start": "14:00", "end": "15:30"},
        {"id": 6, "title": "Riunione progetto Alfa", "date": "2026-11-13", "start": "10:00", "end": "12:00"},
        {"id": 7, "title": "Compleanno di Giulia", "date": "2026-11-14", "start": "20:00", "end": "23:00"},
        {"id": 8, "title": "Spesa", "date": "2026-11-14", "start": "10:00", "end": "11:00"},
        {"id": 9, "title": "Lavaggio auto", "date": "2026-11-14", "start": "15:00", "end": "15:30"},
    ],
    "tasks": [
        {"id": 1, "title": "Rinnovare assicurazione", "due": "2026-11-05", "priority": "alta", "done": False},
        {"id": 2, "title": "Rispondere a Bianchi", "due": "2026-11-08", "priority": "media", "done": False},
        {"id": 3, "title": "Preparare slide Alfa", "due": "2026-11-12", "priority": "alta", "done": False},
        {"id": 4, "title": "Comprare regalo Giulia", "due": "2026-11-13", "priority": "alta", "done": False},
        {"id": 5, "title": "Archiviare fatture", "due": "2026-11-20", "priority": "bassa", "done": False},
        {"id": 6, "title": "Prenotare treno", "due": "2026-11-01", "priority": "media", "done": True},
    ],
    "notes": [
        {"title": "Ufficio", "text": "Wifi ufficio: rete Uff-5G, password Girasole!2026. Portineria apre alle 8."},
        {"title": "Trasloco", "text": "Cose da fare per il trasloco:\n- disdire il gas\n- chiamare il trasportatore\n- cambiare indirizzo in banca"},
        {"title": "Compleanni", "text": "Elena: 3 dicembre. Paolo: 21 marzo. Sara: 9 luglio."},
    ],
    "contacts": [
        {"name": "Sara Neri", "email": "sara.neri@example.com"}, {"name": "Paolo Gallo", "email": "paolo.gallo@example.com"},
        {"name": "Chiara Fabbri", "email": "chiara.fabbri@example.com"}, {"name": "Marco Monti", "email": "marco.monti@example.com"},
    ],
    "sent": [],
}

TOOLS = [
    ("list_events", "Elenca gli eventi del calendario tra due date incluse (YYYY-MM-DD).", {"date_from": "string", "date_to": "string"}),
    ("add_event", "Aggiunge un evento. Orari HH:MM.", {"title": "string", "date": "string", "start": "string", "end": "string"}),
    ("delete_event", "Cancella un evento dato il suo id.", {"id": "integer"}),
    ("list_tasks", "Elenca le attività. status: 'aperte', 'fatte' o 'tutte'.", {"status": "string"}),
    ("add_task", "Aggiunge un'attività. priority: alta, media o bassa. due: YYYY-MM-DD.", {"title": "string", "due": "string", "priority": "string"}),
    ("complete_task", "Segna come fatta un'attività dato il suo id.", {"id": "integer"}),
    ("search_notes", "Cerca nelle note (titolo e testo) una parola o frase; restituisce le note trovate.", {"query": "string"}),
    ("get_contact", "Cerca un contatto per nome e restituisce nome ed email.", {"name": "string"}),
    ("send_email", "Invia un'email. to: indirizzo email (uno solo).", {"to": "string", "subject": "string", "body": "string"}),
]
PY_TOOL = ("python", "Esegue codice Python (date, conti, elenchi) e restituisce ciò che stampa. Usa print().", {"code": "string"})
SCHEMA = [{"type": "function", "function": {"name": n, "description": d, "parameters": {
    "type": "object", "properties": {k: {"type": t} for k, t in p.items()}, "required": list(p)}}} for n, d, p in TOOLS]


def call(st, name, a):
    try:
        if name == "python":
            return bench2.run_python(a.get("code", ""))
        if name == "list_events":
            return [e for e in st["events"] if a["date_from"] <= e["date"] <= a["date_to"]]
        if name == "add_event":
            e = {"id": max([x["id"] for x in st["events"]] + [0]) + 1, **{k: a[k] for k in ("title", "date", "start", "end")}}
            st["events"].append(e)
            return {"ok": True, "id": e["id"]}
        if name == "delete_event":
            n0 = len(st["events"]); st["events"] = [e for e in st["events"] if e["id"] != int(a["id"])]
            return {"ok": len(st["events"]) < n0}
        if name == "list_tasks":
            s = a.get("status", "tutte")
            return [t for t in st["tasks"] if s == "tutte" or (s == "aperte") != t["done"]]
        if name == "add_task":
            t = {"id": max(x["id"] for x in st["tasks"]) + 1, "title": a["title"], "due": a["due"], "priority": a["priority"], "done": False}
            st["tasks"].append(t)
            return {"ok": True, "id": t["id"]}
        if name == "complete_task":
            for t in st["tasks"]:
                if t["id"] == int(a["id"]):
                    t["done"] = True; return {"ok": True}
            return {"ok": False, "errore": "id inesistente"}
        if name == "search_notes":
            q = a["query"].lower()
            return [n for n in st["notes"] if any(w in (n["title"] + " " + n["text"]).lower() for w in q.split())] or "nessuna nota"
        if name == "get_contact":
            q = a["name"].lower()
            return [c for c in st["contacts"] if q.split()[0] in c["name"].lower()] or "nessun contatto"
        if name == "send_email":
            st["sent"].append({k: a.get(k, "") for k in ("to", "subject", "body")}); return {"ok": True}
    except Exception as ex:
        return {"errore": f"{type(ex).__name__}: {ex}"}
    return {"errore": "funzione sconosciuta"}


def ev(st, title_part):
    return [e for e in st["events"] if title_part.lower() in e["title"].lower()]


COMPITI = [
    ("Fissa una riunione con Marco domani dalle 15 alle 16, titolo 'Revisione budget'.",
     lambda s, a: any(e["date"] == "2026-11-10" and e["start"] == "15:00" and e["end"] == "16:00" for e in ev(s, "budget"))),
    ("Giovedì ho degli impegni? Se sì, cancella quello delle 9 e lascia gli altri.",
     lambda s, a: not ev(s, "dentista") and bool(ev(s, "fornitori"))),
    ("Segna come fatte tutte le attività aperte con la scadenza già passata.",
     lambda s, a: all(t["done"] == (t["due"] < "2026-11-09" or t["id"] == 6) for t in s["tasks"])),
    ("Trova nelle note la password del wifi dell'ufficio e mandala per email a Sara.",
     lambda s, a: any(m["to"] == "sara.neri@example.com" and "Girasole!2026" in m["body"] for m in s["sent"])),
    ("Aggiungi un'attività ad alta priorità 'Pagare F24' con scadenza il 16 di questo mese.",
     lambda s, a: any("f24" in t["title"].lower() and t["due"] == "2026-11-16" and t["priority"] == "alta" for t in s["tasks"])),
    ("Sposta la palestra di mercoledì a venerdì, stesso orario.",
     lambda s, a: [(e["date"], e["start"], e["end"]) for e in ev(s, "palestra")] == [("2026-11-13", "18:30", "19:30")]),
    ("Quante ore di riunioni (eventi con 'Riunione' nel titolo) ho questa settimana, da lunedì a domenica? Rispondi con il numero.",
     lambda s, a: bool(re.search(r"(^|[^0-9.,])3([.,]0)?($|[^0-9.,])", a))),
    ("Metti 'Pranzo con Luca' oggi alle 13 per un'ora, ma solo se sono libero; altrimenti alle 14 per un'ora.",
     lambda s, a: [(e["date"], e["start"]) for e in ev(s, "luca")] == [("2026-11-09", "14:00")]),
    ("Manda a Paolo e a Chiara un'email con l'elenco delle attività aperte ad alta priorità.",
     lambda s, a: all(any(m["to"] == to and "slide" in m["body"].lower() and "regalo" in m["body"].lower() and "assicurazione" in m["body"].lower()
                          for m in s["sent"]) for to in ("paolo.gallo@example.com", "chiara.fabbri@example.com"))),
    ("Crea un'attività (priorità media, scadenza 30 novembre 2026) per ogni punto della nota sul trasloco.",
     lambda s, a: sum(1 for t in s["tasks"] if t["due"] == "2026-11-30" and t["priority"] == "media"
                      and any(k in t["title"].lower() for k in ("gas", "trasportatore", "banca", "indirizzo"))) == 3),
    ("Quando è il compleanno di Elena (cerca nelle note) e che giorno della settimana cade nel 2026? Rispondi con il giorno della settimana.",
     lambda s, a: "giovedì" in a.lower() or "giovedi" in a.lower()),
    ("Cancella tutti gli eventi di sabato tranne il compleanno.",
     lambda s, a: [e["title"] for e in s["events"] if e["date"] == "2026-11-14"] == ["Compleanno di Giulia"]),
]

SYSA = ("Sei un assistente personale. Oggi è lunedì 9 novembre 2026. Usa le funzioni per leggere e modificare calendario, "
        "attività, note, contatti ed email: prima guarda i dati, poi agisci. Non inventare id o indirizzi: leggili con le funzioni. "
        "Quando hai finito, rispondi brevemente in italiano con il risultato.")


def chat(url, msgs, schema=None):
    body = {"model": "local", "messages": msgs, "tools": schema or SCHEMA, "temperature": 0.0, "max_tokens": 1200,
            "chat_template_kwargs": {"enable_thinking": False}}
    body.update(bench2.EXTRA)
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())


def main():
    label = sys.argv[1]
    url = next((a for a in sys.argv[2:] if a.startswith("http")), "http://127.0.0.1:8080")
    sysf = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--sys=")), "")
    sysmsg = open(sysf).read().strip() if sysf else SYSA
    nudge, usa_py = "--nudge" in sys.argv, "--python" in sys.argv
    schema = SCHEMA + ([{"type": "function", "function": {"name": PY_TOOL[0], "description": PY_TOOL[1], "parameters": {
        "type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}] if usa_py else [])
    if usa_py:
        sysmsg += " Per date, giorni della settimana e conti usa sempre la funzione python, non calcolare a mente."
    ok_n, errs, t0, steps_tot = 0, [], time.time(), 0
    for q, check in COMPITI:
        st = copy.deepcopy(BASE)
        msgs = [{"role": "system", "content": sysmsg}, {"role": "user", "content": q}]
        final = ""
        spinte = 0
        for step in range(12):
            d = chat(url, msgs, schema)
            m = d["choices"][0]["message"]
            calls = m.get("tool_calls") or []
            msgs.append({"role": "assistant", "content": m.get("content") or "", **({"tool_calls": calls} if calls else {})})
            if not calls:
                final = m.get("content") or ""
                # spinta: il modello annuncia un'azione ("cercherò", "procedo") ma non chiama nessuna funzione
                if nudge and spinte < 2 and re.search(r"\b(cercher|controller|proceder|verificher|invier|aggiunger|ora |prima )", final.lower()):
                    spinte += 1
                    msgs.append({"role": "user", "content": "Procedi ora: chiama le funzioni necessarie e completa il compito, poi riassumi il risultato."})
                    continue
                break
            for c in calls:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                res = call(st, c["function"]["name"], args)
                steps_tot += 1
                msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": json.dumps(res, ensure_ascii=False)})
        try:
            good = bool(check(st, final))
        except Exception:
            good = False
        ok_n += good
        if not good:
            errs.append({"q": q[:70], "finale": final[:120]})
        print("ok" if good else "NO", q[:50], flush=True)
    summ = {"label": label, "summary": True, "totale_pct": round(100 * ok_n / len(COMPITI), 1), "corrette": f"{ok_n}/{len(COMPITI)}",
            "secondi_per_compito": round((time.time() - t0) / len(COMPITI), 1), "chiamate_funzione": steps_tot,
            "extra": bench2.EXTRA, "sys": sysf, "nudge": nudge, "python": usa_py, "errori": errs}
    open(OUT, "a", encoding="utf-8").write(json.dumps(summ, ensure_ascii=False) + "\n")
    print(json.dumps(summ, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
