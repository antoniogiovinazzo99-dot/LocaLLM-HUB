# Schema di un esperimento (v1)

Un file JSON per esperimento in `results/<platform>/<id>.json`. `tools/build.py` lo valida e costruisce l'indice che legge il sito.

## Campi obbligatori
| campo | valore |
|---|---|
| `schema` | `1` |
| `id` | `AAAA-MM-GG-slug`, minuscolo, uguale al nome del file (senza `.json`) |
| `platform` | `windows`, `mac` o `linux` (uguale alla cartella) |
| `author` | `Motti`, `Pietro`, ... |
| `date` | `AAAA-MM-GG` |
| `category` | `speed`, `speculative`, `quality-tiny`, `quality-suite-s`, `agent`, `armature`, `harness`, `other` |
| `status` | `ok`, `partial` (parti mancanti o campioni troppo piccoli), `failed` (non ha prodotto numeri) |
| `title` | nome breve |
| `summary` | 1-3 frasi: cosa dice il test. Compare nella card e e la prima cosa che legge un agente |
| `model.name` | nome del modello |
| `hardware.gpu` o `hardware.chip` | es. `NVIDIA RTX 3060 12GB`, `Apple M3 Max` |
| `metrics` | oggetto (puo essere `{}` solo se `status=failed`) |

## Campi consigliati
`model.repo`, `model.file`, `model.quant`, `model.size_gb`; `engine.name` (`llama.cpp`, `strata`, `mlx`, ...), `engine.version`, `engine.args` (lista); `hardware.ram_gb`, `hardware.os`; `benchmark.suite` e `benchmark.version`, `benchmark.harness`; `reference` (true se e un riferimento di confronto); `notes` (contesto che i numeri non dicono: anomalie, dubbi, cosa rifaresti); `tags`.

## Nomi standard delle metriche
Usa questi nomi quando la misura e la stessa, cosi i confronti funzionano. Altre chiavi sono libere.

| chiave | significato |
|---|---|
| `decode_tps_1` | token/s in scrittura con un solo flusso (mediana) |
| `decode_tps_4` | token/s totali con 4 richieste in parallelo |
| `prompt_tps` | token/s in lettura del prompt (prefill) |
| `tps_media`, `tps_by_type` | velocita media e per tipo di prompt (protocollo `core-speed`) |
| `draft_acceptance_pct` | % di token proposti dal drafter e accettati (sul codice) |
| `mmlu`, `arc`, `gsm`, `code12`, `humaneval` | % sul tiny benchmark (100 domande per materia, rumore ±3) |
| `q_medio` | media delle % del tiny (indicativa, saturata) |
| `math`, `bbh`, `hep`, `lcb`, `lavori`, `lungo` | % sulle parti della Suite S |
| `indice_uso` | media pesata della Suite S (lavori 25, math 15, lcb 15, bbh/hep/lungo/mmlupro 10, mbpp 5) |
| `agente_mini` | % di compiti risolti del tutto da agente-mini (6 compiti) |
| `needle_64k` | 1 se ritrova l'ago in 64K token |
| `armature` | oggetto `{ricetta: {acc, n, min}}` per i test di armatura |
| `suite_s_samples` | `{parte: "campioni fatti/totali"}`: diffida di parti con pochi campioni |

## Esempio completo
[`templates/result.example.json`](../templates/result.example.json)
