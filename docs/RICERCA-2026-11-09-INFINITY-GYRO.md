# Ricerca 9/11/2026: Infinity, Gyro, Strata — cosa serve davvero a contesto, agenti paralleli e intelligenza

Scritta lato Windows. Ogni numero e preso dalle pagine citate e marcato **(venditore)** o **(estrapolato)** quando non e una misura indipendente. Dove non ho letto la fonte lo dico.

## 1. Infinity (hydro-project, AWS + UC Berkeley) — "75.000 agenti in 8 GB"
Fonti: [blog AWS](https://aws.amazon.com/blogs/opensource/introducing-infinity-a-runtime-for-extreme-agent-concurrency/), [repo](https://github.com/hydro-project/infinity), [release 0.1.0](https://github.com/hydro-project/infinity/releases/tag/infinity-agent-core-v0.1.0).

**Cos'e:** un runtime Rust per *aspettare* agenti, non per farli ragionare. Ogni agente gira a "fette": carica la storia, fa **una** chiamata al modello, salva l'output, lancia al massimo **un** tool e finisce. Mentre il tool lavora (altrove) l'agente e sospeso e di lui resta solo la storia della conversazione in uno store. Il tool risponde mettendo il risultato in una coda e l'agente riparte.

**Il numero:** 80.000 agenti, 3,2 milioni di completamenti, un solo thread di un AMD EPYC, store in memoria, **modello simulato**: ~100 KB di memoria per agente fermo. "75.000 in 8 GB" e un'estrapolazione lineare (la menzione del Raspberry Pi 5 e solo l'esempio dei 8 GB); una nota di rilascio successiva parla di ~107 KB e di circa 71.700 agenti, un'analisi esterna di 108,5 KB. Il progetto si dichiara "research project".

