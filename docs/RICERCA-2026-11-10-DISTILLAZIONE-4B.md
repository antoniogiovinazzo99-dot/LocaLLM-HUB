# Piano "4B intelligente come un modello grande" — distillazione, quantizzazione, cascata (10/11/2026)

Richiesta di Tommaso: un 4B a 80 t/s con intelligenza alta; "passargli i parametri in modo ultra-condensato"; quantizzazioni sperimentali; distillare conoscenza. Qui c'e cosa e **vero**, cosa e **fattibile su RTX 3060 12 GB + 16 GB RAM**, e cosa invece e **fisicamente impossibile** (scritto, non nascosto).

## 1. La parte impossibile (da dire subito)
Non posso "passare i miei parametri" a un 4B: sono un modello remoto via API, i pesi non sono accessibili ne' scaricabili. Non esiste un modo legale o tecnico di comprimere un modello da centinaia di miliardi di parametri in 4B "senza perdita". Chi lo promette vende fumo.
Cio' che **si puo' trasferire** e il **comportamento**: tracce di ragionamento, formato degli strumenti, strategie di verifica e correzione. E' distillazione sequenza-per-sequenza (SFT/on-policy), non fusione di pesi.4B addestrato su tracce di un teacher grande puo' battere un 4B generico sulle **nostre** attivita', non essere "come" il teacher in generale.

## 2. Cosa dice la ricerca 2026 (fonti)
- **EOPD — Entropy-Aware On-Policy Distillation** (ICML 2026, arXiv 2603.07079, codice `github.com/WLS04/EOPD`): aggiunge un termine forward-KL sui token ad alta entropia alla reverse-KL standard. Guadagno dichiarato su Qwen3-4B-Base: **+5,05 Pass@8** rispetto alla distillazione on-policy classica. E' la ricetta piu' solida che ho trovato per un 4B.
- **On-Policy Distillation per agenti** (Thinking Machines, 2026; awesome-list `chrisliu298/awesome-on-policy-distillation`): il teacher genera traiettorie multi-turno, lo student impara sulle **proprie** traiettorie con reward verificabile. E' esattamente il nostro caso (test nascosti = reward).
- **Quantization-Aware Distillation (QAD)** (NVIDIA Model Optimizer; OpenReview "QAD for 4-bit on-device"): si addestra lo student mentre si simula la quantizzazione a 4/3/2 bit, con le logit del teacher. Recupera qualita' a bit bassi. Costo: GPU-days, non stanotte.
- **imatrix** (bartowski, dataset 2026): non riduce il modello, "spende meglio" l'errore di quantizzazione proteggendo i pesi importanti per il corpus di calibrazione. Guadagni misurati piccoli su Q4/Q5, piu' grandi a Q2/Q3. **Idea testabile**: calibrare l'imatrix sulle **nostre tracce agentiche** invece che su Wikipedia.
- **Cascata con verifica** (survey arXiv 2603.04445; AutoMix): il modello piccolo risponde e si auto-verifica; se la verifica fallisce si passa al grande. Nei compiti di codice la verifica e' **oggettiva** (i test), quindi la cascata non richiede un router probabilistico.

## 3. Le quattro strade, in ordine di rapporto valore/costo

### A. Cascata con verifica oggettiva 4B -> 35B (costo zero, misurabile subito)
Il 4B fa il compito e esegue i test visibili. Se passano, si tiene la risposta; se falliscono, il 35B riparte sullo stesso compito. Qualita' attesa = quella del 35B sui compiti dove il 4B fallisce, tempo = tempo 4B + tempo 35B **solo sui falliti**.
Misura: dai due file harness (stessi 6 compiti, stesso giorno) si calcola
`qualita_cascata = max(4B, 35B)` per compito e `tempo_cascata = T4 + sum(T35 dei falliti)`.
Limite onesto: se i test visibili passano ma i nascosti no, la cascata non scatta (falso positivo del verificatore). Va misurato: e' la differenza tra "pieno" e "parziale" nei nostri risultati.

