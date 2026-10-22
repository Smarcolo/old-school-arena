# Old School Arena — regole del progetto

App locale (Windows, avvio con `avvia.bat`) per giocare a Magic: The Gathering formato **Old School 93/94, regole Swedish**
contro un'avversaria AI, con un giudice che risponde sulle regole e comandi scritti in italiano.

## Lingua
- Interfaccia, messaggi, comandi, commenti e nomi di variabili/funzioni: **italiano**.
- Nomi delle carte e testo Oracle: **inglese**, come su Scryfall (sono le chiavi del database).

## Struttura
- `app/engine/` — stato della partita (`stato.py`), zone, azioni, validazione, event log. Nessuna dipendenza da API, AI o web.
- `app/cards/` — `carte_base.json` (dati di prova scritti a mano, sovrascritti dall'import Scryfall), database SQLite delle carte, import Scryfall, regole di costruzione mazzo Swedish (`regole_swedish.json`).
- `app/cards/tcdecks.py` — top 8 degli ultimi tornei Old School da TCDecks (format.php → deck.php?id → deck.php?id&iddeck).
  Parser volutamente generico (link e righe «4 Nome»), verificato solo su pagine di prova: la struttura reale di
  TCDecks non era raggiungibile dalla sessione in cui è stato scritto. Mazzi salvati con origine "tcdecks" e info
  (torneo, posizione, giocatore, url). `mazzi.scegli_mazzo_avversaria` sceglie a caso tra i giocabili con supporto
  del motore ≥ 80%. Riserva: import di un singolo mazzo dall'indirizzo.
- `app/cards/scryfall.py` — import dalla ricerca Scryfall (solo set ammessi, tutte le stampe, a pagine).
- `app/cards/mazzi.py` — mazzi salvati (tabella `mazzi`), formato testo «4 Nome carta» con riga «Sideboard»,
  analisi: regole Swedish, carte sconosciute, cosa il motore non sa ancora giocare, colori senza fonti, curva.
- `app/cards/immagini.py` — immagini scaricate da Scryfall alla prima richiesta (`/api/immagini/{nome}`), cache in
  `data/immagini/`. Senza rete l'app resta testuale; i fallimenti si ricordano fino al riavvio.
- `app/web/comune.js` — codice condiviso dalle pagine (anteprima immagine su elementi con `data-carta`).
- Tavolo: sta in una schermata (altezza carte `--h` in `stile.css` calcolata dall'altezza della finestra), giudice e
  registro in pannelli che si aprono dai pulsanti in alto, messaggi come avviso che sparisce, cimitero a richiesta.
  Immagini con `?v=1993` (`comune.js` `urlImmagine`) per non riusare quelle moderne nella cache del browser.
- Tavolo (`app/web/app.js`): carte come immagini fisse (`faccia`, ripiego `facciaTestuale`), banner `#turno` con
  fase spiegata (`fase()`), cosa fare (`cosaFare()`) e pulsanti del momento (`azioniTurno()`); mano in `#mano`.
  `vista` manda per ogni carta dell'umano `giocabile` (mano: lanciabile ora con almeno un bersaglio valido;
  campo: abilità attivabile) e per il combattimento i passi fatti. Immagini sempre con cornice 1993
  (`immagini.STAMPE_PREFERITE`, ricerca `frame:1993`).
- Deck builder (`mazzi.js`): modello `mazzo`/`side` in JS, testo sempre allineato (si salva quello);
  `analizza` manda `carte` (tipo, costo...) per raggruppare; `/api/carte` ha i filtri `colore` e `tipo`.
- Consiglio di sideboard (`ai/consigli.py`, `/api/partite/{id}/consiglio-sideboard`): giudica le carte dal testo
  Oracle (odio di colore, distruzione artefatti/incantesimi, rimozioni, minacce, contromagie) contro le carte
  dell'avversaria viste (`Incontro.viste`); pop-up a fine partita nel tavolo.
- `app/judge/` — indice FTS5 dei testi in `data/regole/*.md` e risposte del giudice.
- `app/ai/` — avversaria. Usa solo le funzioni pubbliche di `engine`.
- `app/commands/` — `parser.py` (testo → Comando) ed `esegui.py` (Comando → azione + messaggio).
- `app/regia.py` — flusso umano contro AI: esegue i comandi, fa agire l'AI quando ha la priorità e salta le
  priorità dell'umano a pila vuota fuori dalle sue fasi principali.
- `app/incontro.py` — incontro al meglio di tre: prima partita a moneta, poi inizia chi ha perso; mazzi nuovi
  a ogni partita dalle `Lista` (mazzo + sideboard) dell'incontro; `cambia_sideboard` (scambi uno per uno, solo tra
  le partite); `viste` = carte giocate da ciascuno. L'AI fa la sua sideboard in `ai/sideboard.py`. L'API tiene gli incontri (`partite: dict[id, Incontro]`), `/api/partite/{id}/prossima`.
