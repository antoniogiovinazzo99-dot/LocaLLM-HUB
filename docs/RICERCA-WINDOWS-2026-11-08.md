# Ricerca completa — LLM locale forte e veloce su RTX 3060 12 GB / 16 GB RAM
Data: 8 novembre 2026. Scritta da Claude per Tommaso. Dove un dato non è verificato lo scrivo esplicitamente.

---
## 1. Sintesi in 12 righe
1. **Dove siamo**: con Qwen3.8-Flash-Next (125B MoE, ~6B attivi) e Strata siamo passati da 5,8 a **30-50 t/s** sul codice e da 6,9 a **30,4 t/s a 253K token reali**, con intelligenza misurata invariata (MMLU-Pro ~70%, HumanEval 96%). Dettagli nelle sezioni 2 e 6.
2. **Onyx non è un modello.** Onyx è una piattaforma open source (chat + RAG + agenti) che pubblica anche una classifica di LLM open; probabilmente hai visto la classifica o l'articolo. Se hai un link preciso, dimmelo.
3. **"Qwen3.8 35B A3B" non è ufficiale di Qwen.** Esistono distillazioni di terzi (la più scaricata: `empero-ai/Qwen3.8-35B-A3B-Distill`, 1,3 milioni di download sul GGUF) e varianti abliterated/coder. Il modello 35B-A3B davvero interessante per noi è un altro: **Agents-A1**.
4. **Agents-A1 (Shanghai AI Lab, giugno 2026)**: MoE 35B con ~3B attivi, 256K di contesto, licenza Apache 2.0, pensato per agenti. Q4_K_M = 21,2 GB, ma esistono quantizzazioni di terzi da **11,7 GB (IQ2_M)** che stanno quasi per intero nei 12 GB di VRAM. La nostra build di llama.cpp contiene già l'architettura `qwen35moe`, quindi dovrebbe caricarlo (da verificare con un avvio vero).
5. **AREX-2 (BAAI, settembre 2026)** è un **dense 27B** (fine-tune di Qwen3.8-27B). Il suo "boost di intelligenza" non è nei pesi per la chat: è un modello addestrato a lavorare **in cicli con feedback** (esegui → misura → correggi) su compiti verificabili (ML engineering, algoritmi, ricerca). Per noi la lezione è il **metodo**, che possiamo applicare subito a Flash-Next senza addestrare nulla.
6. **Non esiste un confronto equo** tra Flash-Next e questi modelli: Artificial Analysis non ha un indice per Flash-Next, e i numeri di Agents-A1/AREX-2 sono quasi tutti dichiarati dagli autori. Serve un **benchmark nostro, uguale per tutti**: la "Fabbrica LLM" (sezione 7).
7. **La Fabbrica**: 3 livelli (smoke 3 min, rapido ~12-15 min, profondo ~45 min), basata sui dataset **tinyBenchmarks** (100 domande per materia, stima l'accuratezza dell'intero benchmark entro ~2 punti secondo gli autori), più test nostri per codice, testo, contesto lungo e sessioni da agente. I dataset sono già scaricati in `C:\Users\motti\llm\fabbrica\dati`.
8. **Vincolo pratico n.1: lo spazio.** C: ha 22 GB liberi. La Fabbrica deve funzionare in modo "scarica → testa → registra → cancella", con guardia sullo spazio. Un secondo NVMe da 1-2 TB lo renderebbe molto più semplice.
9. **Lezioni dai nostri test** che la Fabbrica deve incorporare: il rumore tra due run uguali è di 1-3 punti (quindi confronti appaiati e baseline ripetuta); le domande a risposta multipla **non vedono** il degrado della scrittura (a prior 2.0 MMLU era uguale ma il testo conteneva parole inventate); il greedy a volte si incaglia; il thinking con budget troppo basso dà 0% di risposte.
10. **Per l'intelligenza senza addestramento** i metodi misurati che funzionano sono: thinking con budget adeguato (+5,5 punti MMLU-Pro), loop genera-testa-correggi (da misurare, ipotesi forte), sampling consigliato + presence penalty (evita i collassi). Alzare i top-k degli esperti **peggiora**, secondo la letteratura.
11. **Per la velocità** le leve rimaste sono hardware (RAM 32 GB, secondo NVMe, Linux) o ingegneria sul motore; i ritocchi di configurazione sono esauriti (sezione 5).
12. **Free lab con il tuo amico**: la struttura proposta è nella sezione 8. Esistono già progetti simili (LocalScore, llm-speed, InventiveHQ Lab, BenchLoop) da cui prendere il formato dei risultati.

