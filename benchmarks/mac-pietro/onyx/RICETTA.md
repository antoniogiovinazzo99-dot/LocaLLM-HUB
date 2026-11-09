# Ricetta di Agents-A1 ONYX-224r (Mac, 8 novembre 2026)

ONYX-224r = ONYX-mini potato a 224 expert su 256 per strato, con gli expert Q3_K di 10 strati riquantizzati a IQ3_XXS.
10,21 GB: entra con 256K di contesto (KV q4_0) nei ~12,1 GB di memoria GPU di un Mac M4 da 16 GB.

## Licenze (perche ricetta e non file)
- Modello di partenza **InternScience/Agents-A1**: Apache-2.0 (ridistribuzione dei derivati permessa, con avviso).
- Quantizzazione **el4/Agents-A1-ONYX-GGUF** (`Agents-A1-ONYX-mini.gguf`, sorgente di questa ricetta): **nessuna licenza
  dichiarata** sul repository. Per prudenza non ripubblichiamo il file derivato: si ricostruisce con i passi sotto.
- Gli imatrix (statistiche calcolate da noi) sono nella release `onyx-224r-ricetta` di questo repo.

## Ingredienti
| File | Dove | sha256 |
|---|---|---|
| `Agents-A1-ONYX-mini.gguf` (11,83 GB, 256 expert) | Hugging Face `el4/Agents-A1-ONYX-GGUF` | (quello del repository) |
| `imatrix-a1-v2.gguf` (256 expert) | release `onyx-224r-ricetta` | `c300400e10b0075ecda2a78853c20efe85e0751f9cd8e675301b2bd2b82a60ca` |
| `imatrix-a1-v2-pota224.gguf` (224 expert) | release `onyx-224r-ricetta` (o passo 2) | `13602526c1bfeb3ecad9a515f6639f403a8b7a52f95eeada027b4f3a38959cac` |
| `tipi-onyx224r.txt` | questa cartella | tipo finale di ogni tensore, un nome esatto per riga |
| llama.cpp | b12038 (usato da noi), `llama-quantize` | |
| `prune_experts.py`, `prune_imatrix.py` | `benchmarks/mac-pietro/` | servono `numpy` e `gguf` (`GGUF_PY=<llama.cpp>/gguf-py` oppure `pip install gguf`) |

Risultato atteso: `Agents-A1-ONYX-224r.gguf`, sha256 `3a0ff9c2b6b175f519ab9e4c710720eb4abf140dd11e4d3dc31272ad7e348c45`
(se lo sha256 non coincide ma i tipi si, la differenza puo venire da versioni diverse di gguf-py nei metadati).

## Passi
```bash
# 1) potatura: in ogni strato tiene i 224 expert piu usati secondo i conteggi dell'imatrix (a parita, attivazioni piu forti)
python prune_experts.py Agents-A1-ONYX-mini.gguf imatrix-a1-v2.gguf 224 Agents-A1-ONYX-224.gguf
# 2) imatrix ritagliato agli stessi 224 expert (serve alla riquantizzazione; oppure usare quello della release)
python prune_imatrix.py imatrix-a1-v2.gguf 256 224 imatrix-a1-v2-pota224.gguf
# 3) riquantizzazione: solo gli expert (ffn_up/gate/down_exps) degli strati 3, 7, 11, 27, 34-39 passano da Q3_K a IQ3_XXS;
#    tutti gli altri tensori hanno nel file lo stesso tipo che hanno gia e vengono copiati identici.
llama-quantize --allow-requantize --imatrix imatrix-a1-v2-pota224.gguf --tensor-type-file tipi-onyx224r.txt \
  --output-tensor-type q6_k --token-embedding-type q6_k Agents-A1-ONYX-224.gguf Agents-A1-ONYX-224r.gguf IQ2_XXS 4
```
Nota: senza le righe `=f32` per i tensori F32 a 2 dimensioni (es. `ssm_alpha`) `llama-quantize` li quantizzerebbe: nel file
dei tipi ci sono gia.

## Come e stato fatto l'imatrix v2
`llama-imatrix -m Agents-A1.i1-IQ2_S.gguf -f calibrazione-a1-v2.txt -o imatrix-a1-v2.gguf -ngl 99 -c 512 -b 512 --chunks 400`
(llama.cpp b12038). Calibrazione v2 (1,05 MB): 864.000 caratteri di articoli di Wikipedia italiana e inglese presi a campione
+ 184 KB di testo misto (registri in italiano, sorgenti C++ e Python, esercizi). Con la sola calibrazione v1 (senza Wikipedia)
la potatura faceva crollare la conoscenza dal 100% al 37,5% su `mac-bench2`.

## Come avviarlo (Mac)
```bash
llama-server -m Agents-A1-ONYX-224r.gguf -ngl 99 -c 262144 -fa on -ctk q4_0 -ctv q4_0 -b 512 -ub 256 \
  --parallel 1 --cache-ram 512 --jinja --spec-type ngram-mod
```
Sulla RTX 3060 (circa 11,5 GB utilizzabili) a 256K quasi certamente non entra: provare 64K.

## Opinioni sulle domande della sezione 6
- **ONYX a 192 expert per 12 GB:** sconsigliato senza misurarlo. 192r copre il 94,5% dell'uso (strato peggiore 86%) e a 176
  il modello crolla (18,6% su `duro`). Su 12 GB conviene ONYX-224r con meno contesto (64K) piuttosto che piu potatura.
- **KV q4_0:** a 256K ONYX-224r ritrova 5/5 fatti su 240K token, ma non abbiamo un confronto diretto q8_0 contro q4_0
  sullo stesso set di qualita: il costo non e misurato (tutti i nostri test di qualita ONYX usano gia q4_0).
- **Cervello davanti a un agente reale:** oggi passa intatte le richieste con strumenti (un agente le manda sempre), quindi
  non cambia nulla. Puo servire per decidere *se* ragionare a ogni passo: proprio quello che rallenta gli agenti locali.