- `app/salvataggio.py` — `Archivio`: incontri e tornei salvati con pickle in `data/salvataggi.sqlite` dopo ogni
  mossa (`main._salva`) e ricaricati all'avvio; gli incontri di un torneo stanno dentro il torneo. Per questo niente
  lambda negli oggetti salvati: i mazzi si costruiscono con `database.CostruttoreMazzi`. Un salvataggio illeggibile
  (codice cambiato) si salta. `/api/salvataggi` (GET, DELETE), menu «Riprendi» nel tavolo.
- `app/torneo.py` — top 8 simulata: 7 mazzi veri di un torneo (tcdecks.carica_torneo, per nome; senza rete i mazzi
  salvati) + il mazzo dell'umano al posto scelto; tabellone 1-8, 4-5, 2-7, 3-6; incontri AI contro AI giocati da
  `app/simulazione.py` (gioca_da_sola / gioca_incontro_da_solo); l'incontro dell'umano è un Incontro normale.
  Pagina `/torneo.html`; il tavolo riapre un incontro con `index.html?incontro=<id>`.
- `app/api/main.py` — FastAPI; serve anche il frontend statico in `app/web/`. Le richieste `/api/` si servono una
  alla volta (dipendenza globale `_serializza` con un lock): stato e connessione SQLite sono condivisi.
  Le liste dell'`Incontro` sono copie: la sideboard non cambia il mazzo del partecipante nei turni successivi.
