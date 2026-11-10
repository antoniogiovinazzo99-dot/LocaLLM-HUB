# LocaLLM Hub

Esperimenti e benchmark su **modelli locali**, fatti da due macchine con gli stessi metri di misura:

| | Chi | Macchina |
|---|---|---|
| Windows | Tommaso | RTX 3060 12 GB, 16 GB RAM |
| Mac | Pietro | Mac (Apple Silicon) |

Obiettivo: un modello locale **molto intelligente, veloce (50+ t/s) e con contesto lungo (256K)**, e capire con test onesti cosa funziona davvero: motori, quantizzazioni, drafter/MTP, armature di ragionamento, harness per agenti.

## 👉 [Apri la dashboard condivisa](https://mtom123.github.io/LocaLLM-HUB/)
Esperimenti di Tommaso (Windows) a sinistra, di Pietro (Mac) a destra, classifica per modello e idee da provare. Si aggiorna da sola a ogni push.

## Cosa c'e dentro
```
index.html, assets/        il sito (legge i file JSON, nessuna build)
results/windows/*.json     un esperimento per file (Tommaso)   + index.json generato
results/mac/*.json         un esperimento per file (Pietro)  + index.json generato
templates/                 esempio di file risultato
tools/build.py             valida i risultati e rigenera gli indici
tools/speedtest.py         misura la velocita col protocollo comune e scrive il file risultato
tools/legacy/              importazione della storia dei test Windows
benchmarks/core-speed/     protocollo di velocita identico su tutte le macchine
benchmarks/windows-fabbrica/   Suite S, agente-mini, armature, runner (codice Windows)
data/ideas.json            idee da provare (una per voce)
docs/                      SCHEMA, BENCHMARKS (con piano di unificazione), FINDINGS (cosa sappiamo), ricerca
AGENTS.md                  istruzioni per gli agenti di chi collabora
```

## Aggiungere un test (30 secondi di lavoro)
1. Fai il test (per la velocita: `python tools/speedtest.py ...`, vedi [AGENTS.md](AGENTS.md)).
2. Il risultato e **un solo file JSON** in `results/<tua-piattaforma>/`, formato in [docs/SCHEMA.md](docs/SCHEMA.md).
3. `python tools/build.py` (valida e rigenera l'indice), poi `git add -A && git commit && git push`.

Windows e Mac scrivono in cartelle diverse: **nessun conflitto di merge**.

## Stato attuale (9/11/2026)
- Attenzione: la colonna *lungo contesto* della Suite S era 0 per un bug del runner (corretto, da rimisurare): vedi [FINDINGS](docs/FINDINGS.md) e il capitolo *Quanto fidarsi* di [BENCHMARKS](docs/BENCHMARKS.md#quanto-fidarsi-audit-del-9112026-lato-windows).
- 33 esperimenti Windows registrati: velocita, tiny, Suite S, agente-mini, armature, speculative decoding, 3 fallimenti documentati.
- Intelligenza pari a Flash-Next raggiunta con Agents-A1-35B Q4 (indice d'uso 69,1 vs 68,4), ma ancora alla stessa velocita (~36 t/s): il passo avanti e la velocita.
- Il Mac non ha ancora risultati. Primo passo: `core-speed` su un modello comune.
- Dettagli e trappole gia trovate: [docs/FINDINGS.md](docs/FINDINGS.md).

## Progetti e tecniche
Elenco vivo in [`data/projects.json`](data/projects.json) (tab *Progetti* del sito): Fabbrica, Suite S e agente-mini, Agents-A1, Strata + Flash-Next, decodifica speculativa (MTP, DFlash2, DSpine), armature, agenti reali (opencode, Claude Code, omp), contesto lungo, e idee come Infinity (runtime per agenti concorrenti), Gyro (quantizzazione trellis), knowledge pack, QLoRA. Ognuno aggiunge i suoi: *cosa fa, stato, test collegati, prossimo passo*. Coda dei test: tab *Coda* ([`data/queue.json`](data/queue.json)). Ricerca piu recente: [Infinity, Gyro e Strata](docs/RICERCA-2026-11-09-INFINITY-GYRO.md).

## Benchmark
Tre livelli (velocita comune, tiny, Suite S + agente-mini) e il [piano per unificarli](docs/BENCHMARKS.md#unificazione) cosi che i punteggi siano uguali tra Windows e Mac. Fino ad allora: non confrontare punteggi di suite diverse, dichiara sempre `benchmark.suite`.

## Per gli agenti
Leggi [AGENTS.md](AGENTS.md) prima di fare qualsiasi cosa. Regole d'oro: scrivi solo nella tua cartella, un esperimento per file, registra anche i fallimenti, niente segreti, niente installazioni sul computer dell'utente senza il suo OK.
