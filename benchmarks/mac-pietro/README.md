# Benchmark del Mac (Pietro), 4-9 novembre 2026

Gli script usati sul Mac (MacBook Pro M4, 16 GB) per i test registrati in `results/mac/`. Parlano tutti con un server
**OpenAI-compatibile** (llama-server, Strata `serve.server`, LM Studio, ...): URL come argomento, nessun avvio di processi.
Solo libreria standard, tranne `duro.py` (i test di EvalPlus vogliono numpy, variabile `PYV`) e la potatura (`gguf`).

Ogni script scrive `<nome>-risultati.jsonl` accanto a se (ignorato da git): una riga per domanda e un riepilogo finale.

| Script | Cosa misura | Domande | Durata tipica (A1, ~30 t/s) | Usato per |
|---|---|---|---|---|
| `bench2.py` | v2: 8 categorie (aritmetica, codice, conoscenza, contesto, istruzioni, lettere, logica, unita) + fedelta al modello esatto + "harness" opzionale (ragionamento, verifica, voto) | 59 | 4-35 min | Flash Next su Strata (E107-E168) |
| `bench3.py` | variegato: conoscenza, codice con test nascosti, piu passaggi, italiano, buon senso, formato, tabelle, contesto lungo | 76 | 10-35 min | A1 vs Flash Next (V1-V6) |
| `bench4.py` | difficile: conoscenza rara, matematica calcolata in Python, logica, codice con test, output di codice, contesto a 3 passi | 70 | 10-45 min | A1 vs Flash Next (W1-W4, V3) |
| `bench_ufficiale.py` | 9 categorie, domande nuove (seme 2026) mai usate per regolare i modelli | 67 | 5-35 min | confronto ufficiale U1-U16 |
| `duro.py` | set standard con margine: MATH-500 livelli 4-5, AIME 2025, HumanEval+, MBPP+, MMLU-Pro | 59-74 | 15-110 min | ONYX, cervello, armature (S, Q, F, N, Y) |
| `lungo.py` | contesto lungo reale: 5 aghi a 5K-235K token in un registro, domande a 64K/128K/200K/.../max | 5 | 60 min per 240K | 256K su ONYX-224r |
| `agente.py` | agente con chiamate di funzione native: calendario, attivita, note, contatti, email simulate; controlla lo stato finale | 12 | ~2 min | ONYX-224r a 256K (12/12) |
| `a1_cervello.py` | non e un test: proxy che classifica la domanda e sceglie la strategia (`politica-v2.json`) | - | - | +8,5 punti su `duro` |
| `omp_agente.py` | OMP vero (non simulato) sui 6 compiti di `windows-fabbrica/agente_mini.py`: successo, secondi, passi, token, caratteri di pensiero, modelli non locali usati | 6 | 10-25 min | G1-G11 |
| `esplora_mini.py` | 3 compiti di esplorazione di una cartella grande (registro da 24.000 righe, 80 config, 120 moduli): pesa la lettura, non la scrittura; `omp_agente.py --tasks=esplora` | 3 | 4-15 min | E1-E11 |
| `regole-locale.md` | non e un test: le regole del profilo `omp-locale` (comandi mirati, output corti, dati con Python, verifica prima di finire) | - | - | G8-G11, E8-E11 |
| `prune_experts.py`, `prune_imatrix.py` | potatura degli expert stile REAP da conteggi imatrix, e ritaglio dell'imatrix | - | - | ONYX-224r, 192r, 176r |

## Dataset di `duro.py` (non nel repo)
Vanno in `benchmarks/mac-pietro/dati/` come JSON (righe del dataset):
`HuggingFaceH4/MATH-500` → `math500.json`, `MathArena/aime_2025` (o `opencompass/AIME2025`) → `aime2025.json`,
`evalplus/humanevalplus` → `humanevalplus.json`, `evalplus/mbppplus` → `mbppplus.json`, `TIGER-Lab/MMLU-Pro` → `mmlupro.json`.

## Esempi
```bash
python3 -I duro.py ETICHETTA http://127.0.0.1:8080 --sets=math,code,mbpp,mmlu --n=15 --jobs=4
python3 -I bench4.py ETICHETTA http://127.0.0.1:8080
python3 -I lungo.py ETICHETTA http://127.0.0.1:8080 --max=240000
python3 -I agente.py ETICHETTA http://127.0.0.1:8080
python3 -I a1_cervello.py --porta=8090 --llama=http://127.0.0.1:8080 --politica=politica-v2.json
```

## Avvertenze
- I punteggi di suite diverse **non si confrontano**. Con 59 domande ±6 punti sono rumore; con 15 per categoria ±13.
- `bench2/3/4/ufficiale` sono stati scritti per questi due modelli: risposte e test sono nel codice, quindi non sono segreti.
- `duro.py --jobs=4` usa 4 richieste parallele: con slot paralleli llama.cpp non e deterministico anche a temperatura 0.