---
## 2. Stato attuale del lab (fatti misurati, 5-6 novembre)
Configurazione migliore: Strata 0.2.11 (+ fork compilato da me), Qwen3.8-Flash-Next IQ3_XXS, ROUTE_PRIOR per richiesta, DFlash2, tail-skip attivo, router in BF16, GPU bloccata a 1650 MHz.

| Misura | Ieri (5/11 sera) | v3 finale |
|---|---:|---:|
| Codice vario, prompt brevi | 5,8 t/s | 33-53 t/s |
| Contesto reale 253K | 6,9 t/s | **30,4 t/s** |
| 284K (oltre il limite nativo, YaRN) | crash | 26,3 t/s |
| 420K (YaRN x2) | non provato | 22,4 t/s |
| Prefill 253K | 19,7 min | ~11 min (386 t/s) |
| Sessione agente 12 turni (nuovi token) | — | 22-34 t/s (prior 1,0) / 37-77 (1,5 + penalità) |

Intelligenza (stesse domande, in %):
| Configurazione | MMLU-Pro (200) | GSM8K | HumanEval |
|---|---:|---:|---:|
| Senza perdita | 69,0 | 90,0 | — |
| Standard (prior 1,0) | 70,0 | 90,0 | 96,3 |
| + thinking | ~70,5 (media 2 prove 72/69) | ~93 | — |
Tutto in `C:\Users\motti\llm\notte-20261105\STATO.md`, `DIARIO.md`, `REPORT-GIORNO-0611.md`.

Limiti ancora aperti: i prompt **nuovi e lunghi** (2-6K token) costano 35-55 s perché il percorso a blocchi rilegge tutti gli esperti dall'SSD; il prior 1,5 puro collassa in alcune sessioni lunghe da agente (con presence penalty 1,5 non è collassato in 4 prove su 4).

---
## 3. I modelli di cui hai parlato — cosa sono davvero

