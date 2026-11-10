# Cosa sappiamo gia (aggiornato al 9 novembre 2026, lato Windows)

Verificato = misurato con numeri nei file `results/windows/`. Il resto e dichiarato come non verificato.

## Velocita
- **Qwen3.8-27B IQ2_XXS, base: 20,2 t/s** su RTX 3060. Con **DFlash2** (drafter Q4, ctx 8K): **33,0 t/s medi (+63%)**, ma sul codice solo 25,6 perche l'accettazione cala (37,8%). Con IQ2_S, drafter Q8 e ctx 32K la VRAM si riempiva e DFlash2 era *piu lento* (12 vs 20): **un drafter aiuta solo se resta VRAM libera**.
- **DSpine** (Tencent, fork `llama-dspine`): **gira, ma non batte DFlash2.** 27B IQ2_XXS, n_max 7, ctx 4K: 31,4 t/s medi vs 33,0 di DFlash2 e 20,2 della base; accettazione codice 36,8% vs 37,8%. I blocchi precedenti erano memoria piena (n_max 15, ctx 8K, drafter Q8). Il "1,75x" circolato non e verificato.
- **MTP su Ornith35**: piu lento del no-MTP (38,5 vs 43,9 t/s) con accettazione 48%. Su MoE con pochi parametri attivi il guadagno puo essere nullo.
- **Flash-Next con prior 1,5** (Strata): 47-54 t/s contro 31, ma peggiora matematica e agente. Il prior e un compromesso, non un regalo.
- **Agents-A1-4B** a 76,8 t/s (np1) e il piu veloce, ma qualita tiny 77,6.

## Qualita
- **Il tiny e saturo.** Agents-A1-35B IQ2_M faceva 91,2 sul tiny ma **60,6** sulla Suite S, con agente-mini al 50%. Il costo della compressione a 2 bit non si vede sul tiny. Non fidarsi del tiny per scegliere.
- **Agents-A1-35B Q4: indice d'uso 69,1, agente-mini 83%** a 36,6 t/s. **Flash-Next rieseguito alla pari: 68,4 e 83%** a 31,6 t/s. Intelligenza pari al riferimento, non migliore: il breakthrough richiede ancora velocita (drafter/MTP) o piu intelligenza.
- Qwen3.8-27B IQ3 ha qualita tiny 90 ma gira a 1,8-5,6 t/s (non entra in VRAM): inutilizzabile.
- Nemotron 3.5 Bolt 74B (22 GB): tiny 87,8 a 19 t/s, agente 83%, ma serve molta RAM libera.

## Armature (intelligenza extra)
- Sui test tiny **nessuna armatura ha battuto la base**: Agents-A1-4B-arm 72,7 vs 77,6. Le armature servono su test difficili, non saturi.
- Ornith-1.5-9B, matematica 100 domande: voto su 5 98% (10,8 min), PAL 83-86% (0,8 min). **Manca la base senza armatura sugli stessi 100**: non quantificato il guadagno.

## Trappole
- **`lungo` (contesto lungo) = 0 per tutti era un bug del runner, non dei modelli.** Il server aveva 4 slot da 8192 token e il test mandava 41.318 token: errore `exceeds the available context size`, contato come risposta sbagliata. Prima avevo ipotizzato `max_tokens=40`: sbagliato. Corretto con un server a 1 slot da 49K (`a1-35b-q4-lungo-fix`). Conseguenza: **tutti gli indici d'uso della Suite S pubblicati finora hanno 0 su un componente da 10 punti su 100**: valgono per confronti tra modelli, non come punteggio assoluto.
- Il riferimento Flash-Next del primo giro (`op-flashnext-ref-p10`) ha campioni minuscoli (3-12 per parte): usa `op-flashnext-ref-serio2`.
- Con 16 GB di RAM i file sopra ~14 GB paginano dal disco e crollano di velocita.

## Idee non ancora provate
Vedi [`data/ideas.json`](../data/ideas.json) (35 voci). Priorita Windows: drafter/MTP su Agents-A1-35B Q4, cascata 4B -> 35B, knowledge pack (KV precalcolata), corretto test del lungo contesto, harness reali, QLoRA su 4B-9B per un compito stretto.

## Ricerca di partenza
[`docs/RICERCA-WINDOWS-2026-11-08.md`](RICERCA-WINDOWS-2026-11-08.md) (scritta lato Windows; dove un dato non e verificato lo dice).

## Notte 10/11/2026 (in corso, lato Windows)

Velocita su **Agents-A1-35B Q4** (llama.cpp b12141), stesso protocollo core-speed (4 tipi di prompt x 2 seed, 300 token, 1 slot, ctx 8K):

| configurazione | t/s medio | accettazione codice | note |
|---|---:|---:|---|
| base, nessuna speculativa | **36,4** | - | conferma i 36,6 di ieri |
| DFlash, `--spec-draft-n-max` 3 (default) | **44,0 (+21%)** | 68,0% | il drafter Q4 di z-lab funziona anche sul finetune A1 |
| DFlash, n_max 8 | 36,2 | 36,4% | **peggio del default**: l'accettazione crolla |
| DFlash, n_max 15 | 27,0 | 17,5% | da non usare |
| `ngram-mod` da solo, ctx 8K | **fallito** | - | una richiesta si e bloccata (175 token in 150 s) e il test e andato in timeout: sulla build b12141 Windows non e affidabile come sul Mac b12038 |

