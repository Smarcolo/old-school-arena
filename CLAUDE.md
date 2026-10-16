# Old School Arena — regole del progetto

App locale (Windows, avvio con `avvia.bat`) per giocare a Magic: The Gathering formato **Old School 93/94, regole Swedish**
contro un'avversaria AI, con un giudice che risponde sulle regole e comandi scritti in italiano.

## Lingua
- Interfaccia, messaggi, comandi, commenti e nomi di variabili/funzioni: **italiano**.
- Nomi delle carte e testo Oracle: **inglese**, come su Scryfall (sono le chiavi del database).

## Struttura
- `app/engine/` — stato della partita (`stato.py`), zone, azioni, validazione, event log. Nessuna dipendenza da API, AI o web.
- `app/cards/` — `carte_base.json` (dati di prova scritti a mano, sovrascritti dall'import Scryfall), database SQLite delle carte, import Scryfall, regole di costruzione mazzo Swedish (`regole_swedish.json`).
- `app/cards/mazzi.py` — mazzi salvati (tabella `mazzi`), formato testo «4 Nome carta» con riga «Sideboard»,
  analisi: regole Swedish, carte sconosciute, cosa il motore non sa ancora giocare, colori senza fonti, curva.
- `app/cards/immagini.py` — immagini scaricate da Scryfall alla prima richiesta (`/api/immagini/{nome}`), cache in
  `data/immagini/`. Senza rete l'app resta testuale; i fallimenti si ricordano fino al riavvio.
- `app/web/comune.js` — codice condiviso dalle pagine (anteprima immagine su elementi con `data-carta`).
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
  all'ultimo. Un attaccante bloccato non colpisce il giocatore (salvo travolgere).
- Parole chiave lette dal testo Oracle (`stato.parole_chiave_da_testo`, `Carta.ha("flying")`): volare, raggiungere,
  passaterre, difensore, cautela, rapidità, travolgere, attacca per primo (due passi di danno senza priorità in mezzo),
  protezione da un colore o dagli artefatti. Colori di una carta = simboli colorati del costo (`Carta.colori`); `Carta.protetta_da(fonte)`
  vale per bersagli (`bersaglio_legale(..., fonte)`), danni (prevenuti in `infliggi_danno` e in combattimento) e blocchi.
  Mancano: banding, protezione, abilità innescate.
- Abilità attivate (`engine/abilita.py`): riconosce dal testo Oracle «{costo}: <nome> gets +X/+Y until end of turn.»
  e «{costo}: <nome> deals N damage to any target / target creature / target player.». Vanno in pila
  (`OggettoPila.abilita`); la carta resta in campo. Una riga con frasi in più (es. Dragon Whelp) NON è riconosciuta:
  meglio non attivarla che attivarla male.
- Banding: `Combattimento.bande`; chi blocca un membro blocca tutta la banda (`dichiara_bloccanti` espande i blocchi).
  Nel passo di danno i danni dei bloccanti si calcolano una volta per bloccante. Con banding coinvolto la divisione
  la fa chi controlla la creatura con banding, in automatico (`combattimento._assorbitore`: prima una protetta, poi
  una che sopravvive, altrimenti tutto su quella che vale meno); in difesa niente travolgere oltre i bloccanti.
- Rigenerazione («{B}: Regenerate X.»): l'abilità dà uno scudo (`Carta.scudi_rigenerazione`) fino a fine turno.
  `azioni.distruggi` lo consuma: niente danni, tappata, fuori dal combattimento (un attaccante resta bloccato).
  Sacrificio e costituzione 0 usano `rigenerabile=False`.
- Incantesimi (`engine/statici.py`): aure «Enchant creature» con «Enchanted creature gets +X/+Y [and has ...]» o
  «has <parole chiave>», e globali «<Colore> creatures get +X/+Y.». Le aure si lanciano bersagliando una creatura
  (`Carta.attaccata_a`); i bonus statici vanno in `statico_forza/statico_costituzione/parole_extra`, ricalcolati
  da `statici.aggiorna` dentro `azioni_di_stato` (che ora ripete i controlli finché qualcosa cambia).
  Abilità di un'aura su «Enchanted creature» (Firebreathing): `AbilitaAttivata.su_incantata`.
- Abilità innescate (`engine/inneschi.py`): mantenimento / pescata / fase finale / entrata in campo, con le frasi
  elencate nel docstring. `azioni.metti_inneschi` le mette in pila a inizio fase (prima quelle dell'attivo).
  «that player» = chi era di turno quando è scattata (`OggettoPila.giocatore_del_turno`).
  «...unless you pay {..}» crea una `Partita.scelta`: finché non si risponde (`azioni.rispondi_scelta`, comandi
  «paga» / «non pago») nessuno può fare altro. L'AI decide in `avversaria.decidi_scelta`.
  La regia non ferma l'umano per un innesco in pila se non può rispondere.
- Regia: l'umano si ferma anche per dichiarare attaccanti/bloccanti e, dopo i blocchi, se ha un istantaneo lanciabile.
  `regia.suggerimento` aggiunge al messaggio cosa può fare adesso.
- Terminologia 93/94: "rimosse dal gioco" (non esilio), niente fase di cleanup separata. Mana burn: solo come opzione.
- Il motore è deterministico dato un `seed`: i test devono passare il seed.

## Giudice
- Risponde **solo** citando i testi indicizzati in `data/regole/`. Non inventare regole: se non c'è, lo dice.
- I file `data/regole/01-09` sono una bozza scritta da Claude (regole attuali + chiarimenti da MTG Wiki), da far
  verificare a Marco. Ricerca FTS5 con parole vuote italiane, sinonimi e ricerca per prefisso (`judge/indice.py`).
- Nell'interfaccia: riquadro «Giudice» accanto al registro, oppure il comando «giudice <domanda>».

## Regole Swedish
- `app/cards/regole_swedish.json` è una BOZZA (`"verificato": false`) compilata il 2026-10-16 da riepiloghi online:
  set Alpha, Beta, Unlimited, Summer Magic, Arabian Nights, Antiquities, Legends, The Dark; 7 bandite, 22 ristrette.
  Marco la confronta con il regolamento ufficiale e mette `"verificato": true`. Punto incerto: Shahrazad.
- Niente mana burn nel Swedish (confermato da Marco): `"mana_burn": false`; resta come opzione (`Partita.mana_burn`).

## Lavoro
- Test: `python -m pytest -q`. I test usano un database temporaneo (variabile `OSA_DATI`, impostata in `tests/conftest.py`). Ogni nuova regola del motore arriva con il suo test.
- Avvio sviluppo: `python -m uvicorn app.api.main:app --reload`.
- Import carte reali: `python -m app.cards.scryfall` (scarica il bulk Scryfall, pesante).

## Prossimi passi
1. Fatto: mana, pila, priorità, lancio creature, mana burn, debolezza da evocazione.
2. Fatto: istantanei con bersaglio (Lightning Bolt, Giant Growth), risposte in pila, AI che usa Bolt anche in risposta.
3. Fatto: combattimento con attaccanti, bloccanti (anche multipli), danni; AI che attacca e blocca.
4. Fatto: editor mazzi (`/mazzi.html`), mazzi salvati, scelta dei mazzi a inizio partita.
   Serve che Marco compili bandite/ristrette in `regole_swedish.json` per il controllo completo.
5. Fatto: volare, raggiungere, passaterre, difensore, cautela, rapidità, travolgere, attacca per primo.
   Fatto anche: abilità attivate semplici (pompaggio, danno) e innescate comuni.
   Fatto anche: rigenerazione, protezione da un colore e dagli artefatti, banding.
6. Fatto: immagini delle carte con anteprima al passaggio del mouse.
7. Fatto: aure e incantesimi globali.
8. Serve Marco: verificare `regole_swedish.json` e i testi in `data/regole/`; creare la repo GitHub.
9. Idee: divisione dei danni del banding scelta dal giocatore (oggi automatica), altre famiglie di effetti
   (distruggi bersaglio, contromagie, pescate), mulligan, salvataggio della partita.