### 3.1 Onyx
Nessun modello. [onyx.app](https://onyx.app/insights/best-open-source-llms-2026) è una piattaforma open source (chat + connettori + agenti, self-hosted) che pubblica una classifica di LLM open (snapshot del 13 ottobre 2026: Kimi K3 primo, 2,8T parametri). La pubblica un'azienda che vende un prodotto concorrente: usarla come indicazione, non come verità.

### 3.2 Agents-A1 (InternScience / Shanghai AI Laboratory)
Fonti: [scheda Hugging Face](https://huggingface.co/InternScience/Agents-A1), [pagina progetto](https://internscience.github.io/Agents-A1/), [versione 4B](https://huggingface.co/InternScience/Agents-A1-4B).
- **35B MoE, ~3B attivi**, contesto 256K servito, Apache 2.0, tag `qwen3_5_moe` (famiglia Qwen3.5: la base non è dichiarata nella scheda, è una mia inferenza). Rilasciato il 26 giugno 2026; versione **4B densa** a metà luglio.
- **Come l'hanno reso intelligente** (da scheda): 3 stadi — fine-tuning supervisionato su tutti i domini; modelli "insegnante" per dominio; **distillazione on-policy multi-insegnante**. I dati sono costruiti da un'infrastruttura "conoscenza-azione" (azioni, osservazioni, esiti verificati). Non sono forniti volumi di dati né dettagli RL: sono nel report tecnico (arXiv 2606.30616, non letto).
- **Numeri dichiarati** (presi dagli autori; i valori degli altri modelli sono copiati dai loro report): BrowseComp 75,5 (Qwen3.6-35B-A3B: 67,9), GAIA 96,0 (78,6), IFEval 94,8, IFBench 80,6, SciCode 44,3, MLE-Lite 43,9.
- **Prova indipendente trovata** (poca): [WebBrain](https://www.webbrain.one/blog/agents-a1-webbrain-planner-benchmark), planner di browser, 100 casi: Agents-A1 88/100, Qwen3.6-35B-A3B 90/100, ma Agents-A1 molto più veloce (1,66 s contro 10,3 s). Nessun thread Reddit/HN trovato: **il parere della community è ancora molto sottile**.
- **Per noi**: dimensioni utili. Q4_K_M 21,2 GB; IQ2_M 11,7 GB ([KikoCis](https://huggingface.co/KikoCis/Agents-A1-IQ2_M-GGUF)); APEX-I-Mini 13,5 GB e Compact 16,5 GB ([mudler](https://huggingface.co/mudler/Agents-A1-APEX-GGUF)). La versione **4B Q4_K_M pesa 2,7 GB** e ha 123 mila download: probabile "worker veloce" per compiti semplici.

### 3.3 AREX-2 (BAAI)
Fonti: [scheda](https://huggingface.co/BAAI/AREX-2), [paper arXiv 2609.38288](https://arxiv.org/abs/2609.38288).
- **27B denso**, fine-tune di Qwen3.8-27B, Apache 2.0, BF16 (~54 GB). Un sito terzo stima ~17 GB per Q4_K_M: **non entra nei 12 GB**. Un GGUF ufficiale non l'ho trovato (la scheda indica 16 quantizzazioni da verificare).
- **Metodo** (da paper): un insegnante costruisce ambienti (repo GitHub e problemi di giudici online con funzione di punteggio) e genera traiettorie di **ore e centinaia di chiamate a strumenti**; si tengono solo le traiettorie con punteggio alto; il modello è addestrato per **imitazione** (SFT), con **loss applicata solo ai passi che fanno progredire** (non alle osservazioni degli strumenti né ai passi inutili come il polling ripetuto); il **budget di round viene dato all'agente, non appreso**.
- **Dove sta la forza**: al momento dell'esecuzione, in cicli **propone → misura → rifletti → rivedi**. Frontier-CS: 54,4 dopo 1 h, 65,9 dopo 2 h, 70,7 dopo 5 h; BrowseComp 64,8 a 47 turni → 84,0 a 143 turni; MLE-Lite 81,8 (il modello base senza skill: 28,8). Molti confronti sono riproduzioni degli autori.
- **Limiti ammessi o evidenti**: nessuna sezione limitazioni; domini di addestramento ristretti (ML engineering + algoritmi + ricerca); "non parte con il punteggio più alto"; i risultati dipendono dalle skill in contesto.
- **Per noi**: non è un modello da sostituire a Flash-Next, è una **ricetta di harness**: dare al modello un budget di round e un feedback misurabile. Possiamo provarla già oggi sulla nostra suite di codice.

### 3.4 "Qwen3.8-35B-A3B"
Non ufficiale. [Una guida di ottobre](https://insiderllm.com/guides/best-way-run-qwen-3-6-35b-moe-locally/) lo conferma. Sono distillazioni di terzi (`empero-ai/Qwen3.8-35B-A3B-Distill`, MTP/APEX, varianti abliterated, varianti coder). Il riferimento ufficiale della famiglia è **Qwen3.6-35B-A3B**: su una 3060 12 GB una guida terza riporta **38,9 t/s con 32 GB di DDR4** e llama.cpp Q4_K_M (con 16 GB di RAM andrebbe peggio).

### 3.5 Altri candidati emersi (guide terze, poco affidabili sui numeri)
- **gpt-oss-20b** (21B, ~3,6B attivi, ~12,8 GiB): consigliatissimo per 16 GB.
- **Gemma 4 26B-A4B** (MoE, ~4B attivi), **Laguna XS 2.1** (33B/3B, coding, luglio).
- **Qwen3.8-27B** denso (agosto): "miglior modello locale" per 24 GB; da noi, nella versione IQ2_S, faceva ~24 t/s.
- **Kimi K3, GLM-5.3, DeepSeek V4**: enormi, non praticabili.

### 3.6 Tabella di confronto (sulla nostra macchina)
| Modello | Totali / attivi | File utile | Entra? | Fiducia nei numeri |
|---|---|---|---|---|
| Flash-Next IQ3_XXS (nostro) | 125B / ~6B | 76 GB su SSD | sì, con streaming | **misurati da noi** |
| Agents-A1 35B-A3B | 35B / ~3B | IQ2_M 11,7 GB; Q4 21,2 GB | IQ2_M quasi in VRAM; Q4 con offload | dichiarati dagli autori |
| Agents-A1-4B | 4B denso | Q4 2,7 GB | sì, tutto in VRAM | dichiarati dagli autori |
| AREX-2 27B | 27B denso | ~17 GB (Q4, stima) | no (solo quant. molto bassa) | dichiarati, riproduzioni proprie |
| Qwen3.6-35B-A3B | 35B / ~3B | Q4 ~21 GB | offload | guide terze |
| gpt-oss-20b | 21B / ~3,6B | ~12,8 GiB | quasi | guide terze |

---
## 4. Come aumentare l'intelligenza senza addestrare (e cosa abbiamo misurato)
| Tecnica | Evidenza | Nostro risultato |
|---|---|---|
| Thinking con budget adeguato | molto diffusa | **+5,5 punti MMLU-Pro**, ma con budget x2 su blocchi da 20 domande = 0% di risposte |
| Loop esegui-testa-correggi (stile AREX-2) | paper AREX-2 | **da misurare** (esperimento E6) |
| Self-consistency (voto su N risposte) | classica | utile solo in matematica, +30% di tempo (grazie alla cache del prompt) |
| Sampling consigliato + presence penalty | schede Qwen/Agents-A1 (presence 1,1) | evita incagli e collassi; penalità 1,5 innocua su testo e benchmark |
| Prompt ripetuto | paper recenti | +2 punti incerti, +40% tempo: no |
| Alzare i top-k degli esperti | [Elastic MoE](https://arxiv.org/pdf/2509.21892), [RoE](https://arxiv.org/pdf/2509.17238) | la letteratura dice che **peggiora** senza addestramento; non provato |
| Steering con control vector | paper su modelli 7-8B | guadagni piccoli e variabili; priorità bassa col thinking |
| Ricalibrare il router dopo la quantizzazione (EAC-MoE, EAQuant, compensazione low-rank) | paper | richiedono i pesi BF16 (~250 GB): progetto lungo |
| Distillazione multi-insegnante (Agents-A1), SFT di traiettorie (AREX-2) | paper | non fattibile su una 3060: **si sfrutta il risultato scaricando i modelli già addestrati** |

Conclusione onesta: **fare un modello più intelligente di Flash-Next con la sola 3060 non è realistico**. È realistico (a) scegliere bene tra i modelli che altri hanno già addestrato, con un benchmark equo, e (b) aumentare la resa con il calcolo a tempo di risposta, che la velocità appena guadagnata rende conveniente.

---
## 5. Velocità: cosa abbiamo provato e cosa è rimasto
**Funziona** (cumulativo): tail-skip riattivato (+48%), DFlash2 (+28-52%), router preferenziale (ROUTE_PRIOR, 3,4x a 1,0 e 4x a 1,2), BF16 sui calcoli sensibili (gratis), `--short-read 1024` (dimezza l'attesa dei prompt corti), YaRN + KV K8/V4 per oltre 262K, prior per richiesta (fork) con proxy a tre modalità.
**Non funziona su Windows / 16 GB**: prefetch I/O (solo Linux), più thread I/O, chunk di prefill più grandi, ROUTE_RESIDENT, IQ2_XS (-6,5 punti per +27%), cache della tabella n-gram (Engram già dentro il modello, non è un collo di bottiglia), CPU share sul prefill, lookup più larghi.
**Resta**: (1) prompt nuovi lunghi 35-55 s → Linux o più RAM; (2) tetto ~43 t/s sulle modifiche di codice, limitato dal costo per passo del modello grande.
**Il fronte nuovo**: un **modello più piccolo che sta in VRAM** (Agents-A1-4B, Agents-A1 35B-A3B IQ2_M, gpt-oss-20b) cambia il quadro: niente streaming da SSD, velocità attese molto più alte (stima mia, da misurare: decine di t/s oltre i nostri 50). La domanda è quanta intelligenza si perde: è esattamente ciò che misura la Fabbrica.

---
## 6. Cosa dice la community (in sintesi onesta)
- Sui modelli nuovi la **community indipendente quasi non c'è ancora**: per Agents-A1 una sola prova indipendente trovata (WebBrain), per AREX-2 nessuna.
- Sui motori ci sono blog con numeri riportati dagli autori di Strata, Avalon e Maya (una fork di Strata orientata a GLM/DeepSeek). Avalon dichiara molto più di Strata, ma su GPU AMD con tanta RAM; **nessuna replica pubblica su una 3060 con 16 GB**.
- Il mio consiglio: trattare ogni numero non misurato da noi come ipotesi.

---
## 7. La "Fabbrica LLM": benchmark rapido e preciso
### 7.1 Obiettivo
Confrontare in modo equo qualsiasi modello e qualsiasi configurazione, con **tempo per giro basso**, per poter fare molti esperimenti.

### 7.2 Livelli
| Livello | Tempo | Contenuto |
|---|---|---|
| **0 Smoke** | ~3 min | Carica, 5 prompt, velocità decode e prima risposta, memoria usata |
| **1 Rapido** | ~12-15 min (stima) | tinyMMLU 100 + tinyGSM8k 100 + tinyARC 100, suite codice difficile (12) + HumanEval a campione, sonda "parole inventate", curva attesa/lunghezza |
| **2 Profondo** | ~45-60 min | HumanEval completo, MMLU-Pro 200, contesto lungo 64K/128K/250K con recupero di chiavi, sessione da agente a 12 turni x2, thinking acceso |
| **3 Notte** | ore | confronti appaiati ripetuti, 420K, stabilità |

### 7.3 Regole statistiche (imparate sul campo)
1. **Baseline ripetuta in ogni sessione**: due run identici differiscono di 1-3 punti.
2. **Confronto appaiato** sulle stesse domande (conteggio dei discordanti), non solo percentuali.
3. **Salvare l'esito di ogni domanda** (già fatto nel nostro runner).
4. **Sonda scrittura**: generare ~800 parole e contare le parole non presenti in un dizionario (una nuova metrica; serve perché le domande a lettere non vedono la degradazione).
5. **Risposte vuote contano come sbagliate**, risposte mancanti si riportano a parte.
6. **Greedy solo per velocità**; per la qualità sampling 0,6 + presence penalty (evita incagli).
7. **Mai promuovere un risultato da una sola prova** su sessioni da agente: servono almeno 2 prove.

### 7.4 Tecnica per stimare il benchmark pieno
[tinyBenchmarks](https://arxiv.org/html/2402.14992): 100 domande per benchmark scelte con teoria della risposta all'item (IRT), accuratezza stimata entro ~2 punti sul MMLU completo (dato degli autori). Esistono `tinyMMLU`, `tinyGSM8k`, `tinyHellaswag`, `tinyWinogrande`, `tinyTruthfulQA`, `tinyAI2_arc`, `tinyAlpacaEval`: **li ho già scaricati (MMLU, GSM8k, ARC) in `C:\Users\motti\llm\fabbrica\dati`**. Per stimare il punteggio "pieno" va usato il loro formato di prompt e il loro pacchetto Python.

### 7.5 Pipeline "fabbrica"
`scarica (con SHA e controllo spazio) → avvia il modello con il suo profilo → livello 0 → livello 1 → registra JSON (hardware, versione motore, flag, risultati per domanda) → cancella il modello`. Se lo spazio liberato scende sotto una soglia, si ferma. Un modello alla volta, perché C: ha 22 GB liberi.

---
## 8. Free lab su GitHub (Windows + Mac)
### 8.1 Struttura proposta
```
free-lab/
  README.md              La "bibbia": cosa funziona, cosa no, per fascia di hardware
  CONTRIBUTING.md        Come aggiungere un esperimento o un risultato
  notebook/              Una pagina per esperimento: ipotesi, setup, risultati, verdetto, link ai dati
  fabbrica/              Runner, scorer, dataset (solo riferimenti e hash), schema dei risultati
  ricette/windows-nvidia-12gb/   comandi e .bat pronti
  ricette/mac-apple-silicon/     comandi e script pronti
  risultati/             JSON per hardware (impronta della macchina, versioni, flag)
  modelli/               Catalogo: link, quantizzazione, dimensioni, checksum, licenza (mai i pesi)
```
### 8.2 Principi
Pubblicare **anche i risultati negativi** (ci hanno fatto risparmiare settimane); ogni numero con macchina, versione del motore, flag e data; ogni "miglioramento" con confronto appaiato; **niente chiavi o dati personali** nel repository (i pesi non si committano).
### 8.3 Da riusare
Formati di risultato e CI di [InventiveHQ Lab](https://inventivehq.com/blog/local-llm-benchmarks) (pull request validate dalla CI), [LocalScore](https://hn.jakechampion.name/reader/https://www.localscore.ai/blog), [llm-speed](https://llm-speed.pages.dev/about), [BenchLoop](https://awesome.ecosyste.ms/projects/github.com%2Foutsourc-e%2Fbench-loop). Nessun progetto trovato copre insieme velocità, intelligenza e ricette per chi ha poca RAM: **lo spazio è libero**.
### 8.4 Da fare prima di pubblicare
Controllare le licenze dei progetti che si citano o si copiano (Strata è MIT; per Avalon e per i modelli vanno lette le licenze una per una), scegliere un nome, e decidere con il tuo amico come condividere i modelli (solo link).
### 8.5 Lato Mac
Strata ha un motore Metal e ci sono altri progetti che trasmettono gli esperti dall'SSD su Mac (per esempio slotstream, in Swift/MLX): il tuo amico può contribuire con la fascia "Apple Silicon 16-64 GB". Va verificato quali di questi motori reggono i nostri benchmark.

---
## 9. Esperimenti: passati e prossimi
### 9.1 Passati (sintesi, verdetto)
Vedi la tabella completa in `notte-20261105\STATO.md`. In breve: **sì** a tail-skip, DFlash2, prior 1,0-1,5, BF16, short-read 1024, YaRN, presence penalty, thinking; **no** a prefetch I/O su Windows, thread I/O, chunk grandi, ROUTE_RESIDENT, IQ2_XS per il modello grande, cache n-gram, prompt ripetuto.

### 9.2 Prossimi, in ordine di priorità
| # | Esperimento | Perché | Costo | Criterio di successo |
|---|---|---|---|---|
| E1 | Costruire la Fabbrica livello 0-1 con tiny* + codice + sonda parole | tutto il resto dipende da questo | ~mezza giornata | due run della baseline entro ±2 punti |
| E2 | Liberare spazio (spostare su L: il modello IQ2_XS di 39 GB) | senza spazio non si provano modelli | 20 min | ≥60 GB liberi su C: |
| E3 | **Agents-A1-4B Q4 (2,7 GB)**: velocità e qualità sulla Fabbrica | tutto in VRAM, potenziale >100 t/s (stima) | download 3 GB | confronto con Flash-Next su livello 1 |
| E4 | **Agents-A1 35B-A3B IQ2_M (11,7 GB)** e Q4_K_M (21,2 GB) | MoE 3B attivi, 256K | download 12-21 GB | t/s e punteggi vs Flash-Next |
| E5 | Controlli: Qwen3.6-35B-A3B e gpt-oss-20b sulla stessa Fabbrica | riferimento del mercato | download ~20+13 GB | classifica velocità x intelligenza |
| E6 | **Loop genera-testa-correggi stile AREX-2** su Flash-Next v3 | unico metodo di intelligenza "gratis" con evidenza | mezza giornata | suite difficile 12/12 e HumanEval >96% con costo in tempo accettabile |
| E7 | Pipeline scarica-testa-cancella con guardia spazio | scalare il numero di modelli | 1 giornata | 5 modelli in una notte |
| E8 | Agents-A1-4B come "worker veloce" dietro il proxy (modello `flash-micro`) | usare il modello giusto per ogni compito | dopo E3 | stessa qualità su compiti semplici, 2-3x più veloce |
| E9 | Più avanti: RAM 32 GB / Linux / secondo NVMe / prior intelligente / abliterated | leve strutturali | hardware | dopo la Fabbrica, con numeri |

Idee da verificare (non sono promesse): usare Agents-A1-4B come bozzatore per Flash-Next (servirebbe lo stesso vocabolario del tokenizer: non verificato); la versione abliterated di Flash-Next pesa ~85 GB e non entra senza un secondo disco.

---
## 10. Avvertenze e cosa NON è verificato
- Nessun dato sulle prestazioni di Agents-A1 o AREX-2 sulla nostra macchina: sono tutti numeri degli autori o di blog.
- Il supporto di llama.cpp per Agents-A1 è **probabile** (la nostra build b10955 contiene `qwen35moe`), non provato.
- Le stime di velocità per i modelli piccoli sono mie e vanno misurate.
- I dati da guide "SEO" (ModelFit, MindStudio, insiderllm e simili) sono spesso incoerenti tra loro: usati solo come indizio.
- Per usare i test con la GPU serve che Blender e altre app non occupino VRAM (ora circa 4 GB risultano usati da altri programmi).

---
## 11. Fonti principali
[Onyx — classifica LLM open](https://onyx.app/insights/best-open-source-llms-2026) · [Agents-A1 (HF)](https://huggingface.co/InternScience/Agents-A1) · [Agents-A1-4B (HF)](https://huggingface.co/InternScience/Agents-A1-4B) · [WebBrain su Agents-A1](https://www.webbrain.one/blog/agents-a1-webbrain-planner-benchmark) · [AREX-2 (HF)](https://huggingface.co/BAAI/AREX-2) · [AREX-2 (arXiv 2609.38288)](https://arxiv.org/abs/2609.38288) · [tinyBenchmarks](https://arxiv.org/html/2402.14992) · [Elastic MoE](https://arxiv.org/pdf/2509.21892) · [Roster of Experts](https://arxiv.org/pdf/2509.17238) · [Qwen3.6-35B-A3B su 3060](https://insiderllm.com/guides/best-way-run-qwen-3-6-35b-moe-locally/) · [Strata](https://stratallm.org/) · [Avalon](https://github.com/freriadoc/Avalon) · [Project Maya](https://www.mindstudio.ai/blog/project-maya-fork-strata-llama-cpp) · [InventiveHQ Lab](https://inventivehq.com/blog/local-llm-benchmarks) · [LocalScore](https://hn.jakechampion.name/reader/https://www.localscore.ai/blog) · [llm-speed](https://llm-speed.pages.dev/about)
