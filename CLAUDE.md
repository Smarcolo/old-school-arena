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
- `app/api/main.py` — FastAPI; serve anche il frontend statico in `app/web/`.
- `data/` — database, cache immagini, bulk Scryfall: generati, non versionati (vedi `.gitignore`).

## Regole del motore
- Ogni modifica allo stato passa da una funzione in `engine/azioni.py`, che **valida** (via `validazione.py`,
  sollevando `AzioneIllegale` con un motivo in italiano) e **scrive un Evento** nel registro. Mai modificare lo stato da fuori.
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
1. Pila e lancio magie (costi di mana, pool di mana, mana burn).
2. Combattimento: attaccanti, bloccanti, danno.
3. Editor mazzi con `valida_mazzo` e mazzi salvati.
4. AI che lancia magie e attacca.
5. Immagini delle carte in cache in `data/immagini/`.
