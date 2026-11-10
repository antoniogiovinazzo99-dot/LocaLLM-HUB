# Contesto 1M senza distruggere velocità e intelligenza — metodo e numeri (10/11/2026)

## 1. Il fatto che cambia tutto: A1 non è un transformer denso
Dal `config.json` di `InternScience/Agents-A1` (base di Agents-A1-35B-A3B):
- **40 layer**, di cui **30 a `linear_attention`** e **10 a `full_attention`** (uno ogni 4).
- **2 KV head**, `head_dim = 256`, 16 query head, MoE 256 esperti / 8 attivi.
- `max_position_embeddings = 262.144` (256K nativo).

I layer lineari hanno uno **stato ricorrente a dimensione fissa**: non crescono con il contesto. Solo i 10 layer full attention pagano la KV per token.

## 2. Quanta KV costa davvero (calcolo esatto)
KV per token = 2 (K+V) × 10 layer × 2 KV head × 256 dim = **10.240 elementi/token**.

| precisione KV | byte/token | 128K | 256K | 512K | **1M** |
|---|---:|---:|---:|---:|---:|
| q8_0 (~1,06 B) | ~10,9 KB | 1,4 GB | 2,8 GB | 5,6 GB | **10,9 GB** |
| q4_0 (~0,56 B) | ~5,7 KB | 0,7 GB | **1,5 GB** | 2,9 GB | **5,7 GB** |

Con **KV q4_0**, 1M di contesto costa **5,7 GB**. Sulla 3060 da 12 GB è **fattibile in memoria** — il problema non è più la VRAM, è il **prefill** e la qualità oltre i 256K nativi.

## 3. Perché la velocità non crolla (quanto ci si può aspettare)
- **Decode**: a 1M token si leggono 5,7 GB di KV per token → a ~360 GB/s teorici ≈ 60 t/s di limite di banda; con l'attenzione (10 layer, 16 teste) il conto scende. Realistico: **20-40 t/s**, non 1 t/s. I 30 layer lineari costano O(1), non O(context).
- **Prefill**: è il muro. A ~300 t/s (misurato a 64K) 256K = ~14 min, 1M = ~55 min. **Si paga una volta sola** con il metodo sotto.
- **Memoria**: modello Q4 19,7 GB + KV 5,7 GB non stanno in 12 GB: una parte degli esperti va in RAM (come oggi). Con **IQ3_XXS (13,6 GB)** + KV q4 si avvicina; con IQ2 (8,6 GB) ci starebbe, ma l'esperimento AREX IQ2 dice **-24 punti di duro**: non conviene.

## 4. Il metodo: **KV Knowledge Pack + memoria calda/fredda**
E' la versione locale e onesta di "1M di contesto come una sessione vera":

1. **Pack**: si prefillа una volta il corpus lungo (documenti, storico, codice) a 256K nativi, si **salva lo stato dello slot** su disco (`--slot-save-path`, endpoint slot save/restore di llama-server; da verificare sul build). Il file è la KV compressa q4: ~1,5 GB a 256K, ~5,7 GB a 1M. E' il "file shrinkato" della memoria, non del modello.
2. **Restore**: a ogni nuova sessione si ricarica il pack (secondi, non 14-55 min) e si riparte con il contesto già caldo.
3. **Caldo/freddo**: la finestra calda (8-32K) sta in KV e risponde con qualità piena; il resto del 1M vive nel pack + in un **indice di recupero** (BM25/embedding) che riporta i passaggi rilevanti nella finestra calda. Il modello non deve tenere 1M token "attivi" per ogni domanda.
4. **Eviction/attention sink** (opzionale, ricerca): tenere i primi token + la coda e scartare il mezzo riduce la KV del 90% ma perde il richiamo esatto: si usa **solo** per la parte fredda, con il recupero a coprire i fatti.

