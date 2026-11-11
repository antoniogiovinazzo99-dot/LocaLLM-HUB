# Ricerca 11/11/2026 — FreeToken, Edge0, Sleep, Hope/Nested Learning

Quattro filoni studiati su richiesta di Tommaso. Per ognuno: cosa è, cosa può darci, cosa è provato e cosa no.

## 1. FreeToken (`FlashML-org/FreeToken`, arXiv 2608.16157, UC Berkeley)
**Cos'è:** motore di serving MoE edge-native. Tratta GPU, CPU, RAM host e PCIe come un'unica piattaforma elastica: cache esperti globale LRU, prefill double-buffered, politica di banda $q^\star$, formati FTW, cache semantica di KV per non ricalcolare i tool call, API OpenAI e Anthropic.
**Numeri dichiarati:** 290B+ MoE su PC; **35B su GPU da 8 GB a ~39 tok/s**; 2-4× Ollama.
**Windows:** il **CLI è Linux x86_64** (CUDA 13); c'è una **desktop app per Windows** su flashml.ai. Supporta **GGUF** con architetture `qwen35moe` → il nostro A1-35B è compatibile.
**Perché ci interessa:** è esattamente il problema nostro (35B MoE su 12 GB VRAM + 16 GB RAM). Se la desktop app funziona, possiamo servire A1 IQ3/Q4 con streaming degli esperti e confrontare prefill/decode con llama.cpp.
**Stato:** sorgente clonato in `llm/fabbrica/freetoken`; **non installato** (serve la desktop app o un ambiente Linux). Test da fare: installare l'app Windows, `ft serve --model <A1.gguf>`, misurare con `speedtest.py` e `duro`/`omp`.

## 2. Edge0 (`Edge0-AI/Edge0`, arXiv 2609.18063)
**Cos'è:** streaming MoE da SSD + **Recover-LoRA** (adattatori distillati dal teacher FP per recuperare la perdita int4) + **prerouter** che predice il routing un passo avanti per sovrapporre i caricamenti.
**Numeri dichiarati:** Edge0-35B (Qwen3.6-35B-A3B int4 + LoRA): **23,6-24 tok/s** su RTX 4070S 12 GB, 3,75 s al primo token, **5,35 GB di VRAM**, 2,86 GB di RAM su CPU Windows. Perdita media 3,9 punti vs FP16.
**Windows:** sì, engine `edge0-infer` (GGML) con backend CPU e **Vulkan**; serve build CMake/C++ e i loro asset.
**Perché ci interessa:** è la prova che un 35B può girare in ~3 GB di RAM con qualità vicina al FP16. Se il prerouter funziona, è la strada per far stare A1 a contesto lungo senza thrash.
**Limiti per noi:** il modello è **il loro** (Qwen3.6 + LoRA + prerouter), non A1; servono ~18 GB di sorgente + ~20 GB di asset e un compilatore MSVC (non installato). **Non provabile stanotte**; da valutare con calma.

## 3. Sleep framework (Google Research, "Language Models Need Sleep", Behrouz et al. 2026)
**Cos'è:** ciclo in due fasi per il continual learning: **awake** (il modello lavora e tiene i fatti nuovi in memoria a breve termine) e **sleep** (espansione della memoria, distillazione, "dreaming" con dati sintetici) per consolidare senza dimenticare. Lab PyTorch: `Adineu03/sleep-framework`.
**Perché ci interessa:** è il quadro teorico del "training a cascata" che vogliamo: dopo una sessione, si consolidano le tracce verificate in un adapter, con replay dei vecchi dati per non perdere capacità.
**Fattibilità:** il ciclo completo è da datacenter; su 12 GB si può fare una versione ridotta: **LoRA/QLoRA + replay** delle tracce vincenti, non l'espansione della memoria. È la stessa idea di EOPD già documentata.

## 4. Hope / Nested Learning (Google Research, arXiv 2512.24695)
**Cos'è:** "Nested Learning: The Illusion of Deep Learning Architectures". L'idea: l'apprendimento non è un livello unico ma **livelli annidati di ottimizzazione** con memorie a scale diverse; **Hope** è il proof-of-concept, un'architettura con memoria continua e self-modifying.
**Perché ci interessa:** è la direzione "intelligenza che si aggiorna da sola" — il contrario di un modello statico con un adapter. Non è un modello GGUF e non è addestrabile su 12 GB; per ora è **ricerca da leggere**, non da eseguire. Utile per progettare il "cervello" della cascata: memoria veloce (KV), memoria episodica (retrieval), memoria lenta (LoRA).

## 5. Cosa testiamo adesso (non solo teoria)
1. **A1-35B IQ3_XXS** (13,6 GB, entra in RAM): duro+agente e harness omp. Se tiene 5/6 e un duro vicino all'89,5 del Q4, è il modello da tenere in RAM per la cascata.
2. **AREX 4B omp** (terza corsa): varianza.
3. **Cascata reale**: AREX sui 6 compiti, poi A1 IQ3 **solo sui compiti falliti** (config_loader, paginazione) in una workspace nuova. Misura qualità e tempo contro A1 da solo.
4. **FreeToken**: app Windows da provare (richiede installazione) per servire A1 IQ3 via GGUF e confrontare con llama.cpp.
5. **Sleep/EOPD**: dopo aver raccolto le tracce verificate, QLoRA sul 4B con replay; è il "training a cascata" fattibile su 12 GB.
