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
- `tengo` / `mulligan` a inizio partita (mulligan London); dopo un mulligan, `in fondo <carte>` per scegliere
  quali carte mettere in fondo al mazzo (oppure i pulsanti e un clic sulle carte).
- `gioca <carta>`: gioca una terra o lancia una magia (paga il costo tappando le terre da solo).
- `gioca <carta> su <bersaglio>`: per le magie con bersaglio, es. `gioca giant growth su grizzly bears`,
  `gioca lightning bolt su avversaria`. Dall'interfaccia: clicchi la magia, poi il bersaglio.
- `attiva <carta> [su <bersaglio>]`: usa un'abilità della carta, es. `attiva shivan dragon`,
  `attiva prodigal sorcerer su avversaria`. Dall'interfaccia: clic sulla carta in campo.
- `danni su <creatura>` o `danni 2 su <creatura>, 1 su <altra>`: quando con il banding tocca a te dividere i danni.
- `concedo`: abbandoni la partita in corso.
- `paga` / `non pago`: quando una carta chiede di pagare o subire (es. Force of Nature nel tuo mantenimento).
- `tappa <carta>`: tappa per mana; `mana` mostra la riserva. Il mana non usato a fine fase si perde (niente mana burn nel Swedish).
- `passa`: passi la priorità. Se c'è qualcosa in pila si risolve, altrimenti si va alla fase dopo.
- `fine turno`: chiudi il turno (risolvendo quello che hai in pila).
- `attacca con <carte>` (separate da virgola o «e»), `attacca con tutto`, `non attacco`. Con «+» le creature
  attaccano in banda: `attacca con benalish hero + grizzly bears`.
- `blocca <attaccante> con <tua creatura>; <altro attaccante> con <altra creatura>`, `nessun blocco`.
  Dall'interfaccia: clicchi una tua creatura e poi l'attaccante, poi «Conferma blocchi».
- `mano`, `stato`, `pesca [n]`, `vita <+/-n>`, `giudice <domanda>`, `aiuto`.

Puoi anche cliccare una carta in mano per giocarla o sul campo per tapparla, e usare i pulsanti Passa e Fine turno.

## Mazzi
Dal tavolo, «Mazzi» apre l'editor: incolli o scrivi la lista («4 Lightning Bolt», una riga «Sideboard» per la
sideboard), cerchi le carte e le aggiungi con un clic. L'analisi dice se il mazzo è legale per le regole Swedish
caricate, quali carte il motore non sa ancora giocare e se mancano fonti di mana per qualche colore.
Prima di «Nuovo incontro» scegli il tuo mazzo e quello dell'avversaria.

## Incontri
Si gioca al meglio di tre: nella prima partita chi inizia si decide con il lancio della moneta, nelle successive
inizia chi ha perso. A fine partita il pulsante «Partita 2» (o 3) avvia la successiva; `concedo` abbandona la partita.

## Cosa funziona oggi
- Partita a due con mazzi di prova, turni e fasi, una terra per turno, stap e pescata automatici.
- Mana, pila e priorità: si lanciano le creature, che entrano con debolezza da evocazione. Niente mana burn, come nel Swedish (attivabile da `regole_swedish.json`).
- Istantanei con bersaglio: Lightning Bolt e Giant Growth, anche in risposta l'uno all'altro.
- Combattimento: attacchi, blocchi (anche più creature sullo stesso attaccante), danni, Giant Growth dopo i blocchi.
- Abilità attivate semplici: pompaggio (Shivan Dragon, Frozen Shade), danno (Prodigal Sorcerer) e rigenerazione
  (Drudge Skeletons, Uthden Troll, Will-o'-the-Wisp): lo scudo vale fino a fine turno e compare sulla carta.
- Abilità innescate comuni: Juzám Djinn, Serendib Efreet, Black Vise, Howling Mine, Ivory Tower, Ball Lightning,
  Force of Nature (con la scelta «paga o subisci»), effetti quando una creatura entra in campo.
- Incantesimi: aure sulle creature (Holy Strength, Unholy Strength, Giant Strength, Firebreathing, Flight) e
  globali (Crusade, Bad Moon). Si lanciano come le magie con bersaglio: clic sull'aura, poi sulla creatura.
- Abilità: volare, raggiungere, passaterre, difensore, cautela, rapidità, travolgere, attacca per primo,
  protezione da un colore (White Knight, Black Knight) e dagli artefatti, banding (Benalish Hero, Timber Wolves:
  quando tocca a te dividere i danni la partita si ferma e scegli tu; l'avversaria sceglie da sola).
- Editor dei mazzi con analisi e mazzi salvati.
- Immagini delle carte: passando il mouse su una carta compare l'immagine (scaricata da Scryfall la prima volta,
  poi tenuta in `data/immagini/`; senza internet si gioca lo stesso, solo senza immagini).
- Sconfitta a 0 vita o pescando da grimorio vuoto; registro eventi.
- Avversaria base: gioca terre, lancia la creatura più cara che può pagare, usa Lightning Bolt sulle tue creature o su di te, attacca quando non rischia, blocca con giudizio, usa Giant Growth e le abilità delle sue creature.
- Giudice (riquadro accanto al registro): risponde con le regole scritte in `data/regole/` (formato Swedish, turno,
  pila, combattimento, abilità, chiarimenti sui casi difficili). Sono una bozza da verificare.
- Regole Swedish in `app/cards/regole_swedish.json`: set ammessi, 7 carte bandite e 23 ristrette, niente mana burn,
  mulligan London.

## Carte reali
Le carte in `app/cards/carte_base.json` sono dati di prova scritti a mano: l'import da Scryfall le sovrascrive con i dati ufficiali.
`python -m app.cards.scryfall` importa le carte dei set ammessi da Scryfall nel database locale.

## Test
`python -m pytest -q`
