"""A1-cervello: proxy compatibile OpenAI davanti a llama-server (Agents-A1) che applica il sistema studiato stanotte.
- Richieste con "tools" (agenti come OMP che gestiscono da soli le chiamate di funzione): inoltrate così come sono.
- Richieste di chat semplici: il decisore (A1 stesso, 6 token) classifica la domanda; la politica per classe sceglie
  strumenti Python eseguiti davvero, voto a più campioni con arresto adattivo, memoria di strategie.
Uso: python3 -I a1_cervello.py [--porta=8090] [--llama=http://127.0.0.1:8080] [--politica=politica.json] [--memoria=FILE]
Poi punta il client a http://127.0.0.1:8090/v1 (modello: qualunque nome).
"""
import collections, json, os, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench2  # noqa: E402
from bench2 import TOOLS_SYS, ask, extract  # noqa: E402
import duro  # noqa: E402

opt = lambda k, d: next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{k}=")), d)
PORTA = int(opt("porta", "8090"))
LLAMA = opt("llama", "http://127.0.0.1:8080")
POL = json.load(open(opt("politica", os.path.join(HERE, "politica-v2.json"))))
_mf = opt("memoria", os.path.join(HERE, "cheatsheet-claude.txt"))
MEM = open(_mf).read().strip() if os.path.exists(_mf) else ""
BASE_SYS = ("Rispondi nella lingua dell'utente, in modo chiaro. Se serve calcolare o verificare usa il Python. "
            "Alla fine della risposta aggiungi una riga RISPOSTA: <risultato in breve>.")
LOG = os.path.join(HERE, "a1-cervello.log")


def inoltra(path, body, handler):
    req = urllib.request.Request(LLAMA + path, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as r:
        handler.send_response(r.status)
        for k, v in r.getheaders():
            if k.lower() in ("content-type", "cache-control"):
                handler.send_header(k, v)
        handler.end_headers()
        while True:
            chunk = r.read(4096)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()


_LOCK = threading.Lock()


def ask_think(conv, budget, temp):
    """Ragionamento con il campionamento consigliato da Qwen (top_p 0,95, top_k 20)."""
    with _LOCK:
        old = dict(bench2.EXTRA)
        bench2.EXTRA.update({"top_p": 0.95, "top_k": 20})
        try:
            return ask(LLAMA, conv, True, budget, temp)
        finally:
            bench2.EXTRA.clear()
            bench2.EXTRA.update(old)


def rispondi(msgs):
    user = next((m["content"] for m in reversed(msgs) if m["role"] == "user" and isinstance(m.get("content"), str)), "")
    classe, _ = duro.classifica(LLAMA, user)
    pol = POL.get(classe, POL.get("ALTRO", {}))
    sys_user = next((m["content"] for m in msgs if m["role"] == "system"), "")
    sysmsg = (sys_user + "\n\n" if sys_user else "") + BASE_SYS + ("\n" + TOOLS_SYS if pol.get("tools") else "") + \
             ("\n\nStrategie apprese:\n" + MEM if pol.get("cheatsheet") else "")
    conv = [{"role": "system", "content": sysmsg}] + [m for m in msgs if m["role"] != "system"]
    votes = pol.get("votes", 1) if classe in ("CALCOLO", "CONOSCENZA") else 1
    c, testi = collections.Counter(), {}
    for v in range(votes):
        temp = 0.0 if v == 0 else 0.7
        if pol.get("think"):
            # ragionamento con budget forcing (s1): nei test finali +5 risolte / -1 su calcolo e conoscenza
            t, _, _, fr = ask_think(conv, pol.get("budget", 2500), temp if v else 0.6)
            if fr == "length":
                m3 = conv[:-1] + [{"role": "user", "content": user + "\n\nI tuoi appunti di ragionamento (interrotti):\n"
                                   + t[-2500:] + "\n\nIl tempo per ragionare è finito. Scrivi la risposta completa e chiara, "
                                   "poi la riga finale RISPOSTA: <risposta>."}]
                t, _, _, _ = ask(LLAMA, m3, False, 800, 0.0)
        elif pol.get("tools"):
            t, _, _ = bench2.solve_with_tools(LLAMA, conv, False, 2000, temp)
        else:
            t, _, _, _ = ask(LLAMA, conv, False, 2000, temp)
        a = extract(t)
        c[a] += 1
        testi.setdefault(a, t)
        if votes > 1 and c.most_common(1)[0][1] > votes // 2:
            break
    best = c.most_common(1)[0][0]
    return testi[best], classe, dict(c)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        try:
            inoltra(self.path, None, self)
        except Exception as e:
            self.send_error(502, str(e))

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not self.path.endswith("/chat/completions"):
            return inoltra(self.path, body, self)
        d = json.loads(body or b"{}")
        if d.get("tools") or any(m.get("role") == "tool" for m in d.get("messages", [])):
            return inoltra(self.path, body, self)      # l'agente esterno gestisce le chiamate di funzione
        t0 = time.time()
        testo, classe, voti = rispondi(d.get("messages", []))
        with open(LOG, "a") as f:
            f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "classe": classe, "voti": voti, "s": round(time.time() - t0, 1)}, ensure_ascii=False) + "\n")
        msg = {"role": "assistant", "content": testo}
        if d.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            ch = {"id": "a1", "object": "chat.completion.chunk", "model": "agents-a1-cervello",
                  "choices": [{"index": 0, "delta": msg, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(ch, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())
            return
        out = {"id": "a1", "object": "chat.completion", "model": "agents-a1-cervello", "created": int(time.time()),
               "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}], "usage": {}}
        data = json.dumps(out, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print(f"A1-cervello su http://127.0.0.1:{PORTA}/v1 -> {LLAMA}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORTA), H).serve_forever()