Guadagno per tipo di prompt con DFlash n3: JSON 56,0 (da 36,9), ragionamento 45,5 (37,1), codice 42,7 (35,4), **storia 31,9 (peggio della base 36,3)**. Come sul Mac, il testo libero e il caso peggiore.

**Non ancora verificato:** la ricetta esatta a 64K (q4_0 KV, b512/ub256), `--n-cpu-moe`, il confronto harness opencode/omp e AREX-Turbo/AREX-2: tutto in coda stanotte. Vedi `C:/Users/motti/llm/fabbrica/NOTTE-2026-11-10-PIANO.md` (fuori dal repo) e i file che arriveranno in `results/windows/`.

### Aggiornamento 10/11 mattina (harness reale, solo omp)

| modello | harness omp | t/s | tempo 6 compiti |
|---|---|---:|---:|
| **Agents-A1-35B Q4** (corsa 1) | **6/6 pieni (100%)** | 37-45 | **5,5 min** |
| Agents-A1-35B Q4 (corsa 2, ripetizione) | 5/6 (83,3%) — sbaglia `dati_ordini` in 29 s | 37-45 | 7,2 min |
| **AREX-Turbo 4B Q4** | **5/6 pieni (83,3%)**, parziale 93,9% — `config_loader` 0,636 | **76** | 7,1 min |

Lezione: **il 35B non e' piu' lento del 4B sui compiti agentici veri.** Il 4B scrive piu' veloce, ma sui compiti difficili entra in cicli (212 s su `config_loader`); il 35B chiude in 66 s. La velocita' in token/s non predice il tempo per compito. `dati_ordini` (conteggio su CSV sporco) e' il punto debole sistematico del 35B; il 4B lo fa bene in 9 s. Un router per tipo di compito li combina.

### MoE cache (PR 30966) — provato, NON funziona su questa macchina
`-cmoe --moe-cache-mib 6000` su A1-35B Q4: **17,3 t/s** contro 47,5 della config senza cache. Causa: i 21 GB di esperti non stanno nei 16 GB di RAM, quindi i "miss" della cache leggono dal disco. Il PR e' ottimo, ma serve RAM >= modello (come il desktop da 128 GB dell'esempio). Da riprovare solo con un modello <= 14 GB (es. A1 IQ3_XXS 13,6 GB).
Nota: la build **b12244** ha anche `--moe-cache-cpu-share`, ma su CUDA Windows e' risultata **~9 t/s** sulla stessa config (b12141: 47,5). Restiamo su b12141.

### Benchmark comune (duro + agente) — ora funziona anche su Windows (10/11 pomeriggio)
`duro.py` falliva su Windows per **WinError 206** (la riga di comando con i test EvalPlus supera i 32 KB), non per numpy. Copia `benchmarks/windows-fabbrica/duro_win.py` (test su file temporaneo) e stessi set di Pietro. Primo confronto **stesso modello, due macchine**:

| modello | Windows duro | Mac duro | Windows agente | Mac agente |
|---|---:|---:|---:|---:|
| Agents-A1-4B Q4_K_M | **71,1** (27/38, n=8) | **73,7** (28/38) | **91,7** (11/12) | **75,0** (9/12) |
| **AREX-Turbo 4B Q4_K_M** | **76,3** (29/38) | non misurato | 75,0 (9/12) | non misurato |

- Sul `duro` la differenza A1-4B Windows/Mac (71,1 vs 73,7) e **dentro il rumore** (n=38): le due macchine sono allineate.
- Sull'`agente` (n=12) il divario 91,7 vs 75 e grande ma con 12 compiti vale ±1 compito ≈ 8 punti: **da ripetere**, non e una conclusione.
- **AREX-Turbo 4B e la base migliore trovata finora**: 76,3 duro, 75 agente, 5/6 su omp, **76 t/s**. Batte A1-4B sul benchmark pubblico ed e 2,9 GB.
- **Nemotron 3.5 Bolt 74B: 6/6 su omp** (tutti i compiti, incluso `dati_ordini` dove A1 fallisce), 18,3 t/s, 19,8 min. E il "cervello profondo" della cascata; il duro e in corso.

Il **QI** della dashboard usa ora il benchmark comune come prima fonte: `duro` (rank 0) → `omp` (1) → suite S (2) → agente (3) → tiny (4), con la fonte scritta accanto. Cosi i modelli misurati sugli stessi set pubblici stanno davanti, e i 100 "omp" non mascherano un duro piu basso.

### GLM-5.3-Flash - non e' "condensabile" qui
BF16 ~700 GB (14 parti da ~50 GB), Q8 ~390 GB, e anche la versione **REAP50** (potata al 50%) e' **72-99 GB**. Non entra in 16+12 GB in nessuna quantizzazione. "Trapiantare il cervello" in un altro modello e' tecnicamente impossibile tra architetture diverse: cio' che si trasferisce e' il **comportamento** (distillazione di tracce), non i pesi. Vedi `docs/RICERCA-2026-11-10-DISTILLAZIONE-4B.md`.