## 5. Perché è "rivoluzionario" e non un trucco
- Sfrutta l'architettura **ibrida** del modello (linear attention) invece di combatterla: la memoria a lungo termine è nello stato ricorrente, la KV serve solo per i 10 layer full.
- Il pack è **persistente**: una sessione da 1M non ripaga il prefill ogni volta. E' la differenza tra "context window" e "memoria di lavoro".
- E' **misurabile**: richiamo a 256K/512K/1M, TTFT con e senza pack, decode t/s, qualità duro/harness. Se il richiamo oltre 256K crolla (estrapolazione RoPE), lo scriviamo.

## 6. Piano di test (in ordine)
1. **[in corso]** `n10-a1-35b-q4-256k`: A1-35B Q4, `-c 262144 -ctk q4_0 -ctv q4_0`, `lungo --max=250000`. Misura prefill, decode, richiamo a 250K. E' il punto di partenza nativo.
2. **512K con YaRN** (`--rope-scaling yarn --rope-scale 2`): verifica se il richiamo regge oltre il nativo.
3. **1M con KV pack**: prefill 1M, salva lo slot, riavvia, restore, misura TTFT e richiamo. Se il prefill supera i 60 min, si fa a blocchi con checkpoint.
4. **Retrieval caldo/freddo**: indice BM25 su 1M token + finestra 16K; 50 domande con aghi a profondità diverse; confronto con truncation 32K.
5. **Confronto modelli**: Nemotron 74B (Mamba-2 ibrido, 256K nativo) e un eventuale modello MLA; la stessa metrica.

## 7. Limiti da dire chiaro
- **256K è il nativo**. 1M è estrapolazione: la qualità può calare anche se la memoria basta.
- Il prefill di 1M è lungo (~1 ora) e il pack va salvato/ripristinato con un formato stabile: se cambia la build di llama.cpp, il pack può non essere compatibile.
- Il pack occupa disco (1,5-5,7 GB per sessione) e la KV q4 costa qualcosa in qualità (da misurare contro q8 a 64K).
- La parte fredda **non è** "il modello che ricorda 1M token": è un recupero. Per i fatti esatti funziona; per il ragionamento su tutto il corpus in una volta, no.

## 8. Fork candidati (ricerca GitHub, 10/11)
- **`AmesianX/TurboQuant`** — KV cache compression per llama.cpp: **~5,2x meno memoria, near-lossless**. Se funziona, la KV di 1M scende da 5,7 GB a ~1,1 GB e il decode legge 5x meno: è la strada più concreta per 1M *e* velocità. Da provare su CUDA Windows.
- **`scrya-com/rotorquant`** — KV compression via rotazione block-diagonal, PPL migliore di TurboQuant; altro fork da confrontare.
- **`DaoyuanLi2816/mini-verl`** — PPO/GRPO/on-policy distillation su **una sola GPU consumer**: è l'infrastruttura giusta per addestrare il 4B su 12 GB.
- **`songmzhang/KDFlow`** — framework di knowledge distillation (off/on-policy).
- **`WLS04/EOPD`** — entropia-aware on-policy distillation (ICML 2026), +5 Pass@8 su Qwen3-4B.
- **`Zagitta/gpu-unlock`** — Linux only; port Windows `impacifist/Windows-GPU-UNLOCK` sperimentale (EFI headless), guadagno reale su Q4 GGUF piccolo e rischio alto. Non prioritario.

## 9. Nota su DFlash/DSpine
Sono **speculative decoding**: accelerano il **decode**, non il prefill. Per il prefill servono ubatch più grandi (misurato **+52%** con `-ub 1024`), FlashAttention e il KV pack.

## 10. Cosa significa per l'intelligenza

Il 4B AREX-Turbo (duro 76,3, 76 t/s) resta la base veloce; il 74B Nemotron (6/6 su omp) è il cervello profondo; A1-35B è l'ibrido da 256K. La combinazione giusta non è un modello solo: **4B per il turno veloce + pack 256K per la memoria + 74B per i compiti difficili**. La cascata decide; il pack evita di ripagare il contesto.
