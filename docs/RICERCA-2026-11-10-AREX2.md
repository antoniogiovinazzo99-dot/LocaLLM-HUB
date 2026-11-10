# AREX-2 e AREX-Turbo (BAAI) — vale la pena sulla 3060? (10/11/2026, lato Windows)

Ricerca fatta stanotte su richiesta di Tommaso ("molti ne parlano, il concetto di harness e interessante").
**Stato: non ancora testato su questa macchina.** I numeri qui sotto sono quelli dichiarati da BAAI (model card + paper), non misure nostre.

## Cosa sono (fatti verificati sulla model card)

- **AREX-2**: 27B **denso**, base `Qwen/Qwen3.8-27B`, contesto 262.144, licenza Apache-2.0. Addestrato su compiti di programmazione e ML con **feedback verificabile** ("propose, measure, reflect, revise"): il modello impara a fare da solo il ciclo *prova -> misura -> rifletti -> correggi*, invece di lasciarlo tutto all'harness esterno. E' esattamente il concetto che interessa a Tommaso.
- **AREX-Turbo**: lo stesso tipo di addestramento su una base **4B**.
- Pesi: `BAAI/AREX-2` (safetensors), GGUF della comunita: `bartowski/BAAI_AREX-2-GGUF`, `mradermacher/AREX-2-i1-GGUF`, `bartowski/BAAI_AREX-Turbo-GGUF`.

## Numeri dichiarati (da prendere con le molle: sono del produttore)

| modello | parametri | Frontier-CS | MLE-Lite | BrowseComp | HLE | GAIA |
|---|---|---:|---:|---:|---:|---:|
| AREX-2 | 27B denso | 70,7 | 81,8 | 84,0 | 52,6 | 92,2 |
| Agents-A1 (il nostro 35B) | 35B MoE | - | - | 75,5 | 47,6 | 96,0 |
| AREX-Turbo | 4B | - | - | 70,7 | 40,6 | 81,6 |
| GPT-5.6 Sol (chiuso) | - | 76,4 | 72,7 | 90,4 | 58,0 | - |

Se anche solo meta del vantaggio su MLE-Lite/Frontier-CS e reale, AREX-2 e **piu intelligente di Agents-A1 come agente**, e AREX-Turbo e un 4B con numeri da 30B sulle stesse prove.

## Cosa entra sulla RTX 3060 (12 GB) + 16 GB RAM

| file | GB | entra? | nota |
|---|---:|---|---|
| AREX-2 IQ2_XXS | 8,64 | si, in VRAM | qualità a 2 bit da verificare (il 27B IQ2_XXS di Qwen gia girava a 20 t/s) |
| AREX-2 IQ2_M | 10,28 | si, al limite | il candidato giusto: piu qualità di XXS, pochi GB di margine |
| AREX-2 Q4_K_M | 17,20 | no in VRAM | paginerebbe da RAM/disco: probabilmente < 10 t/s, inutile |
| AREX-Turbo Q4_K_M | 2,88 | si, comodamente | 4B: atteso 60-80 t/s |

**Onesta sulla velocita:** un 27B denso a 2 bit letto dalla 3060 (~360 GB/s teorici) non arriva a 50 t/s, e tantomeno a 80. AREX-2 non e il modello dei 80 t/s. AREX-Turbo si: un 4B Q4 in VRAM puo stare intorno ai 70-80 t/s (il nostro Agents-A1-4B fa 76,8).

## Le due ipotesi da testare (non ancora misurate)

1. **AREX-Turbo Q4_K_M** come *fronte veloce* e come modello agentico: se sul nostro `agente_mini` (6 compiti con test nascosti) fa meglio di Agents-A1-4B, e il nuovo front-end della cascata a ~75 t/s. Costo: 2,9 GB di download, ~15 min di test.
2. **AREX-2 IQ2_M** come *modello "intelligente"* della cascata: `duro` n=8 + `agente_mini`, da confrontare con Agents-A1-35B Q4 (indice 69,1 / agente 83%) e con Flash-Next. Costo: 10,3 GB di download, ~40 min. Rischio: a 2 bit la qualita puo crollare — in quel caso lo registriamo come fallimento, non lo nascondiamo.

## Perche' il concetto di "harness nel modello" ci serve anche senza AREX

Il ciclo *prova -> misura -> rifletti -> correggi* si puo mettere **nel prompt di sistema** di qualunque modello: dopo ogni modifica eseguire i test visibili, leggere l'errore, correggere, e ripetere al massimo N volte prima di rispondere. E' la stessa idea di Pietro ("cervello") applicata al loop agentico. Costa zero download e si misura con gli stessi 6 compiti di `agente_mini` (base contro variante, stessi esempi). Se funziona su Agents-A1-35B, vale per tutti i modelli che useremo dopo.

## Cosa NON e verificato

- Le misure di BAAI non sono riprodotte da noi.
- Non sappiamo se il GGUF IQ2_M di AREX-2 conserva il comportamento di self-improvement (i 2 bit colpiscono soprattutto le capacita rare).
- Non sappiamo se il template di chat di AREX-2 passa `--jinja` senza patch (da verificare al primo avvio, come per Agents-A1).