- `app/avvio.py` — avvio: `python -m app.avvio` (solo questo PC) o `--rete` (`avvia_ipad.bat`: host 0.0.0.0, password
  in `data/password.txt` creata la prima volta, indirizzo per l'iPad). Il middleware `password_dalla_rete` in
  main.py chiede la password (HTTP Basic) a chi non arriva da 127.0.0.1, solo se `OSA_PASSWORD` è impostata.
  `comune.js`: pressione lunga = anteprima della carta (iPad), il clic dopo la pressione si annulla.
- «Annulla» (`main.storia`, `/api/partite/{id}/annulla`): prima di ogni comando dell'umano che cambia qualcosa si
  tiene l'incontro serializzato (pickle, max 15, solo in memoria); annullare lo rimette in `partite` (e nel torneo).
  La storia si svuota con la partita successiva e a incontro finito.
- `app/versione.py` — `VERSIONE` mostrata in alto nel tavolo (`/api/versione`): **aggiornarla a ogni consegna**.
  I file del sito si servono con `Cache-Control: no-cache` (`FileDelSito`) perché Safari non tenga i vecchi.
- `data/` — database, cache immagini, bulk Scryfall: generati, non versionati (vedi `.gitignore`).

## Regole del motore
- Ogni modifica allo stato passa da una funzione in `engine/azioni.py`, che **valida** (via `validazione.py`,
  sollevando `AzioneIllegale` con un motivo in italiano) e **scrive un Evento** nel registro. Mai modificare lo stato da fuori.
- Priorità: chi lancia la mantiene; due passaggi di fila risolvono la cima della pila (poi priorità al giocatore
  attivo) o, a pila vuota, chiudono la fase. Le abilità di mana non usano la pila.
- Mana: `engine/mana.py`. A fine fase le riserve si svuotano con mana burn. `lancia` tappa da solo le fonti
  necessarie (`piano_pagamento`), usando prima la riserva e, per il generico, prima le terre delle creature.
- Istantanei e stregonerie si lanciano solo se il loro effetto è registrato con `@effetto("Nome Carta", bersaglio=...)`
  in `engine/carte_implementate.py` (oggi 31 carte: Power 9 incluse, StP, Terror, Counterspell, Mana Drain,
  Disenchant, Fireball, Mind Twist, Demonic Tutor, Balance, Wrath...). I tipi di bersaglio sono in
  `effetti._tipi()` (creatura, magia in pila «pila:<id>», carta nel tuo cimitero «cimitero:<id>», terra, ...).
  Costi con X: `OggettoPila.x`, `mana.con_x`, comando «gioca fireball x=5 su avversaria».
  Più bersagli: `Effetto.max_bersagli` (0 = quanti si vuole) e `costo_per_bersaglio`; il costo totale è
  `validazione.costo_di_lancio`. Fireball divide X per difetto al lancio; comando «su avversaria e orso».
  Disintegrate: `Carta.disintegrata` (fino a fine turno) → niente rigenerazione e `distruggi` la rimuove dal gioco.
  Balance: un passo alla volta (`continua_balance`); l'umano sceglie con Scelta "scegli" e `seguito`
  (`carte_implementate.SEGUITI`), che fa riprendere l'effetto dopo ogni carta scelta.
- Mana (`engine/mana.py`): `FonteMana` con colori a scelta, quantità, sacrificio (Black Lotus), danno (City of Brass);
  terre doppie dai tipi base. `piano_pagamento` ritorna [(fonte, colore)]; prova le fonti meno flessibili e torna
  indietro se resta un colore scoperto (Tundra + Plateau per {W}{U}). Il mana si produce solo con la priorità o per
  pagare una propria Scelta "paga" (`puo_tappare`).
- Sconfitte: azione di stato (`azioni.controlla_sconfitte`, dentro `azioni_di_stato`, `passa_priorita`, `passa_fase`).
  `modifica_vita` e `pesca` (flag `Giocatore.pescato_da_vuoto`) non chiudono la partita da sole: così Earthquake o
  Timetwister che fanno perdere entrambi danno `vincitore == PAREGGIO`, che nell'incontro non conta (si rigioca,
  inizia di nuovo chi aveva iniziato). Nei test, dopo `modifica_vita` chiamare `azioni_di_stato`.
- Carte che lasciano il campo: `Carta.lascia_il_campo()` azzera tutto. Tipo corrente (Factory animata = artefatto):
  usare `tipo_attuale`, non `tipo`, per i controlli in campo.
- AI (`ai/avversaria.py`): gioca subito Mox/Sol Ring/Lotus; con Counterspell/Mana Drain in mano tiene {U}{U}
  (`lascia_contromagia`); attacca con tutto se è letale; Bolt in faccia quando basta; anima Mishra's Factory per
  attaccare/bloccare; Moat e The Abyss solo se convengono. Contro la versione precedente vince il 73% (100 partite
  con mazzi da torneo scambiati). Per confronti simili: due moduli avversaria su due giocatori, vedi simulazione.py.
- L'AI decide le magie in `ai/politiche.py` (POLITICHE per nome carta) e le abilità di utilità in `scegli_abilita`. I permanenti si lanciano sempre, ma le loro abilità (tranne quelle di mana) non sono attive.
- Bersagli: stringhe `"giocatore:<nome>"` o `"carta:<id>"`, risolte con `Partita.risolvi_bersaglio`. Se alla
  risoluzione il bersaglio non è più valido la magia non ha effetto. Dopo ogni risoluzione girano `azioni_di_stato`
  (creature con danni letali al cimitero). A fine turno danni e bonus "fino alla fine del turno" si azzerano.
- Combattimento (`engine/combattimento.py`): l'attivo dichiara gli attaccanti con priorità e pila vuota; al doppio
  passaggio il difensore dichiara i bloccanti (saltato se non può bloccare); al doppio passaggio successivo danni
  simultanei; poi la fase finisce. Più bloccanti sullo stesso attaccante: danno letale a ciascuno in ordine, il resto
  all'ultimo. Un attaccante bloccato non colpisce il giocatore (salvo travolgere).
