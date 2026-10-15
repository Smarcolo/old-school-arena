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
- `gioca <carta>`: gioca una terra o lancia una magia (paga il costo tappando le terre da solo).
- `tappa <carta>`: tappa per mana; `mana` mostra la riserva. Il mana non usato a fine fase fa perdere vita (mana burn).
- `passa`: passi la priorità. Se c'è qualcosa in pila si risolve, altrimenti si va alla fase dopo.
- `fine turno`: chiudi il turno (risolvendo quello che hai in pila).
- `mano`, `stato`, `pesca [n]`, `vita <+/-n>`, `giudice <domanda>`, `aiuto`.

Puoi anche cliccare una carta in mano per giocarla o sul campo per tapparla, e usare i pulsanti Passa e Fine turno.

## Cosa funziona oggi
- Partita a due con mazzi di prova, turni e fasi, una terra per turno, stap e pescata automatici.
- Mana, pila e priorità: si lanciano le creature, che entrano con debolezza da evocazione. C'è il mana burn.
- Sconfitta a 0 vita o pescando da grimorio vuoto; registro eventi.
- Avversaria base: gioca terre e lancia la creatura più cara che può pagare.
- Giudice che cerca nei testi di `data/regole/`.

## Carte reali
`python -m app.cards.scryfall` importa le carte dei set ammessi da Scryfall nel database locale.

## Test
`python -m pytest -q`
