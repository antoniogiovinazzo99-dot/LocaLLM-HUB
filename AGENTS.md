# AGENTS.md — istruzioni per gli agenti che lavorano su questo repo

Sei un agente (Claude Code, Codex o altro) che lavora per uno dei due collaboratori di **LocaLLM-HUB**:

| Piattaforma | Persona | Cartella risultati |
|---|---|---|
| `windows` | Motti (RTX 3060 12 GB, 16 GB RAM) | `results/windows/` |
| `mac` | Pietro (Mac) | `results/mac/` |

Obiettivo comune: far girare in locale modelli **molto intelligenti, veloci (obiettivo 50+ t/s) e con contesto lungo (256K)**, e capire con test onesti cosa funziona davvero. I numeri devono essere confrontabili tra le due macchine.

## Regole d'oro
1. **Scrivi solo nella tua cartella** `results/<tua-piattaforma>/` (e `docs/`, `benchmarks/`, `tools/` se migliori il metodo). Non modificare mai `results/<altra-piattaforma>/`. Cosi non ci sono conflitti di merge.
2. **Un esperimento = un file JSON** `results/<piattaforma>/<AAAA-MM-GG>-<slug>.json` (l'`id` dentro deve essere uguale al nome del file). Schema in [`docs/SCHEMA.md`](docs/SCHEMA.md), esempio in [`templates/result.example.json`](templates/result.example.json).
3. **Nessun numero senza contesto.** Ogni file ha `summary` (1-3 frasi: cosa dice il test), `engine` (nome, versione, argomenti), `hardware`, `benchmark.suite`. Un risultato senza queste cose e inutile per chi legge dopo.
4. **Registra anche i fallimenti** (`status: "failed"`, spiega perche in `summary`): sapere che DSpine si pianta o che un modello non entra in VRAM e informazione preziosa.
5. **Onesta statistica:** scrivi `n` (campioni) quando sono pochi; il tiny benchmark ha rumore ±3 punti; non dichiarare un vincitore dentro il rumore. Se un risultato contraddice un altro test (es. tiny alto, Suite S bassa) dillo nelle `notes`.
6. **Niente segreti**: mai token, chiavi API, percorsi con il nome utente, dati personali. Usa `<PATH>/nome-file` per i percorsi.
7. **Non scaricare, installare o cancellare nulla sul computer del tuo utente senza il suo OK.** Pubblicare su GitHub invece e il lavoro che ti e stato chiesto.

## Come aggiungere un test (flusso standard)
```bash
git pull --rebase
# 1) avvia il tuo server (llama-server, LM Studio, mlx_lm.server...) con il modello da testare
# 2) misura la velocita col protocollo comune e genera il file:
python tools/speedtest.py --platform mac --author Pietro --title "Qwen3.8-27B Q4 base" \
  --model-name Qwen3.8-27B --quant Q4_K_M --engine llama.cpp --engine-version b12141 \
  --engine-args "-c 8192 -ngl 99" --chip "Apple M3 Max" --ram-gb 64 --os "macOS 15" --port 8080
# 3) per altri tipi di test (qualita, agente, armature, harness) scrivi il JSON a mano partendo dal template
python tools/build.py          # valida tutto e rigenera results/mac/index.json
git add -A && git commit -m "mac: <cosa hai testato>" && git push
```
Il sito (`index.html`) legge `results/*/index.json`: dopo il push (e un minuto di Pages) il test compare nella colonna giusta. Niente altro da toccare.

## Che test fare (in ordine di priorita)
1. **Velocita comune (`core-speed`)**: obbligatoria per ogni modello/configurazione, e quella che rende i Mac e il Windows confrontabili. Prova la stessa configurazione con e senza drafter / MTP / speculative decoding.
2. **Qualita seria (metro comune dal 9/11)**: `duro.py`, `lungo.py`, `agente.py` in [`benchmarks/mac-pietro/`](benchmarks/mac-pietro/): parlano con qualsiasi server OpenAI-compatibile. Dichiara `benchmark.suite` = `duro-v1` ecc. e i parametri (`--n`, `--jobs`). I benchmark Windows ([`benchmarks/windows-fabbrica/`](benchmarks/windows-fabbrica/)) restano solo per agente-mini e harness reali. Leggi [`docs/ALLINEAMENTO-2026-11-09.md`](docs/ALLINEAMENTO-2026-11-09.md).
3. **Agenti**: agente-mini (6 compiti con test nascosti) e prove con harness reali (Claude Code, opencode, omp, ...).
4. **Armature e intelligenza extra**: voto su N campioni, programma eseguito, verifica, cascate, knowledge pack, QLoRA. Sempre con la **base senza armatura sugli stessi esempi** accanto.
5. **Idee**: aggiungi a [`data/ideas.json`](data/ideas.json) (solo in coda, un oggetto per idea) cio che vale la pena provare.

## Cosa sappiamo gia (non rifare, parti da qui)
Leggi [`docs/FINDINGS.md`](docs/FINDINGS.md) prima di scegliere i test: contiene i risultati verificati e le trappole gia trovate (tiny saturo, IQ2 che crolla fuori dal tiny, DFlash2 che aiuta solo con VRAM libera, DSpine che non gira, test "lungo contesto" sospetto).

## Unificazione dei benchmark
Piano in [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md#unificazione). Fino a quando non e fatta: usa `core-speed` per la velocita, dichiara sempre quale suite usi, non confrontare punteggi di suite diverse.

## Etichetta
- Commit piccoli, messaggi chiari: `<piattaforma>: <cosa>`.
- Prima di ogni push: `git pull --rebase` e `python tools/build.py --check`.
- Se non sei sicuro di un dato, scrivilo nelle `notes` come "non verificato" invece di arrotondarlo.
