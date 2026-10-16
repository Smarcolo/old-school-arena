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
- `gioca <carta> su <bersaglio>`: per le magie con bersaglio, es. `gioca giant growth su grizzly bears`,
  `gioca lightning bolt su avversaria`. Dall'interfaccia: clicchi la magia, poi il bersaglio.
- `attiva <carta> [su <bersaglio>]`: usa un'abilità della carta, es. `attiva shivan dragon`,
  `attiva prodigal sorcerer su avversaria`. Dall'interfaccia: clic sulla carta in campo.
- `tappa <carta>`: tappa per mana; `mana` mostra la riserva. Il mana non usato a fine fase fa perdere vita (mana burn).
- `passa`: passi la priorità. Se c'è qualcosa in pila si risolve, altrimenti si va alla fase dopo.
- `fine turno`: chiudi il turno (risolvendo quello che hai in pila).
- `attacca con <carte>` (separate da virgola o «e»), `attacca con tutto`, `non attacco`.
- `blocca <attaccante> con <tua creatura>; <altro attaccante> con <altra creatura>`, `nessun blocco`.
  Dall'interfaccia: clicchi una tua creatura e poi l'attaccante, poi «Conferma blocchi».
- `mano`, `stato`, `pesca [n]`, `vita <+/-n>`, `giudice <domanda>`, `aiuto`.

Puoi anche cliccare una carta in mano per giocarla o sul campo per tapparla, e usare i pulsanti Passa e Fine turno.

## Mazzi
Dal tavolo, «Mazzi» apre l'editor: incolli o scrivi la lista («4 Lightning Bolt», una riga «Sideboard» per la
sideboard), cerchi le carte e le aggiungi con un clic. L'analisi dice se il mazzo è legale per le regole Swedish
caricate, quali carte il motore non sa ancora giocare e se mancano fonti di mana per qualche colore.
Prima di «Nuova partita» scegli il tuo mazzo e quello dell'avversaria.

## Cosa funziona oggi
- Partita a due con mazzi di prova, turni e fasi, una terra per turno, stap e pescata automatici.
- Mana, pila e priorità: si lanciano le creature, che entrano con debolezza da evocazione. C'è il mana burn.
- Istantanei con bersaglio: Lightning Bolt e Giant Growth, anche in risposta l'uno all'altro.
- Combattimento: attacchi, blocchi (anche più creature sullo stesso attaccante), danni, Giant Growth dopo i blocchi.
- Abilità attivate semplici: pompaggio (Shivan Dragon, Frozen Shade) e danno (Prodigal Sorcerer).
- Abilità: volare, raggiungere, passaterre, difensore, cautela, rapidità, travolgere, attacca per primo.
- Editor dei mazzi con analisi e mazzi salvati.
- Sconfitta a 0 vita o pescando da grimorio vuoto; registro eventi.
- Avversaria base: gioca terre, lancia la creatura più cara che può pagare, usa Lightning Bolt sulle tue creature o su di te, attacca quando non rischia, blocca con giudizio, usa Giant Growth e le abilità delle sue creature.
- Giudice che cerca nei testi di `data/regole/`.

## Carte reali
Le carte in `app/cards/carte_base.json` sono dati di prova scritti a mano: l'import da Scryfall le sovrascrive con i dati ufficiali.
`python -m app.cards.scryfall` importa le carte dei set ammessi da Scryfall nel database locale.

## Test
`python -m pytest -q`
