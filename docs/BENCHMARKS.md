# Benchmark

Tre livelli, in ordine di costo. I primi scartano in fretta, gli altri si fanno solo sui finalisti.

## 1. `core-speed` (comune, ~2 minuti)
[`benchmarks/core-speed/prompts.json`](../benchmarks/core-speed/prompts.json) e [`tools/speedtest.py`](../tools/speedtest.py). 4 prompt (codice, storia, ragionamento, json), 300 token, temperatura 0, seed 1 e 2. Misura t/s e, con drafter, l'accettazione. **E l'unico benchmark gia identico tra Windows e Mac.**

## 2. Tiny (Fabbrica Windows, ~10 min)
Dataset tinyBenchmarks (100 domande per materia: MMLU, ARC, GSM8K), 12 problemi di codice, HumanEval, ago in 64K, parole inventate. Veloce ma **saturo**: i modelli forti prendono tutti 90+ e non si distinguono. Rumore ±3 punti. Utile solo per scartare i deboli e per la velocita. I dataset non sono nel repo: si scaricano da Hugging Face (`tinyBenchmarks/tinyMMLU`, `tinyGSM8k`, `tinyAI2_arc`).

## 3. Suite S + agente-mini (Fabbrica Windows, ~25-45 min)
Codice in [`benchmarks/windows-fabbrica/`](../benchmarks/windows-fabbrica/) (`suite_s.py`, `serio_lavori.py`, `agente_mini.py`, runner `fabbrica.py`).

- **Parti:** MATH-500 (campione), BBH, HumanEval+, LiveCodeBench (test privati), 8 **lavori reali** con test nascosti e credito parziale (fattura_bug, durata, secchio, lru_ttl, csv, semver, topo, espressione), contesto lungo (tracciare una variabile in ~1000 righe).
- **Indice d'uso:** media pesata lavori 25, math 15, lcb 15, bbh/hep/lungo/mmlupro 10, mbpp 5. Vuole stimare l'intelligenza *in uso reale*, non il punteggio di una tabella.
- **Budget di tempo:** ogni parte ha una scadenza e, se il modello e lento, valuta un campione casuale. Per questo guarda sempre `suite_s_samples`: una parte con 3 campioni non vale niente.
- **agente-mini:** 6 compiti (bug_prezzi, config_loader, rinomina, paginazione, dati_ordini, rapporto) con strumenti `list_files`, `read_file`, `write_file`, `run_tests`, `run_python`, test nascosti, metrica `agente_mini` = % compiti risolti del tutto. Verifica dell'oracolo: `python agente_mini.py control`.
- **Harness reali:** `harness_reali.py` ha gli adattatori per Claude Code, opencode, omp (hook nel runner dal 9/11, primo giro in coda: servono un server con contesto 64K).
- **Armature:** `armature.py` (voto su 5, programma eseguito PAL, verifica, escalation condizionata, MCQ).

Nota di sicurezza e di onesta: i test dei lavori e di agente-mini sono nel codice, quindi **non sono piu segreti**. Vanno bene per confrontare modelli oggi; se un modello venisse addestrato su questo repo il confronto sarebbe invalido. Non scrivere soluzioni nel repo.

Il codice e ancora cucito su Windows (percorsi, kill dei processi, server Strata/llama.cpp locali). I percorsi personali sono stati sostituiti con `<HOME>`. Per usarlo su Mac vanno cambiati almeno `ROOT`/`LLAMA`, il lancio del server e le funzioni di kill.

## Quanto fidarsi (audit del 9/11/2026, lato Windows)
| Misura | Affidabilita | Perche |
|---|---|---|
| Velocita t/s a un flusso, `core-speed` | **alta** | prompt e seed fissi, 8 misure per config, ripetibile |
| Accettazione del drafter | media | dipende dal tipo di prompt (codice 38% vs json 82% sullo stesso drafter) |
| Tiny (MMLU/ARC/GSM/codice) | **bassa per classificare, ok per scartare** | saturo (forti tutti 90+), rumore +-3, campioni ridotti dal budget |
| Suite S: lavori reali, math, bbh, hep | media | campioni piccoli (`suite_s_samples`), il budget di tempo riduce n sui modelli lenti |
| Suite S: lcb | bassa | 4-8 problemi |
| Suite S: lungo | **nulla finora** | bug del server (slot da 8K), corretto 9/11; da rimisurare |
| agente-mini | media-bassa | 6 compiti: una differenza di 1 compito = 16,7 punti. 83% vs 75% e un compito |
| Harness reali | non ancora misurata | primo giro in coda |
| Armature | bassa | manca la base accanto sugli stessi esempi |

Regole che ne derivano: nessuna conclusione su differenze entro il rumore; per classificare serve la Suite S con n alto e agente reale; i numeri del 9/11 sono "indicativi per scegliere cosa approfondire", non "il modello X batte Y".

## Decisione del 9/11/2026: metro di qualita comune
Per misurare l'intelligenza si usano **`duro.py` + `lungo.py` + `agente.py` di Pietro** (`benchmarks/mac-pietro/`): set pubblici con margine, seed fissi, rumore dichiarato. La Suite S e il tiny di Windows restano solo come storia e per `agente_mini` (compiti di codice con test nascosti) e harness reali. Dettagli e motivi: [`docs/ALLINEAMENTO-2026-11-09.md`](ALLINEAMENTO-2026-11-09.md).

## Unificazione
Obiettivo: che Tommaso e Pietro eseguano **lo stesso identico benchmark** e i punteggi siano confrontabili. Piano proposto:

1. **Subito:** `core-speed` per la velocita (fatto). Tutti dichiarano `benchmark.suite` e `version` nei loro file.
2. **Prossimo passo:** estrarre da `fabbrica.py` un runner portabile `benchmarks/core/run.py` che parla solo con un server OpenAI-compatibile (porta e URL come argomenti, nessun avvio di processi), con la Suite S e agente-mini. Il lancio dei server resta alla persona.
3. **Congelare** `core v1`: stessi seed, stessi campioni (niente budget a tempo: o completo o dichiarato `partial`), stessi prompt, temperatura 0. Da quel momento i punteggi `core-v1` sono comparabili, quelli vecchi restano come storia.
4. **Controllo incrociato:** un modello piccolo (es. Agents-A1-4B Q4) eseguito su entrambe le macchine deve dare punteggi uguali entro il rumore: se no, c'e un bug nel runner o nel server.
5. **Riferimento comune:** un modello di riferimento per ogni macchina (Windows: Flash-Next; Mac: da decidere) rieseguito ogni volta che cambia il protocollo.

Chi propone modifiche al protocollo apre una pull request su `docs/BENCHMARKS.md` e su `benchmarks/`, e l'altro la guarda prima del merge.
