# MoE cache (PR llama.cpp 30966), Nemotron 3.5 Bolt 74B, vLLM e Kubernetes — ricerca 10/11/2026

## 1. PR 30966 di llama.cpp — "2x" e' vero e ci riguarda direttamente
**Titolo:** `llama_moe_cache: run missed experts on CPU, add tuning script` (am17an), **mergeto il 7/11/2026**.
Cosa fa: quando gli esperti di un MoE stanno in RAM (`-cmoe`, `-ncmoe`, `-ot`), tiene in VRAM una **cache degli esperti piu' usati** per i batch piccoli (decode e speculativa); i miss li calcola in parte sulla CPU invece di caricarli ogni volta.

| argomento | significato |
|---|---|
| `--moe-cache-mib N` | dimensione cache in VRAM (MiB), divisa tra le GPU |
| `--moe-cache-cpu-share F` | quota dei miss calcolata sulla CPU (0..1); utile se la CPU legge gli esperti piu' velocemente di quanto la GPU li carichi |

**Numeri dell'esempio nel PR** (desktop, Qwen3.8-Flash-Next IQ4, 6,4 GB di cache): 24,2 t/s senza cache → **47,6 t/s con share 0,95**; con 19,4 GB di cache 65,5 t/s. Quindi il "2x" e' reale, ma dipende da quanta VRAM si dedica alla cache e dalla velocita' della RAM/PCIe.
C'e' anche `scripts/moe-cache-tune.py`: avvia il server 6 volte (2 dimensioni di cache x share 0/0,5/0,95), misura e **raccomanda i parametri** per la tua macchina. L'ho gia' scaricato in `llm/fabbrica/consulenza/moe-cache-tune.py`.

**Perche' e' la cosa piu' importante da provare su A1-35B Q4:** il nostro modello ha 21 GB di esperti su 12 GB di VRAM. Oggi llama.cpp divide a strati (auto) e fa 36-47 t/s. Con `-cmoe --moe-cache-mib ~6000-8000 --moe-cache-cpu-share 0,9-0,95` la VRAM diventa una cache degli esperti "caldi" e i miss vanno sulla CPU: e' esattamente lo scenario del PR. **Ipotesi pre-registrata:** +20-40% sul decode rispetto alla config attuale (47,5 t/s a 8K), quindi 55-65 t/s; se non succede, lo scriviamo.
Nota: la build **b12141 che usiamo ha gia' `--moe-cache-mib`** (verificato con `--help`); `--moe-cache-cpu-share` non compare nell'help ma il tuning script la passa — da validare al primo avvio.

## 2. Nemotron 3.5 Bolt 74B-A9B — "il piu' intelligente" (con riserve)
Fatti dalla model card NVIDIA:
- **74B totali, 9B attivi**, architettura **Mamba-2 + Transformer ibrida LatentMoE** (non un MoE classico), contesto **256K**, multilingue (anche italiano), licenza OpenMDW-1.1.
- Variante **24GB-GGUF**: un solo file da **22,02 GB**, quantizzazione nativa a 2 bit pensata per stare in 24 GB. E' la variante giusta per noi (non la BF16).
- Benchmark dichiarati (24GB IQ2): Terminal-Bench 2.1 **50,98**, GPQA Diamond **86,43**, BrowseComp **66,75**, HLE **25,30**, MCP-Atlas **52,20**, PinchBench **87,82**, SciCode **41,02**. Sono numeri da modello frontier, superiori a Qwen3.6-35B-A3B e a Gemma4 26B-A4B sulle stesse prove.

**Il nostro muro:** 22 GB di file su **12 GB VRAM + 16 GB RAM**. Il test di ieri (`yt-bolt-74b`, stesso GGUF) ha dato **19,2 t/s**, tiny 87,8, agente 83%: gira, ma con 16 GB di RAM il file pagina dal disco. Sul Mac di Pietro/nel video di NoCodeAbode con 32 GB di RAM fa 30,5 t/s.
**Cosa cambia con il MoE cache:** gli esperti possono restare in RAM e la VRAM fa da cache; ma 22 GB > 16 GB di RAM, quindi una parte del file resta mmap'd sul disco. Il guadagno possibile c'e' (meno upload PCIe, piu' cache), ma non lo dichiaro finche' non lo misuro. Da provare **dopo** aver liberato A1 (21 GB): disco attuale 17 GB liberi, il file e' 22 GB.
**Verdetto onesto:** e' il candidato numero uno per **intelligenza** (se regge anche a 2 bit, ed e' progettato per quello), non per velocita'. Se fa 20-25 t/s con 5/6 su omp, vale piu' di un 4B a 76 t/s con 4/6.

## 3. "repo vkke" — presumo vLLM
vLLM e' il motore di serving ad alta produttivita' (PagedAttention, continuous batching, DFlash/n-gram/EAGLE, prefix caching). **Non e' la scelta giusta qui:** su Windows con 12 GB e modelli GGUF serve WSL/Linux, pesa GB di dipendenze e la sua forza e' servire molte richieste in parallelo, non un singolo utente. llama.cpp resta il motore giusto. Da tenere in considerazione solo se un domani Tommaso mette un secondo PC/server Linux con piu' VRAM.

## 4. NVIDIA Kubernetes — non serve (per ora)
Kubernetes serve per orchestrare container su piu' nodi/GPU (device plugin, MIG, scheduling). Su **un solo desktop Windows con una 3060** aggiunge solo complessita' e overhead. NVIDIA NIM/container sono utili quando c'e' un server dedicato o piu' GPU. Risposta secca: **no adesso**, si' il giorno in cui il "modello di casa" gira su una macchina dedicata.

## 5. Prossimi esperimenti (in ordine, da lanciare quando Tommaso da' l'ok)
1. **MoE cache su A1-35B Q4** (nessun download): tuning script + 3 config con DFlash n3 a 8K e 64K; controllo appaiato con la config attuale (47,5 / 44,8). Atteso 55-65 t/s se il PR mantiene le promesse.
2. **Harness solo omp** su A1-35B (riferimento 35B) e cascata 4B→35B. Niente opencode: la sua TUI sporca la console e riavvia la sessione.
3. **Nemotron 3.5 Bolt 74B 24GB** dopo aver liberato A1: speed + omp + tiny. Se l'intelligenza e' quella dichiarata, diventa il "modello intelligente" della cascata, con il 4B come fronte veloce.
4. **AREX-2 IQ2** resta in coda come alternativa piu' piccola (10 GB) se Nemotron non entra.