**Cosa NON e:** non include inferenza locale (l'esempio chiama un provider cloud), non fa batching, non aumenta i token/s. 75k agenti che *aspettano* non sono 75k agenti che *pensano*.

**Cosa ci serve davvero (pensando alla 3060):**
- Il collo di bottiglia dei nostri agenti paralleli e il decode della GPU, non la RAM degli agenti. Su Agents-A1-35B Q4 abbiamo misurato 36,9 t/s con 1 flusso e **10,6 t/s totali con 4 flussi**: il parallelo *peggiora* perche un MoE con esperti offloadati tocca piu esperti per batch. Conclusione: pochi slot di decode (1-2), molti agenti sospesi.
- L'idea utile e il **modello a fette**: un agente non occupa uno slot mentre aspetta un tool (build, test, web). Con uno scheduler davanti al llama-server, N agenti si dividono 1-2 slot e il tempo di attesa dei tool si sovrappone. Guadagno reale = (tempo di tool) / (tempo di tool + tempo di modello): per agenti da coding e spesso il 30-60%.
- Per usarlo con un modello locale serve scrivere un provider verso l'API di llama-server (nell'articolo non c'e): lavoro modesto, non fatto.
- **Misura da fare prima di costruire:** quanti agenti agente-mini girano in parallelo su 1, 2, 4 slot e quanto scende il successo per slot da 8K vs 16K vs 32K.

## 2. Gyro (agentionai) — quantizzazione trellis per Flash-Next
Fonte: [scheda Hugging Face](https://huggingface.co/agentionai/Qwen3.8-Flash-Next-Gyro-GGUF). Tutti i numeri sono **del venditore**, su campioni piccoli (70 domande MMLU-Pro, 30 LiveCodeBench).

- **Metodo:** trellis-coded quantization con rotazione di Hadamard (famiglia QTIP), esperti in base ruotata. File: **Gyro-S 27,64 GiB** di pesi in GPU, **Gyro-M 34,98 GiB**, **Gyro-L 50,21 GiB**. Meta del file e una tabella n-gram (PLE) che resta su disco e si legge a righe (serve NVMe veloce). Bit per peso: non dichiarati.
- **Qualita (KLD, minore e meglio):** Gyro-S 0,401 contro 0,420 di IQ2_XS (36,5 GiB) e 0,311 di IQ3_XXS (43,8 GiB): a parita di KLD Gyro usa circa **25% di memoria in meno**. Gyro-L 0,146 vs EXL3 3,18 bpw 0,142.
- **Runtime:** il llama.cpp upstream non li carica. Servono Strata >= 0.2.0 (Gyro-L richiede il ramo Strata gitlab) o i fork agentionai/strix. Gyro-S e Gyro-M con Strata funzionano su NVIDIA.
- **Velocita dichiarate:** RTX 5090 Gyro-S 113 t/s (fork) / 140-221 (Strata, con MTP piu alte); RTX A6000 57; R9700 58; Strix Halo 32-36 (con MTP 50+). Gyro-L ~100 t/s a 100K di contesto su una 5090 (report della comunita).
- **Contesto:** Gyro-S "fino a 128K" (28,8 GiB a 64K); 262K provato su Strix Halo.
- **Per noi:** **non e testabile con 12 GB di VRAM + 16 GB di RAM**: Gyro-S vuole ~27,6 GiB di memoria utile per i pesi, piu KV e sistema. Non e un problema di software ma di memoria. Con 64 GB di RAM diventa la strada piu promettente per portare Flash-Next a pieno contesto con qualita vicina al Q4. Ricordato come motivo per l'upgrade RAM (2x32 GB), che resta una decisione tua.
- Cautele: file sostituiti a ottobre (versioni vecchie stale), "experimental", encoder di produzione non pubblicato, licenza qwen-community-1.0.

## 3. Strata: come allunga il contesto (pagina DETAILS)
Fonte: [Strata/docs/DETAILS.md](https://github.com/Niko1221/Strata/blob/main/docs/DETAILS.md) (letta per circa due terzi; il resto non verificato). Misure dell'autore su RTX 5070 12 GB + 64 GB RAM, **non trasferibili alla nostra macchina**.

| Leva | Cosa fa | Costo dichiarato |
|---|---|---|
| `--kv int8` | default | — |
| `--kv q4_0` | meta KV, rotazione Hadamard prima dei 4 bit | perplexity +8-12%, ~4% piu veloce a 128K |
| `--kv k8v4` | 23% meno KV dell'8 bit | prompt 2-5% piu lenti |
| `--kv-streaming` / `--kv-resident N` | KV in RAM con finestra in VRAM | ~13,7 KB di RAM per token (1,7 GB a 128K) |
| contesto | 8K-262K, oltre YaRN sperimentale | ~13 KB/token KV |
| checkpoint prompt | fino a 6, ~118 MB l'uno | — |
| `--parallel N` | N richieste decodificate insieme | logprobs solo con max_tokens 1 |

Misura dell'autore: contesto 262K, decode 60 t/s (87 a 1K).

**Per raddoppiare il contesto da noi:** la leva piu economica e `--kv q4_0` (meta memoria KV) con costo di qualita da misurare con il nostro lungo corretto e con l'agente; la seconda e il KV in RAM (13,7 KB/token: 128K = 1,7 GB, entra nei nostri 16 GB solo se il modello non occupa gia la RAM). Non dare per buono il +perplexity: va misurato su compiti da agente.

## 4. Come aumentare davvero l'intelligenza (ordinato per rapporto costo/prove)
1. **Modello migliore a pari memoria:** quantizzazione migliore (Gyro: servirebbe RAM) e modelli come Agents-A1-35B Q4, gia alla pari di Flash-Next sulla Suite S.
2. **Armature solo dove i test sono difficili:** il voto su N campioni vale in matematica ma costa 13x; il PAL costa 1x. Da provare sui lavori reali, non sul tiny.
3. **Cascata:** modello piccolo (A1-4B, 77 t/s) risponde, il 35B interviene quando il piccolo e incerto. Si simula sui log gia salvati senza usare la GPU.
4. **Contesto + conoscenza:** knowledge pack (KV precalcolata) e un contesto lungo davvero usabile (dopo aver sistemato il test del lungo).
5. **Training mirato:** QLoRA solo su un compito stretto; non rende il modello piu intelligente in generale.

## 5. Cose non verificate
Il tetto dei 75.000 agenti; ogni numero di velocita/qualita Gyro (vendor); le cifre di `STRATA_ROUTE_PRIOR`, prompt lookup e MTP room della pagina Strata che ho letto solo in riassunto; qualsiasi velocita su 16 GB di RAM di Strata (la pagina non ne ha).
