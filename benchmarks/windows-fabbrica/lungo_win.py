"""Test di contesto lungo reale: un registro di magazzino con 5 'aghi' a profondità note, domande a 64K/128K/200K/240K token.
Misura richiamo corretto, velocità di lettura del prompt (prefill) e di scrittura. Il prefisso è condiviso, così la cache
riusa la lettura precedente e il costo totale è circa una sola lettura da 240K.
Uso: python3 -I lungo.py ETICHETTA URL [--max=240000]"""
import json, random, sys, time, urllib.request

LAB, URL = sys.argv[1], sys.argv[2]
MAXT = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--max=")), "240000"))
random.seed(7)
AGHI = [(5000, "Il codice segreto del deposito Nord è GIRASOLE-7319.", "codice segreto del deposito Nord", "girasole-7319"),
        (60000, "La responsabile del turno di notte del 14 marzo è Ilaria Fontebasso.", "responsabile del turno di notte del 14 marzo", "fontebasso"),
        (125000, "Il camion targato FX 482 KP trasporta 37 bancali di piastrelle.", "quanti bancali trasporta il camion targato FX 482 KP", "37"),
        (195000, "La chiave della cella frigorifera 9 è custodita nel cassetto blu.", "dove è custodita la chiave della cella frigorifera 9", "blu"),
        (235000, "Il fornitore Verdi Srl ha cambiato IBAN il giorno 3 ottobre.", "in che giorno il fornitore Verdi Srl ha cambiato IBAN", "3 ottobre")]


def post(path, body, timeout=3600):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def riga(i):
    return (f"Registro {i:06d}: lotto ART-{random.randint(1000, 9999)} spostato da scaffale {random.choice('ABCDEFGH')}"
            f"{random.randint(1, 40)} a scaffale {random.choice('ABCDEFGH')}{random.randint(1, 40)}, operatore {random.randint(100, 999)}.\n")


# stima token per riga con il tokenizer del server
campione = "".join(riga(i) for i in range(200))
tpr = len(post("/tokenize", {"content": campione})["tokens"]) / 200
righe, aghi_pos = [], []
for pos_tok, frase, dom, gold in AGHI:
    aghi_pos.append((int(pos_tok / tpr), frase, dom, gold))
n = int(MAXT / tpr)
k = 0
for i in range(n):
    while k < len(aghi_pos) and aghi_pos[k][0] == i:
        righe.append("NOTA: " + aghi_pos[k][1] + "\n"); k += 1
    righe.append(riga(i))
for target in sorted(set(t for t in (64000, 128000, 200000, 300000, 400000, MAXT) if t <= MAXT)):
    nr = int(target / tpr)
    testo = "".join(righe[:nr])
    presenti = [a for a in aghi_pos if a[0] < nr]
    domande = "\n".join(f"{j+1}. {a[2]}?" for j, a in enumerate(presenti))
    msgs = [{"role": "system", "content": "Rispondi solo usando il documento. Una risposta breve per riga, numerata."},
            {"role": "user", "content": "DOCUMENTO:\n" + testo + "\nFINE DOCUMENTO.\n\nDomande:\n" + domande}]
    t0 = time.time()
    try:
        d = post("/v1/chat/completions", {"model": "x", "messages": msgs, "max_tokens": 200, "temperature": 0,
                                           "chat_template_kwargs": {"enable_thinking": False}})
    except Exception as e:
        print(json.dumps({"label": LAB, "target": target, "errore": str(e)[:200]}), flush=True)
        break
    txt = d["choices"][0]["message"]["content"].lower()
    tm = d.get("timings", {})
    ok = sum(1 for a in presenti if a[3] in txt)
    out = {"label": LAB, "target": target, "prompt_tok": d["usage"]["prompt_tokens"], "richiamo": f"{ok}/{len(presenti)}",
           "prefill_tps": round(tm.get("prompt_per_second", 0), 1), "prefill_nuovi": tm.get("prompt_n"),
           "decode_tps": round(tm.get("predicted_per_second", 0), 1), "s": round(time.time() - t0, 1), "risposta": txt[:300]}
    print(json.dumps(out, ensure_ascii=False), flush=True)
    with open(r"C:\Users\motti\Desktop\claude sept 2026\LocaLLM-HUB\benchmarks\windows-fabbrica\lungo-risultati.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")
