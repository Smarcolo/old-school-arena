# Old School Arena — regole del progetto

App locale (Windows, avvio con `avvia.bat`) per giocare a Magic: The Gathering formato **Old School 93/94, regole Swedish**
contro un'avversaria AI, con un giudice che risponde sulle regole e comandi scritti in italiano.

## Lingua
- Interfaccia, messaggi, comandi, commenti e nomi di variabili/funzioni: **italiano**.
- Nomi delle carte e testo Oracle: **inglese**, come su Scryfall (sono le chiavi del database).

## Struttura
- `app/engine/` — stato della partita (`stato.py`), zone, azioni, validazione, event log. Nessuna dipendenza da API, AI o web.
- `app/cards/` — database SQLite delle carte, import Scryfall, regole di costruzione mazzo Swedish (`regole_swedish.json`).
- `app/judge/` — indice FTS5 dei testi in `data/regole/*.md` e risposte del giudice.
- `app/ai/` — avversaria. Usa solo le funzioni pubbliche di `engine`.
- `app/commands/` — `parser.py` (testo → Comando) ed `esegui.py` (Comando → azione + messaggio).
- `app/regia.py` — flusso umano contro AI: esegue i comandi, fa agire l'AI quando ha la priorità e salta le
  priorità dell'umano a pila vuota fuori dalle sue fasi principali.
- `app/api/main.py` — FastAPI; serve anche il frontend statico in `app/web/`.
- `data/` — database, cache immagini, bulk Scryfall: generati, non versionati (vedi `.gitignore`).

## Regole del motore
- Ogni modifica allo stato passa da una funzione in `engine/azioni.py`, che **valida** (via `validazione.py`,
  sollevando `AzioneIllegale` con un motivo in italiano) e **scrive un Evento** nel registro. Mai modificare lo stato da fuori.
- Priorità: chi lancia la mantiene; due passaggi di fila risolvono la cima della pila (poi priorità al giocatore
  attivo) o, a pila vuota, chiudono la fase. Le abilità di mana non usano la pila.
- Mana: `engine/mana.py`. A fine fase le riserve si svuotano con mana burn. `lancia` tappa da solo le fonti
  necessarie (`piano_pagamento`), usando prima la riserva e, per il generico, prima le terre delle creature.
- Istantanei e stregonerie si lanciano solo se il loro effetto è registrato con `@effetto("Nome Carta", bersaglio=...)`
  in `engine/carte_implementate.py`. I permanenti si lanciano sempre, ma le loro abilità (tranne quelle di mana) non sono attive.
- Bersagli: stringhe `"giocatore:<nome>"` o `"carta:<id>"`, risolte con `Partita.risolvi_bersaglio`. Se alla
  risoluzione il bersaglio non è più valido la magia non ha effetto. Dopo ogni risoluzione girano `azioni_di_stato`
  (creature con danni letali al cimitero). A fine turno danni e bonus "fino alla fine del turno" si azzerano.
- Combattimento (`engine/combattimento.py`): l'attivo dichiara gli attaccanti con priorità e pila vuota; al doppio
  passaggio il difensore dichiara i bloccanti (saltato se non può bloccare); al doppio passaggio successivo danni
  simultanei; poi la fase finisce. Più bloccanti sullo stesso attaccante: danno letale a ciascuno in ordine, il resto
  all'ultimo. Un attaccante bloccato non colpisce il giocatore. Niente ancora attacco improvviso, travolgere, volare.
- Regia: l'umano si ferma anche per dichiarare attaccanti/bloccanti e, dopo i blocchi, se ha un istantaneo lanciabile.
  `regia.suggerimento` aggiunge al messaggio cosa può fare adesso.
- Terminologia 93/94: "rimosse dal gioco" (non esilio), mana burn e interrupt esistono, niente fase di cleanup separata.
- Il motore è deterministico dato un `seed`: i test devono passare il seed.

## Giudice
- Risponde **solo** citando i testi indicizzati in `data/regole/`. Non inventare regole: se non c'è, lo dice.

## Regole Swedish
- `app/cards/regole_swedish.json` ha set ammessi e limiti; **liste bandite/ristrette vuote finché non le compila Marco
  dalla fonte ufficiale**. Non riempirle a memoria. I set ammessi sono da verificare sul regolamento in vigore.

## Lavoro
- Test: `python -m pytest -q`. Ogni nuova regola del motore arriva con il suo test.
- Avvio sviluppo: `python -m uvicorn app.api.main:app --reload`.
- Import carte reali: `python -m app.cards.scryfall` (scarica il bulk Scryfall, pesante).

## Prossimi passi
1. Fatto: mana, pila, priorità, lancio creature, mana burn, debolezza da evocazione.
2. Fatto: istantanei con bersaglio (Lightning Bolt, Giant Growth), risposte in pila, AI che usa Bolt anche in risposta.
3. Fatto: combattimento con attaccanti, bloccanti (anche multipli), danni; AI che attacca e blocca.
4. Editor mazzi con `valida_mazzo` e mazzi salvati.
5. Abilità chiave del 93/94: volare, attacco improvviso, travolgere, prima dei danni (first strike), banding (!).
6. Immagini delle carte in cache in `data/immagini/`.
