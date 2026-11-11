# Riepilogo notte 10→11 novembre 2026 (Windows, RTX 3060 12 GB)

Tutti i numeri sono in `risultati.jsonl` e in `results/windows/`; questo file serve a leggere la notte in due minuti. Test fermati alle 07:52, coda svuotata.

## 1. Cosa è stato testato stanotte
| ora | test | durata | risultato |
|---|---|---:|---|
| 02:11 | **A1-35B Q4 duro + agente** | 12,4 min | **duro 89,5**, **agente 100,0 (12/12)** |
| 02:37 | **A1-35B Q4 omp** (6 compiti) | 12 min | **5/6** (83,3%), `dati_ordini` 0 |
| 03:05 | **AREX-Turbo 4B omp** (ripetizione) | 22 min | **4/6** (66,7%), parziale 93,3% |
| 03:28 | **A1-4B omp** | 10,6 min | **3/6** (50%), parziale 78,1% |
| 03:38 | **Nemotron E4B omp** | ~10 min | **2/6** (33,3%), parziale 47,0% |
| 03:49 | **Qwen3.5-9B Kimi duro + agente** | ~8 min | **fallito**: server chiuso (connection reset/refused) |
| 03:57 | **Qwen3.5-9B Kimi omp** | ~10 min | **2/6** (33,3%), parziale 63,7% |
| 04:31 | **AREX 4B, 128K** | 4,5 min | **3/3 aghi**, prefill **1119,6 t/s**, decode **30,0 t/s** |
| 04:34 | **E4B, 128K** | 3 min | **3/3**, prefill 1426,1, decode 19,1 |
| 04:36 | **A1-4B omp** (seconda corsa) | ~10 min | **4/6** (66,7%), parziale 94,8% |
| 04:46 | **Qwen9B, 128K** | 4 min | **3/3**, prefill 888,8, decode 25,2 |
| 04:48 | **AREX 4B, 64K** | 2,5 min | **2/2**, prefill 1886,7, decode **42,0** |
| 04:50 | **E4B, 64K** | 2 min | **2/2**, prefill 2551,2, decode 29,1 |

Fatti prima (sera 10/11): A1 256K q4 **5/5** (prefill 264,4 ub1024, decode 11,8); AREX 256K **0/5** (degenera); TBQ3 256K **19 t/s** (bocciato); 1M **thrashing** (59% in 56 min, 22,7 t/s).

## 2. Intelligenza (stessi benchmark)
| modello | duro | agente | omp pieno | t/s | note |
|---|---:|---:|---:|---:|---|
| **A1-35B Q4** | **89,5** | **100 (12/12)** | **5/6** | 34-45 | il più intelligente; `dati_ordini` è il buco |
| E4B | 78,9 | 50,0 | 2/6 | 62-65 | forte su math/code, **non** è un agente |
| AREX-Turbo 4B | 76,3 | 75,0 | 4-5/6 | 69-76 | base veloce; harness variabile |
| A1-4B | 71,1 | 91,7 | 3-4/6 | 69-73 | agente discontinuo |
| Nemotron 74B | 62,5 (n=4) | 91,7 | **6/6** | 18 | cervello profondo, lento |
| Qwen9B Kimi | — (crash) | — | 2/6 | 49 | 128K buono, agente debole |

## 3. Contesto: dove sta il punto
- **AREX 4B a 128K è il modello veloce per sessioni lunghe**: 3/3 aghi, 30 t/s di decode, 1119 t/s di prefill. A 256K degenera (0/5): **128K è il suo limite**.
- **A1-35B a 256K**: 5/5, ma decode 11,8 t/s. Buono per memoria, lento per chat.
- **64K**: AREX 42 t/s, E4B 29 t/s. Ottimo compromesso.
- **1M**: non praticabile su 12+16 GB (working set in thrash). Serve KV compressa matura (RotorQuant) o un'altra architettura; TurboQuant TBQ3 è troppo lento sul prefill (19 t/s).

## 4. Cosa abbiamo reso migliore (e cosa no)
**Migliorato davvero:**
- **Affidabilità del harness omp**: trovato e corretto il bug del file parziale vecchio che attribuiva i compiti di A1 ad AREX/E4B; watchdog + freschezza + record dal parziale. I record ora sono giusti.
- **Benchmark comune**: duro/agente funzionano su Windows; A1-4B Win/Mac allineati (71,1 vs 73,7).
- **Dashboard**: QI unico, filtri per ogni parametro, ctx, matrice di copertura, mobile.
- **Mappa dei modelli**: ora sappiamo chi è intelligente (A1), chi è veloce (AREX/E4B) e chi è profondo (74B).

**Non migliorato (ancora):**
- **Nessun training**: non ho addestrato né fatto QLoRA/distillazione su A1-35B Q4. L'89,5 è **misurato**, non ottenuto con un boost. Il "boost di intelligenza" è il prossimo passo (QLoRA/EOPD sul 4B con teacher A1/74B).
- **Cascata**: simulata, più lenta del 35B da solo (il 4B entra in loop); serve un router per tipo, non un verifier.
- **1M**: non risolto.

## 5. Idee organizzate per stasera
1. **Router per tipo di compito** (dati/veloci → AREX 4B; specifiche lunghe → A1 35B): misurare qualità e tempo contro A1 da solo. È l'unico "boost" a costo zero.
2. **Training del 4B**: QLoRA 4-bit su AREX con tracce verificate di A1-35B/Nemotron 74B + EOPD; valutare su held-out e harness. Il 35B non entra in training su 12 GB.
3. **128K come standard di sessione**: AREX 128K (veloce) + A1 256K (memoria) + KV pack per non ripagare il prefill.
4. **Dati**: completare duro/agente su Qwen9B (riprovare con server stabile) e sui modelli rimasti; copertura QI al 100%.
5. **Ricerca**: RotorQuant (10,3× KV) per 1M; richiede build MSVC (non installato). Da valutare con calma, non stanotte.
