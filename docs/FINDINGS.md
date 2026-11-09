# Cosa sappiamo gia (aggiornato al 9 novembre 2026, lato Windows)

Verificato = misurato con numeri nei file `results/windows/`. Il resto e dichiarato come non verificato.

## Velocita
- **Qwen3.8-27B IQ2_XXS, base: 20,2 t/s** su RTX 3060. Con **DFlash2** (drafter Q4, ctx 8K): **33,0 t/s medi (+63%)**, ma sul codice solo 25,6 perche l'accettazione cala (37,8%). Con IQ2_S, drafter Q8 e ctx 32K la VRAM si riempiva e DFlash2 era *piu lento* (12 vs 20): **un drafter aiuta solo se resta VRAM libera**.
- **DSpine** (Tencent, fork `llama-dspine`): **nessun numero**. Il server del fork si e piantato due volte (connessione chiusa, poi timeout di 2 ore). Il paper dichiara +1,28-1,32x di accettazione rispetto a DFlash; il "1,75x" circolato non e verificato.
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
