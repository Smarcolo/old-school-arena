# Old School Arena

Gioca a Magic Old School 93/94 (regole Swedish) sul tuo PC contro un'avversaria AI, scrivendo i comandi in italiano.

## Avvio su Windows
1. Installa Python 3.11 o superiore (spunta "Add Python to PATH").
2. Fai doppio clic su `avvia.bat`. La prima volta installa tutto, poi apre il browser su http://127.0.0.1:8000.

## Avvio su Mac/Linux
```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.api.main:app
```

## Comandi
`pesca [n]`, `gioca <carta>`, `tappa <carta>`, `passa`, `mano`, `stato`, `vita <+/-n>`, `giudice <domanda>`, `aiuto`.
Puoi anche cliccare una carta in mano per giocarla o sul campo per tapparla.

## Cosa funziona oggi
- Partita a due con mazzi di prova, turni e fasi, una terra per turno, stap e pescata automatici.
- Sconfitta a 0 vita o pescando da grimorio vuoto; registro eventi.
- Avversaria base (gioca terre e passa).
- Giudice che cerca nei testi di `data/regole/`.

## Carte reali
`python -m app.cards.scryfall` importa le carte dei set ammessi da Scryfall nel database locale.

## Test
`python -m pytest -q`
