# Allineamento Windows ↔ Mac — 9 novembre 2026 (sera)

Scritto dal lato Windows (Motti + il suo agente). **Pietro e il suo agente: leggete tutto, poi seguite la sezione 6.**

## 1. Cosa abbiamo letto del vostro lavoro
Il lavoro del Mac è molto più avanti del nostro sull'obiettivo comune (modello locale intelligente, veloce, con contesto lungo):
- **Agents-A1 ONYX-224r**: 10,2 GB, 256K di contesto tutto in GPU su M4 da 16 GB, 28,3 t/s, 5/5 aghi a 240K, agente 12/12.
- **DFlash z-lab + ngram-mod** su A1: 51,0 t/s a 64K contro 26,5 della base (accettazione 72,6%). `ngram-mod` da solo: +19% a 256K.
- **Potatura REAP con imatrix calibrato su Wikipedia** (224 expert tornano al 100% di conoscenza) e le prove negative utili: 512K non entra, 176 expert crollano al 18,6%.
- **Armature**: con ONYX nessuna armatura generica batte la base (importante per noi); gli strumenti Python aiutavano solo IQ2_S.
- **Cervello** (instradamento per tipo di domanda): +8,5 punti su ONYX-240.

Il nostro lato (Windows, RTX 3060 12 GB + 16 GB RAM) finora ha prodotto **meno di quanto serviva**: Agents-A1-35B Q4 pareggia Flash-Next (indice 69,1 vs 68,4) alla stessa velocità (~36 t/s); le armature non guadagnano sul tiny; DSpine gira ma non batte DFlash2; il primo giro di agenti reali era invalido (adattatore opencode sbagliato); il test di lungo contesto era rotto (bug del nostro runner). Nessun salto di velocità o di intelligenza. Il vostro `ngram-mod`/DFlash e ONYX sono la strada più concreta e la stiamo riproducendo.

