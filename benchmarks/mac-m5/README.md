# Banco di prova del Mac M5 24 GB (Lan), notte 10-11 novembre 2026

Script usati per i file `results/mac/2026-11-11-m5-*`. Tutto contro un `llama-server` locale, solo libreria standard
(i test di `duro` vogliono numpy: variabile `PYV`).

| File | Cosa fa |
|---|---|
| `notte.py` | coda di esperimenti: per ognuno avvia il server, esegue i test, scrive una riga JSON. `--dir code/` = coda continua che rilegge i file, non riprova i falliti, va in pausa sotto il 20% di batteria |
| `am.py` | lancia `windows-fabbrica/agente_mini.py` su Mac (`am.py control` verifica l'oracolo) |
| `duro_dev.py` | `duro.py` su un insieme di SVILUPPO (80 domande, seme 777) disgiunto dal campione standard `--n=15`: si regola su uno, si misura sull'altro |
| `tab.py` | tabella compatta dei risultati |
| `pack-v1.md` | knowledge pack v1 (6 regole) scritto guardando gli errori sul campione standard; da valutare solo su DEV (`--cheatsheet=`) |

Test di `notte.py`: `speed` (i 4 prompt di core-speed **una volta sola**, cosi ngram-mod non ripete una risposta gia vista),
`long` (prompt di ~15,5k token: lettura, poi 3 scritture con il prefisso in cache), `core` (tools/speedtest.py), `agente`,
`duro`, `durodev`, `agentemini`, `lungo`, `ufficiale`. I percorsi sono relativi: il repo va accanto alla cartella degli script
(`../LocaLLM-HUB`), i modelli in `modelli/`, i motori in `motore/llama-<build>/`.