- Parole chiave lette dal testo Oracle (`stato.parole_chiave_da_testo`, `Carta.ha("flying")`): volare, raggiungere,
  passaterre, difensore, cautela, rapidità, travolgere, attacca per primo (due passi di danno, con priorità in mezzo),
  protezione da un colore o dagli artefatti. Colori di una carta = simboli colorati del costo (`Carta.colori`); `Carta.protetta_da(fonte)`
  vale per bersagli (`bersaglio_legale(..., fonte)`), danni (prevenuti in `infliggi_danno` e in combattimento) e blocchi.
- Abilità attivate (`engine/abilita.py`): riconosce dal testo Oracle «{costo}: <nome> gets +X/+Y until end of turn.»
  e «{costo}: <nome> deals N damage to any target / target creature / target player.». Vanno in pila
  (`OggettoPila.abilita`); la carta resta in campo. Una riga con frasi in più (es. Dragon Whelp) NON è riconosciuta:
  meglio non attivarla che attivarla male.
- Banding: `Combattimento.bande`; chi blocca un membro blocca tutta la banda (`dichiara_bloccanti` espande i blocchi).
  Nel passo di danno i danni dei bloccanti si calcolano una volta per bloccante. Con banding coinvolto la divisione
  la fa chi controlla la creatura con banding: per chi è in `Partita.scelte_manuali` (l'umano, impostato dall'API)
  con una Scelta di tipo "danni" (`combattimento.assegna_danni`, comando «danni [n] su <creatura>»); per l'AI in
  automatico (`_assorbitore`). `Combattimento.assegnazioni` e `passi_fatti` permettono di riprendere il passo di
  danno dopo la scelta. In difesa niente travolgere oltre i bloccanti.
- Rigenerazione («{B}: Regenerate X.»): l'abilità dà uno scudo (`Carta.scudi_rigenerazione`) fino a fine turno.
  `azioni.distruggi` lo consuma: niente danni, tappata, fuori dal combattimento (un attaccante resta bloccato).
  Sacrificio e costituzione 0 usano `rigenerabile=False`.
- Incantesimi (`engine/statici.py`): aure «Enchant creature» con «Enchanted creature gets +X/+Y [and has ...]» o
  «has <parole chiave>», e globali «<Colore> creatures get +X/+Y.». Le aure si lanciano bersagliando una creatura
  (`Carta.attaccata_a`); i bonus statici vanno in `statico_forza/statico_costituzione/parole_extra`, ricalcolati
  da `statici.aggiorna` dentro `azioni_di_stato` (che ora ripete i controlli finché qualcosa cambia).
  Abilità di un'aura su «Enchanted creature» (Firebreathing): `AbilitaAttivata.su_incantata`.
- Carte di Millstone Dreams: Millstone (abilità «macina», `azioni.macina`), Mirror Universe («scambia_vita»,
  `solo_nel_mantenimento`, bersaglio «avversario»), Chaos Orb (il lancio fisico è reso come «distrugge un permanente
  a scelta, poi Chaos Orb»: `abilita.py`, tipo «chaos_orb»), Fellwar Stone (`mana.fonte_in_partita`: colori delle
  terre avversarie), Recall (`continua_recall`, `Effetto.rimuovi_dal_gioco`), Sylvan Library (innesco «sylvan»:
  pesca sempre 2 in più, poi per 2 carte pescate nel turno — `Carta.pescata_nel_turno` — «in_cima» o
  «tieni_pagando» 4 vita; scelte «azione:id» in `rispondi_scegli`), Field of Dreams (la vista mostra la cima dei
  grimori, `cima`), incantesimi del mondo (ne resta uno, il più recente, in `_un_giro_di_controlli`).
- Liste incollate da TCDecks: `mazzi.analizza_testo` salta «Tipo [N]», «Deck Name:», «X playing Y Position: N» e
  mette in sideboard le carte oltre il totale delle sezioni.
