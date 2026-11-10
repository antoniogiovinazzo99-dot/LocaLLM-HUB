# Ricetta DFlash + ngram-mod (Mac, 9 novembre 2026)

Risultato: `2026-11-09-agents-a1-onyx-224r-64k-dflash-ngram-mod` = 51,0 t/s medi su `core-speed` (mediana 41,2),
accettazione 72,6%, contro 26,5 t/s della base allo stesso contesto.

## Esatto
| Voce | Valore |
|---|---|
| llama.cpp | **b12038** (release ufficiale `llama-b12038-bin-macos-arm64`, commit a7a490a49), Metal |
| Modello | `Agents-A1-ONYX-224r.gguf` (ricetta in `onyx/RICETTA.md`) |
| Drafter | `Anbeeld/Qwen3.5-35B-A3B-DFlash-GGUF` → `Qwen3.5-35B-A3B-DFlash-Q4_K_M.gguf` (0,24 GB), sha256 `b92b48aaeef7048c102ac8f7e7796fd5c5c49a8d696095e5ccec33fd36c56700`; drafter originale `z-lab/Qwen3.5-35B-A3B-DFlash` (Apache-2.0) |
| `--spec-type` | `draft-dflash,ngram-mod` (in quest'ordine) |
| `-ngld` | `99` (drafter tutto sulla GPU) |
| `--spec-draft-n-max` | **non impostato** = default 3 |
| `--spec-draft-n-min`, `--spec-draft-p-min` | default (0, 0.00) |
| ngram-mod | default: `--spec-ngram-mod-n-min 48`, `--spec-ngram-mod-n-max 64`, `--spec-ngram-mod-n-match 24` |
| Contesto | `-c 65536` (a 96K rallenta, a 128K e 256K memoria GPU esaurita) |

```bash
llama-server -m Agents-A1-ONYX-224r.gguf -ngl 99 -fa on --jinja --parallel 1 --cache-ram 512 \
  -c 65536 -ctk q4_0 -ctv q4_0 -b 512 -ub 256 \
  --spec-type draft-dflash,ngram-mod -md Qwen3.5-35B-A3B-DFlash-Q4_K_M.gguf -ngld 99
```

## Cosa sappiamo e cosa no
- Solo `ngram-mod` (nessun drafter) a 256K: 33,8 t/s contro 28,3 (+19%), accettazione 53,5%. `ngram-simple`: nessun guadagno.
- Solo DFlash a 64K: 37,1 t/s (+40%), accettazione 66,8%.
- Il guadagno dipende dal testo: ragionamento 70 t/s e JSON 54 (ripetitivi), codice 41, storia 38.
- Provati il 10 novembre (`2026-11-10-...-draft-*`): `--spec-draft-n-max` 6, 8, 10, `--spec-draft-p-min` 0,5 e 0,7, `-ub 512`: **nessuno batte la ricetta**
  (controllo nello stesso momento 54,9 t/s, varianti 50-51, draft 10 = 27). Il rumore tra corse uguali e alto (44 e 30 t/s per la stessa
  configurazione): confrontare solo con un controllo vicino nel tempo.
- Non provati: i drafter Q8_0 / Q2_K, la versione Qwen3.6, build piu recenti di b12038.
- Il drafter non e stato addestrato su Agents-A1 ma sul modello base Qwen3.5-35B-A3B: l'accettazione del 67-73% dice che
  la famiglia e abbastanza vicina.