### B. Distillazione di comportamento su tracce del teacher (1-2 giorni di lavoro, non stanotte)
- Teacher: DeepSeek V4.1 Flash (OpenCode Go, consentito) o il 35B locale.
- Dati: 6 compiti `agente_mini` x 30 varianti (nomi, dati, bug diversi) + le tracce di correzione. Il teacher genera la soluzione **e** il ciclo prova->errore->correzione.
- Student: AREX-Turbo 4B (o Agents-A1-4B) con **QLoRA 4-bit**, seq 4096, batch 1, grad-accum 16. Su 12 GB sta.
- Ricetta: SFT sulle tracce + un giro on-policy (lo student prova, il teacher corregge) con il termine EOPD semplificato (forward-KL sui token dove il teacher e' incerto). Implementazione realistica: `unsloth` o `torchtune` + export GGUF.
- Valutazione: **held-out** (varianti mai viste) + `duro` + harness opencode/omp. Senza held-out e' overfitting alle 6 attività, e lo diremo.

### C. Quantizzazione sperimentale con imatrix di dominio (fattibile in ~40 min di GPU)
1. Scaricare AREX-Turbo **Q8_0** (4,49 GB) come sorgente.
2. Costruire un corpus di calibrazione con: tracce agentiche nostre, codice dei 6 compiti, README/regole, e una quota di testo generale (per non perdere lingua).
3. `llama-imatrix -m Q8 -f calib.txt -o imatrix-agent.gguf` (4B: pochi minuti).
4. `llama-quantize --imatrix imatrix-agent.gguf Q8 IQ2_XXS/IQ3_XXS arex-turbo-agent-IQ2.gguf`.
5. Confronto **appaiato** con il quant standard di bartowski sugli stessi esempi: `duro --n=8` + `agente`.
Ipotesi: a IQ2_XXS l'imatrix di dominio recupera 3-8 punti su codice/agente rispetto al quant generico; se non li recupera, lo scriviamo.
Nota: a 4B, IQ2_XXS ~1,8 GB -> sta in VRAM con 128K di contesto e viaggia sopra 100 t/s. E' l'unico modo di avere insieme "80+ t/s" e "contesto lungo".

### D. Knowledge pack (contesto come memoria, non come pesi)
Prefillare una volta un corpus di conoscenza e salvare la KV (`--slot-save-path`, endpoint slot save/restore di llama-server), poi riusarla. Per un agente il caso d'uso vero e' il **prefisso di sistema lungo** (16-27K token): `--cache-ram` + `--cache-reuse` lo riusano gia' oggi, senza ricerca. Per 1M di contesto su 12 GB la KV densa non entra (a q4_0, 1M token costano decine di GB): servono modelli con attenzione lineare/SWA o retrieval. Lo misureremo a 128K e diremo il muro reale.

## 4. Cosa faccio stanotte (dentro il loop)
- [in corso] Velocita' A1-35B Q4: DFlash n3 = **44,0 t/s** (+21% sulla base 36,4); n8/n15 peggiori.
- [in coda] Ricetta 64K di Pietro, `--n-cpu-moe`, **harness opencode vs omp** su A1 (misura di intelligenza richiesta da Tommaso).
- [in coda] AREX-Turbo 4B Q4: `duro` + harness. E' il candidato "80 t/s".
- [aggiunto] AREX-Turbo 4B **IQ2_XXS**: se regge l'intelligenza, e' il modello della svolta (1,8 GB, contesto lungo, >100 t/s).
- [aggiunto] `--cache-ram 512 --cache-reuse 256` sugli harness: riuso del prefisso, il "knowledge pack" che si puo' fare oggi.
- [domani] Distillazione B e imatrix C: servono dati e GPU dedicata, non si fanno in parallelo a un benchmark di velocita'.

## 5. La cosa piu' importante
La metrica primaria e' l'**intelligenza**, non i t/s. Un 4B distillato che passa 5/6 compiti a 75 t/s vale piu' di un 4B generico che ne passa 3 a 110 t/s. Per questo stanotte la classifica si fa **sugli harness reali** (opencode e omp), non sui token al secondo.