## 2. I benchmark di Pietro sono migliori dei nostri? Confronto onesto
| | Mac (`benchmarks/mac-pietro/`) | Windows (`benchmarks/windows-fabbrica/`) |
|---|---|---|
| Qualità | `duro.py`: **set pubblici con margine** (MATH-500 liv. 4-5, AIME 2025, HumanEval+, MBPP+, MMLU-Pro) → confrontabili con la letteratura, non saturi | tiny (saturo) + Suite S (campioni piccoli per il budget di tempo) |
| Contesto lungo | `lungo.py`: 5 aghi fino a 240K, reale, con prefill misurato | `lungo` della Suite S: 1 campione, era rotto |
| Agente | `agente.py`: 12 compiti con **chiamate di funzione native**, stato finale controllato; e OMP reale | `agente_mini`: 6 compiti di **codice** con test nascosti (utile per l'uso da programmatore); harness reali (opencode/Claude Code) in corso |
| Rigore | seed fissi, dichiara il rumore (±13 con 15/categoria), registra le risposte troncate (loop) | budget a tempo, campione variabile da modello a modello |
| Punti deboli | `bench2/3/4/ufficiale` scritti per i due modelli (rischio di sovradattamento); agente = compiti brevi non di codice; n piccolo per categoria | non confrontabile con la letteratura; molti ritocchi del runner |

**Conclusione:** per misurare l'*intelligenza* i benchmark di Pietro (`duro.py` + `lungo.py`) sono migliori e **da ora sono il nostro metro di qualità comune**. I nostri restano utili solo per due cose che i suoi non coprono: compiti di *programmazione agentica con test nascosti* (`agente_mini`) e il confronto fra *harness reali* (opencode, Claude Code). Non li usiamo più per classificare i modelli.

## 3. Cosa cambia da oggi lato Windows
- Il runner ora ha un modo `pietro`: avvia il server e lancia `duro.py`, `agente.py`, `lungo.py` di Pietro contro di esso. Primi giri in coda: **Agents-A1-35B Q4** e **Flash-Next di riferimento** con `duro --n=8 --jobs=1`, `agente`, `lungo --max=64000`.
- I dataset di `duro.py` sono stati scaricati e convertiti in `benchmarks/mac-pietro/dati/` (non nel repo, come da `.gitignore`).
- Limite: n=8 per set → ±20 punti per set: **solo confronti grossolani**; se un confronto conta, ripetiamo con n più alto.
- Non cambiamo i vostri script; se serve un fix lo proponiamo con una pull request.

## 4. File grandi (GGUF) su GitHub
- Un push con un file **> 100 MB viene rifiutato**. Git LFS gratuito ha 1 GB di spazio e 1 GB di banda al mese: non basta per 10 GB.
- **Soluzione consigliata: GitHub Release, file a parti.** Ogni file di una release può arrivare a 2 GB. Per ONYX-224r (10,2 GB):
  ```bash
  split -b 1900m Agents-A1-ONYX-224r.gguf onyx224r.gguf.part-
  shasum -a 256 Agents-A1-ONYX-224r.gguf > onyx224r.sha256
  gh release create onyx-224r --repo mtom123/LocaLLM-HUB --title "ONYX-224r (parti)" \
     --notes "Ricomporre con: cat onyx224r.gguf.part-* > Agents-A1-ONYX-224r.gguf; verificare sha256" \
     onyx224r.gguf.part-* onyx224r.sha256
  ```
  Ricomposizione su Windows: `copy /b onyx224r.gguf.part-aa+onyx224r.gguf.part-ab+... Agents-A1-ONYX-224r.gguf`.
- **Attenzione alla licenza**: il repo è pubblico. Prima di pubblicare un derivato, controlla la licenza del modello di partenza (Agents-A1, APEX/ONYX di mudler: se non permette la ridistribuzione, non caricare il file, **scrivi invece la ricetta**).
- **Alternativa senza file:** ricetta riproducibile in `docs/`: repo e nome esatto del file sorgente, `prune_experts.py K`, quale imatrix (e come generato), quali 10 strati riquantizzati e a cosa. Noi rifacciamo il file sul PC Windows.
- Se nessuna delle due è possibile: trasferimento diretto (cloud personale) tra Motti e Pietro, fuori da GitHub.

## 5. Cosa non è ancora verificato
- ONYX-224r sulla RTX 3060: sul Mac sono ~12,1 GB utilizzabili; sulla 3060 12 GB con Windows ne restano ~11,5. A 64K potrebbe entrare, a 256K quasi sicuramente no. **Non l'abbiamo provato**.
- La velocità DFlash+ngram-mod su Windows non è ancora misurata (in coda).

## 6. Richieste a Pietro e al suo agente (in ordine)
1. **Aggiornate il repo**: `git pull --rebase` (ci sono nuovi file in `docs/`, `data/`, `tools/`).
2. **ONYX-224r**: scegliete una delle due vie della sezione 4 (release a parti **oppure** ricetta), e scrivete nel file che pubblicate la licenza del sorgente.
3. **Ricetta DFlash+ngram-mod**: ci serve versione di llama.cpp, `-ngld`, `--spec-draft-n-max`, `--spec-type` esatto e il drafter Q4_K_M usato. Noi stiamo provando `--spec-type draft-dflash,ngram-mod` con `Anbeeld/Qwen3.5-35B-A3B-DFlash-GGUF` (Q4_K_M, 0,24 GB).
4. **Controllo incrociato** (entrambi): stesso modello piccolo, **Agents-A1-4B Q4_K_M** (InternScience), tre misure: `tools/speedtest.py` (core-speed), `duro.py --sets=math,code,mbpp,mmlu --n=8 --jobs=1`, `agente.py`. Pubblicate i risultati con `benchmark.suite` = `duro-v1` / `agente-v1`. Se i numeri tra le due macchine non coincidono entro il rumore, c'è un bug nel setup di uno dei due.
5. **Un solo punto di aggiornamento**: ogni ciclo, aggiornate `data/projects.json` e `data/queue.json` (con `platform: mac`), come abbiamo fatto noi. Scrivete **cosa non ha funzionato**, non solo i successi.
6. **Idee su cui vorremmo la vostra opinione**: (a) l'ONYX potato a 192 expert per macchine da 12 GB; (b) `--kv q4_0` per raddoppiare il contesto: quanto vi è costato in qualità a 256K?; (c) usare il "cervello" davanti a un agente reale.

Grazie: il vostro metodo (set pubblici, seed fissi, prove negative documentate) è quello che vogliamo applicare anche noi.
