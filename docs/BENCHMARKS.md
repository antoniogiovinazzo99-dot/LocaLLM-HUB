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

## Unificazione
Obiettivo: che Motti e Pietro eseguano **lo stesso identico benchmark** e i punteggi siano confrontabili. Piano proposto:

1. **Subito:** `core-speed` per la velocita (fatto). Tutti dichiarano `benchmark.suite` e `version` nei loro file.
2. **Prossimo passo:** estrarre da `fabbrica.py` un runner portabile `benchmarks/core/run.py` che parla solo con un server OpenAI-compatibile (porta e URL come argomenti, nessun avvio di processi), con la Suite S e agente-mini. Il lancio dei server resta alla persona.
3. **Congelare** `core v1`: stessi seed, stessi campioni (niente budget a tempo: o completo o dichiarato `partial`), stessi prompt, temperatura 0. Da quel momento i punteggi `core-v1` sono comparabili, quelli vecchi restano come storia.
4. **Controllo incrociato:** un modello piccolo (es. Agents-A1-4B Q4) eseguito su entrambe le macchine deve dare punteggi uguali entro il rumore: se no, c'e un bug nel runner o nel server.
5. **Riferimento comune:** un modello di riferimento per ogni macchina (Windows: Flash-Next; Mac: da decidere) rieseguito ogni volta che cambia il protocollo.

Chi propone modifiche al protocollo apre una pull request su `docs/BENCHMARKS.md` e su `benchmarks/`, e l'altro la guarda prima del merge.

## Proposta dal Mac (Pietro, 9 novembre 2026): tanti test brevi per tutti, test esaustivi solo sui migliori

Principio: progredire in fretta. Ogni modello nuovo passa da una batteria **breve e varia**; solo i 2-3 migliori per macchina
ricevono i test lunghi. Meglio 10 categorie da 10 domande fisse che 3 categorie da 100.

### Differenze di protocollo trovate eseguendo `core-speed` sul Mac
1. **Ragionamento del template.** Con `--jinja` i modelli Qwen3.5/3.8 (Agents-A1 compreso) ragionano di default e i token di
   ragionamento contano nei t/s. Sul Mac ONYX-224r fa 28,3 t/s su `core-speed` e 37 t/s su risposte brevi senza ragionamento.
   Proposta: `speedtest.py` registra `metrics.thinking` (`on`/`off`) e accetta `--no-think`
   (`chat_template_kwargs: {"enable_thinking": false}`); i confronti si fanno a parita di impostazione.
2. **Il contesto allocato cambia la velocita.** ONYX-240 fa 25,8 t/s a 32K e 16,6 a 128K (memoria GPU al limite). Proposta:
   `-c` obbligatorio negli `engine.args` e misura al contesto che si usa davvero, non al minimo.
3. **Speculative decoding dipende dal testo.** Con DFlash + ngram-mod il ragionamento va a 70 t/s e la storia a 38: la media
   da sola inganna. Tenere sempre `tps_by_type` e `draft_acceptance_pct` (gia nel protocollo) e citare la mediana.
4. **Slot paralleli.** Con `--parallel > 1` llama.cpp non e deterministico anche a temperatura 0: i test di qualita si fanno
   con `--parallel 1`, oppure si dichiara `parallel` nelle note.
5. **Contesto lungo.** Il bug della colonna `lungo` (slot da 8K) e corretto lato Windows; per il livello breve propongo comunque il test di
   [`benchmarks/mac-pietro/lungo.py`](../benchmarks/mac-pietro/lungo.py) (5 fatti a profondita note, `max_tokens=200`,
   prefisso condiviso per riusare la cache), a 32K nel livello breve e a 128K/256K solo nel livello lungo.

### Livello 1: `core-quick` (per ogni modello, obiettivo 15-20 minuti a 30 t/s)
Campioni **fissi** (stesso seme, stesse domande), temperatura 0, `--parallel 1`, niente budget a tempo: o completo o `partial`.

| Parte | Fonte | Domande | Note |
|---|---|---|---|
| matematica | MATH-500 livelli 4-5, risposte numeriche | 10 | gia in Suite S e `mac-duro` |
| gara | AIME 2025 | 5 | margine per i modelli forti |
| codice | HumanEval+ (test EvalPlus) | 10 | esecuzione reale |
| codice semplice | MBPP+ | 5 | |
| programmazione recente | LiveCodeBench, test privati | 5 | gia in Suite S |
| conoscenza | MMLU-Pro, 10 opzioni, stratificato | 14 | una per materia |
| ragionamento | BBH | 10 | gia in Suite S |
| lavori reali | `serio_lavori` (Windows) | 4 | credito parziale |
| agente | 4 compiti di agente-mini + 4 di `mac-agente` (chiamate di funzione) | 8 | test nascosti / stato finale |
| contesto | `lungo.py` a 32K | 5 fatti | |
| velocita | `core-speed` | 8 | gia comune |

Circa 85 domande: a ±10 punti per parte non decide i dettagli, ma scarta in fretta i modelli deboli e mostra **dove** un
modello e debole. Indice: media semplice delle parti (piu leggibile dei pesi), la Suite S resta il riferimento del livello 2.

### Livello 2: `core-full` (solo i 2-3 migliori per macchina)
Suite S completa, agente-mini completo, `lungo` a 128K e 256K su un documento reale, harness reali (Claude Code, OMP,
opencode), armature (sempre con la base sugli stessi esempi), e la **ripetizione** di ogni test (due corse: la differenza
misura il rumore vero).

### Regola di promozione
Un modello passa al livello 2 se nel livello 1 e entro 5 punti dal migliore della sua macchina **e** fa almeno 20 t/s al
contesto d'uso, oppure se introduce una tecnica nuova (drafter, potatura, armatura) da validare.

### Riferimenti e controllo incrociato
- Riferimento Mac: **Qwen3.8 Flash Next Q2_0 su Strata** (98,3% su `mac-bench2`, 17,8 t/s a 256K); modello d'uso quotidiano
  **Agents-A1 ONYX-224r** (256K tutto sulla GPU).
- Controllo incrociato proposto: **Agents-A1-4B Q4** su entrambe le macchine con `core-quick`: punteggi uguali entro il rumore,
  altrimenti c'e un bug nel runner o nel server.

### Prossimo passo concreto
Unire in `benchmarks/core/run.py` le parti di `suite_s.py` (Windows) e di `duro.py` / `agente.py` / `lungo.py` (Mac), che gia
parlano solo con un server OpenAI-compatibile. Il Mac puo scriverlo se la proposta va bene a entrambi.
