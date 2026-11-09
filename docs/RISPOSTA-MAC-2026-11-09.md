# Risposta del Mac all'allineamento del 9 novembre (sezione 6)

Scritto dal lato Mac (Pietro + il suo agente) dopo aver letto `ALLINEAMENTO-2026-11-09.md`.

## 1. Repo aggiornato
Fatto (`git pull --rebase`).

## 2. ONYX-224r: ricetta, non file
La quantizzazione sorgente `el4/Agents-A1-ONYX-GGUF` **non dichiara una licenza** (Agents-A1 di InternScience e Apache-2.0):
per prudenza non ripubblichiamo il file. Ricetta completa e riproducibile in
[`benchmarks/mac-pietro/onyx/RICETTA.md`](../benchmarks/mac-pietro/onyx/RICETTA.md) (potatura 256→224, imatrix ritagliato,
10 strati riquantizzati, `tipi-onyx224r.txt`, sha256 atteso). Gli imatrix (statistiche nostre) sono nella release
[`onyx-224r-ricetta`](https://github.com/mtom123/LocaLLM-HUB/releases/tag/onyx-224r-ricetta).

## 3. Ricetta DFlash + ngram-mod
[`benchmarks/mac-pietro/RICETTA-DFLASH-NGRAM.md`](../benchmarks/mac-pietro/RICETTA-DFLASH-NGRAM.md). In breve: llama.cpp
**b12038**, `--spec-type draft-dflash,ngram-mod`, `-ngld 99`, `--spec-draft-n-max` non impostato (default 3), ngram-mod ai
default (48/64/24), drafter `Anbeeld/Qwen3.5-35B-A3B-DFlash-GGUF` Q4_K_M (sha256 nel file), `-c 65536`.
Il vostro `--spec-type draft-dflash,ngram-mod` con quel drafter e esattamente il nostro.
**Attenzione:** sul Mac la build piu nuova **b12223 e piu lenta** di b12038 su ONYX-224r (`2026-11-09-llama-cpp-b12223-vs-b12038`).

## 4. Controllo incrociato su Agents-A1-4B Q4_K_M
| Misura | Mac | File |
|---|---|---|
| core-speed | 26,4 t/s | `2026-11-09-agents-a1-4b-q4_k_m-controllo-incrociato` |
| `duro --n=8 --jobs=1` | 73,7% (28/38): math 75, code 75, mbpp 62,5, mmlu 78,6 | `2026-11-09-agents-a1-4b-q4_k_m-duro` |
| `agente.py` | 75% (9/12), 13,8 s per compito | `2026-11-09-agents-a1-4b-q4_k_m-agente` |

**Trappola trovata grazie al controllo** (controllate anche voi): `duro.py` esegue i test di HumanEval+/MBPP+ con
`python -I`, che ignora i pacchetti installati per l'utente. Se numpy e solo li, **codice e MBPP valgono 0%** senza nessun
errore visibile. Ora `duro.py` si ferma con un messaggio; usate `PYV=<python con numpy>` se serve.
Sul Mac il 4B denso **non e piu veloce** del 35B-A3B (26 contro 28 t/s): la banda di memoria del M4 base (~120 GB/s) conta
piu dei parametri attivi.

## 5. projects.json e queue.json
Aggiornati con `platform: mac`, compreso cio che non ha funzionato. Il sito ora mostra "Windows" o "Mac" accanto a ogni voce
della coda (piccola modifica in `assets/app.js`).

## 6. Opinioni
- **ONYX a 192 expert per 12 GB:** sconsigliato. 192 copre il 94,5% dell'uso (strato peggiore 86%) e a 176 il modello crolla
  (18,6% su `duro`). Meglio ONYX-224r con meno contesto (64K su 12 GB).
- **KV q4_0:** il costo non e misurato con un confronto diretto (tutti i nostri test ONYX usano q4_0); a 256K ritrova 5/5 fatti.
- **Cervello davanti a un agente:** passa intatte le richieste con strumenti, quindi oggi non cambia nulla. Ma la domanda giusta
  e un'altra, vedi sotto.

## Novita: perche un agente locale e lento, e cosa aiuta (misurato oggi)
Un compito reale con OMP + ONYX (analisi dello spazio disco) ha richiesto **45 minuti** contro meno di uno di Claude.
Analisi della sessione: 63 passi, uno strumento per passo, ragionamento a ogni passo, e **23 minuti per leggere tre output
di comandi da 22.000 token** a 90-135K di contesto (circa 50 t/s di lettura).
Poi i 6 compiti di agente-mini guidati da OMP vero (`benchmarks/mac-pietro/omp_agente.py`, file `2026-11-09-omp-agente-mini-*`):

| Configurazione | Tempo 6 compiti | Pieni | Parziale |
|---|---|---|---|
| Base (256K, ragionamento attivo) | 1334 s | 5/6 | 83% |
| 256K, ragionamento spento | 1650 s | 5/6 | 83% (2 cicli) |
| Veloce 64K DFlash, ragionamento spento | 982 s | 4/6 | 95% (1 ciclo) |
| Veloce, ragionamento max 1024 token | 1380 s | 4/6 | 96% |
| **Veloce + ragionamento spento + DRY 0,5 + profilo omp-locale** | **965 s** | **5/6** | **97%** |

Lezioni: `--thinking=off` di OMP non spegne il ragionamento su llama.cpp (serve `--reasoning off` sul server); senza
ragionamento A1 entra in cicli di ripetizione, che il campionatore DRY leggero (`--dry-multiplier 0.5 --dry-allowed-length 4`)
ha eliminato; nei compiti di codice il tempo va quasi tutto nella **scrittura** (24-26 t/s), nei compiti di esplorazione nella
**lettura** di output lunghi: per questo il profilo omp-locale limita gli output dei comandi a 4+4 KB e 120 righe.
n=6 e una sola corsa: il -28% va confermato (in coda la ripetizione).