- Regole di singole carte (`engine/speciali.py`): Moat, Ali from Cairo, Juggernaut, Kird Ape/Sedge Troll,
  Sengir Vampire (innesco in pila, effetto «segnalino_su_se»), Triskelion. Segnalini +1/+1 (`Carta.segnalini`), animazione
  (`Carta.animata`, Mishra's Factory), danni tracciati per fonte (`danneggiata_da`), `danni_a_giocatore` /
  `danni_a_creatura` (Hypnotic Specter, Ali). Scelte tra carte: `azioni.scegli_o_decidi` (Scelta "scegli" per
  l'umano, `avversaria.scelta_automatica` per l'AI): The Abyss, Erhnam Djinn, Disrupting Scepter.
- Abilità innescate (`engine/inneschi.py`): mantenimento / pescata / fase finale / entrata in campo, con le frasi
  elencate nel docstring. `azioni.metti_inneschi` le mette in pila a inizio fase (prima quelle dell'attivo).
  «that player» = chi era di turno quando è scattata (`OggettoPila.giocatore_del_turno`).
  «...unless you pay {..}» crea una `Partita.scelta`: finché non si risponde (`azioni.rispondi_scelta`, comandi
  «paga» / «non pago») nessuno può fare altro. L'AI decide in `avversaria.decidi_scelta`.
  La regia non ferma l'umano per un innesco in pila se non può rispondere.
- Regia: l'umano si ferma anche per dichiarare attaccanti/bloccanti e, dopo i blocchi, se ha un istantaneo lanciabile;
  nel turno avversario anche dopo la dichiarazione degli attaccanti (prima dei blocchi) e nella fase finale, se ha
  qualcosa da usare (`ha_istantanei`). Quello che mette in pila l'umano si risolve da solo.
- Scarto a fine turno (`azioni._scarta_fino_a_sette`): l'AI scarta da sola, l'umano con Scelta "scegli" e seguito
  "fine_turno" che fa ripartire `passa_fase`. La vista dà per le carte dell'umano in campo `mana`/`mana_ora`:
  il tavolo fa tappare scegliendo il colore («tappa <id> per <colore>»), `lancia` usa prima la riserva.
  `regia.suggerimento` aggiunge al messaggio cosa può fare adesso.
- Terminologia 93/94: "rimosse dal gioco" (non esilio), niente fase di cleanup separata. Mana burn: solo come opzione.
- Il motore è deterministico dato un `seed`: i test devono passare il seed.

## Giudice
- Risponde **solo** citando i testi indicizzati in `data/regole/`. Non inventare regole: se non c'è, lo dice.
- I file `data/regole/01-09` sono una bozza scritta da Claude (regole attuali + chiarimenti da MTG Wiki), da far
  verificare a Marco. Ricerca FTS5 con parole vuote italiane, sinonimi e ricerca per prefisso (`judge/indice.py`).
- Nell'interfaccia: riquadro «Giudice» accanto al registro, oppure il comando «giudice <domanda>».

## Regole Swedish
- `app/cards/regole_swedish.json` compilato il 2026-10-16 da riepiloghi online e confermato da Marco:
  set Alpha, Beta, Unlimited, Summer Magic, Arabian Nights, Antiquities, Legends, The Dark; 7 bandite, 23 ristrette.
- Niente mana burn nel Swedish (confermato da Marco): `"mana_burn": false`; resta come opzione (`Partita.mana_burn`).
- Confermato da Marco il 2026-10-16: liste B&R (23 ristrette con Shahrazad, 7 bandite), set (con Summer Magic,
  senza Revised e Fallen Empires), mulligan London, chi inizia salta la prima pescata, incontri al meglio di tre
  (moneta, poi inizia chi perde), divisione del banding scelta dal giocatore, mano dell'avversaria nascosta.
- Mulligan (`engine/mulligan.py`): `Partita.mulligan` = nome -> StatoMulligan finché tutti non hanno tenuto e messo
  in fondo le carte; fino ad allora `_priorita` blocca ogni azione. Comandi «tengo», «mulligan», «in fondo <carte>».
  L'AI tiene con 2-5 terre (`avversaria.decidi_mulligan`).

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
8. Serve Marco: verificare i testi in `data/regole/`; creare la repo GitHub.
9. Idee: sideboard tra una partita e l'altra dell'incontro, altre famiglie di effetti (distruggi bersaglio,
   contromagie, pescate). Fatto: salvataggio di incontri e tornei.
