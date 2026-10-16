"""Combattimento 93/94, semplificato: dichiarazione attaccanti, bloccanti, danni simultanei.

Flusso dentro la fase di combattimento:
1. Il giocatore attivo, con la priorità e la pila vuota, dichiara gli attaccanti (si tappano). Se entrambi
   passano senza attaccanti dichiarati, la fase finisce.
2. Quando entrambi passano dopo la dichiarazione, il difensore deve dichiarare i bloccanti (anche nessuno).
3. Quando entrambi passano dopo i blocchi, si infliggono i danni; dopo un altro doppio passaggio la fase finisce.

Abilità gestite: volare / raggiungere, passaterre, difensore, cautela, rapidità, travolgere, attacca per primo,
protezione da un colore (non bloccabile da quel colore, danni da quel colore prevenuti), banding.

Banding: si attacca in banda (creature con banding più al massimo una senza); chi blocca un membro blocca tutta la
banda. Se in un blocco c'è una creatura con banding, i danni della creatura avversaria li divide chi controlla quella
con banding, non chi controlla la creatura che li infligge. La divisione è automatica (vedi `_assorbitore`).
Con «attacca per primo» ci sono due passi di danno di fila, senza priorità in mezzo (semplificazione).
"""
from app.engine.stato import Carta, Combattimento, Fase, Partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def _log(partita, giocatore, tipo, descrizione, **dati):
    from app.engine.azioni import _log as log
    log(partita, giocatore, tipo, descrizione, **dati)


def puo_attaccare(partita: Partita, giocatore: str, carta: Carta) -> str | None:
    if carta not in partita.giocatore(giocatore)[Zona.CAMPO] or not carta.is_creatura:
        return f"{carta.nome} non è una tua creatura in campo"
    if carta.tappata:
        return f"{carta.nome} è tappata"
    if carta.ha("defender"):
        return f"{carta.nome} non può attaccare (difensore)"
    if partita.ha_debolezza_da_evocazione(carta):
        return f"{carta.nome} è entrata in questo turno e non può attaccare"
    return None


def puo_bloccare(partita: Partita, giocatore: str, carta: Carta) -> str | None:
    if carta not in partita.giocatore(giocatore)[Zona.CAMPO] or not carta.is_creatura:
        return f"{carta.nome} non è una tua creatura in campo"
    if carta.tappata:
        return f"{carta.nome} è tappata e non può bloccare"
    return None


def puo_bloccare_contro(partita: Partita, giocatore: str, bloccante: Carta, attaccante: Carta) -> str | None:
    if motivo := puo_bloccare(partita, giocatore, bloccante):
        return motivo
    if attaccante.protetta_da(bloccante):
        return f"{attaccante.nome} ha protezione dal colore di {bloccante.nome}: non può bloccarla"
    if attaccante.ha("flying") and not (bloccante.ha("flying") or bloccante.ha("reach")):
        return f"{attaccante.nome} vola: la blocca solo una creatura con volare o raggiungere"
    terre = {t for c in partita.giocatore(giocatore)[Zona.CAMPO] if c.is_terra for t in c.tipo.split()}
    for tipo in attaccante.passaterre:
        if tipo in terre:
            return f"{attaccante.nome} non si può bloccare: controlli una {tipo} e lei ha passa-{tipo.lower()}"
    return None


def possibili_attaccanti(partita: Partita, giocatore: str) -> list[Carta]:
    return [c for c in partita.giocatore(giocatore)[Zona.CAMPO] if c.is_creatura and puo_attaccare(partita, giocatore, c) is None]


def possibili_bloccanti(partita: Partita, giocatore: str) -> list[Carta]:
    return [c for c in partita.giocatore(giocatore)[Zona.CAMPO] if c.is_creatura and puo_bloccare(partita, giocatore, c) is None]


def attaccanti_in_campo(partita: Partita) -> list[Carta]:
    comb = partita.combattimento
    return [t[1] for i in (comb.attaccanti if comb else []) if (t := partita.trova_in_campo(i))]


def deve_dichiarare_attaccanti(partita: Partita, giocatore: str) -> bool:
    comb = partita.combattimento
    return (comb is not None and not comb.attaccanti_dichiarati and not partita.pila
            and partita.giocatore_attivo.nome == giocatore and bool(possibili_attaccanti(partita, giocatore)))


def deve_dichiarare_bloccanti(partita: Partita, giocatore: str) -> bool:
    comb = partita.combattimento
    return comb is not None and comb.attesa_bloccanti and partita.giocatore_attivo.nome != giocatore


def _valida_bande(attaccanti: list[Carta], bande: list[list[Carta]]) -> list[list[str]]:
    ids = {c.id for c in attaccanti}
    gia = set()
    risultato = []
    for banda in bande:
        if len(banda) < 2:
            continue
        if any(c.id not in ids for c in banda):
            raise AzioneIllegale("in una banda possono entrare solo creature che attaccano")
        if any(c.id in gia for c in banda):
            raise AzioneIllegale("una creatura può stare in una sola banda")
        if sum(not c.ha("banding") for c in banda) > 1:
            raise AzioneIllegale("in una banda al massimo una creatura può essere senza banding")
        gia |= {c.id for c in banda}
        risultato.append([c.id for c in banda])
    return risultato


def dichiara_attaccanti(partita: Partita, giocatore: str, attaccanti: list[Carta],
                        bande: list[list[Carta]] | None = None) -> None:
    comb = partita.combattimento
    if partita.fase != Fase.COMBATTIMENTO or comb is None:
        raise AzioneIllegale("si attacca solo nella fase di combattimento")
    if partita.giocatore_attivo.nome != giocatore:
        raise AzioneIllegale("puoi attaccare solo nel tuo turno")
    if comb.attaccanti_dichiarati:
        raise AzioneIllegale("hai già dichiarato gli attaccanti")
    if partita.pila or partita.giocatore_con_priorita.nome != giocatore:
        raise AzioneIllegale("serve la priorità con la pila vuota")
    if len({c.id for c in attaccanti}) != len(attaccanti):
        raise AzioneIllegale("ogni creatura può attaccare una volta sola")
    for c in attaccanti:
        if motivo := puo_attaccare(partita, giocatore, c):
            raise AzioneIllegale(motivo)
    bande_id = _valida_bande(attaccanti, bande or [])
    for c in attaccanti:
        if not c.ha("vigilance"):
            c.tappata = True
    comb.attaccanti = [c.id for c in attaccanti]
    comb.bande = bande_id
    comb.attaccanti_dichiarati = True
    partita.passaggi = 0
    nomi = ", ".join(c.nome for c in attaccanti) or "nessuna creatura"
    _log(partita, giocatore, "attacco", f"{giocatore} attacca con {nomi}")
    per_id = {c.id: c for c in attaccanti}
    for banda in bande_id:
        _log(partita, giocatore, "banda", "In banda: " + " + ".join(per_id[i].nome for i in banda))


def dichiara_bloccanti(partita: Partita, giocatore: str, blocchi: list[tuple[Carta, Carta]]) -> None:
    """blocchi: coppie (bloccante, attaccante). Più bloccanti possono bloccare lo stesso attaccante."""
    comb = partita.combattimento
    if comb is None or not comb.attesa_bloccanti:
        raise AzioneIllegale("ora non si dichiarano bloccanti")
    if partita.giocatore_attivo.nome == giocatore:
        raise AzioneIllegale("blocca il giocatore che difende")
    usati: dict[str, tuple] = {}  # bloccante -> banda che blocca
    unici = []
    for bloccante, attaccante in blocchi:
        if motivo := puo_bloccare_contro(partita, giocatore, bloccante, attaccante):
            raise AzioneIllegale(motivo)
        if attaccante.id not in comb.attaccanti or not partita.trova_in_campo(attaccante.id):
            raise AzioneIllegale(f"{attaccante.nome} non sta attaccando")
        banda = tuple(comb.banda_di(attaccante.id))
        if bloccante.id in usati:
            if usati[bloccante.id] != banda:
                raise AzioneIllegale(f"{bloccante.nome} può bloccare una sola creatura (o una sola banda)")
            continue  # stesso blocco ripetuto su un altro membro della stessa banda
        usati[bloccante.id] = banda
        unici.append((bloccante, attaccante))
    for bloccante, attaccante in unici:
        for membro in comb.banda_di(attaccante.id):
            if membro in comb.attaccanti and partita.trova_in_campo(membro):
                comb.blocchi.setdefault(membro, []).append(bloccante.id)
        in_banda = " (e tutta la sua banda)" if len(comb.banda_di(attaccante.id)) > 1 else ""
        _log(partita, giocatore, "blocco", f"{bloccante.nome} blocca {attaccante.nome}{in_banda}")
    if not unici:
        _log(partita, giocatore, "blocco", f"{giocatore} non blocca")
    comb.attesa_bloccanti = False
    comb.bloccanti_dichiarati = True
    partita.priorita = partita.attivo
    partita.passaggi = 0


def inizia_blocchi(partita: Partita) -> None:
    """Dopo il doppio passaggio con attaccanti dichiarati: tocca al difensore, salvo che non possa bloccare."""
    comb = partita.combattimento
    difensore = partita.avversario_di(partita.giocatore_attivo.nome).nome
    comb.attesa_bloccanti = True
    partita.priorita = partita.giocatori.index(partita.giocatore(difensore))
    partita.passaggi = 0
    blocco_possibile = any(puo_bloccare_contro(partita, difensore, b, a) is None
                           for a in attaccanti_in_campo(partita) for b in possibili_bloccanti(partita, difensore))
    if not blocco_possibile:
        dichiara_bloccanti(partita, difensore, [])


def _colpisce_in(carta: Carta, passo: str | None) -> bool:
    """passo None = unico passo di danno; "primo"/"normale" quando qualcuno attacca per primo."""
    return passo is None or carta.ha("first strike") == (passo == "primo")


def _assorbitore(fonte: Carta, candidate: list[Carta]) -> Carta:
    """Divisione con banding, decisa da chi controlla le candidate: tutti i danni di `fonte` su una sola creatura,
    scegliendo prima una protetta da fonte, poi una che sopravvive (la più robusta), altrimenti quella che vale meno."""
    protette = [c for c in candidate if c.protetta_da(fonte)]
    if protette:
        return protette[0]
    sopravvivono = [c for c in candidate if c.costituzione_attuale - c.danni > fonte.forza_attuale or c.scudi_rigenerazione]
    if sopravvivono:
        return max(sopravvivono, key=lambda c: c.costituzione_attuale - c.danni)
    return min(candidate, key=lambda c: (c.forza_attuale, c.costituzione_attuale))


def _passo_di_danno(partita: Partita, passo: str | None) -> None:
    from app.engine.azioni import azioni_di_stato, modifica_vita
    comb = partita.combattimento
    difensore = partita.avversario_di(partita.giocatore_attivo.nome).nome
    danni_creature: list[tuple[Carta, Carta, int]] = []  # (fonte, bersaglio, danni)
    danni_giocatore: list[tuple[Carta, int]] = []
    in_campo = attaccanti_in_campo(partita)

    # Danni degli attaccanti
    for attaccante in in_campo:
        if not _colpisce_in(attaccante, passo):
            continue
        bloccato = attaccante.id in comb.blocchi
        bloccanti = [t[1] for i in comb.blocchi.get(attaccante.id, []) if (t := partita.trova_in_campo(i))]
        restante = attaccante.forza_attuale
        if not bloccato:
            danni_giocatore.append((attaccante, restante))
        elif any(b.ha("banding") for b in bloccanti):
            danni_creature.append((attaccante, _assorbitore(attaccante, bloccanti), restante))
        else:
            travolge = attaccante.ha("trample")
            for n, b in enumerate(bloccanti):
                letale = max(0, b.costituzione_attuale - b.danni)
                ultimo = n == len(bloccanti) - 1
                quota = min(restante, letale) if (travolge or not ultimo) else restante
                danni_creature.append((attaccante, b, quota))
                restante -= quota
            if travolge and restante > 0:
                danni_giocatore.append((attaccante, restante))

    # Danni dei bloccanti: ognuno una volta sola, anche se blocca una banda
    for id_bloccante in comb.bloccanti():
        trovato = partita.trova_in_campo(id_bloccante)
        if not trovato or not _colpisce_in(trovato[1], passo):
            continue
        b = trovato[1]
        bloccati = [a for a in in_campo if id_bloccante in comb.blocchi.get(a.id, [])]
        if not bloccati:
            continue
        bersaglio = _assorbitore(b, bloccati) if any(a.ha("banding") for a in bloccati) else bloccati[0]
        danni_creature.append((b, bersaglio, b.forza_attuale))

    for fonte, bersaglio, n in danni_creature:
        if n > 0 and bersaglio.protetta_da(fonte):
            _log(partita, fonte.proprietario, "prevenuto", f"{bersaglio.nome} ha protezione: niente danni da {fonte.nome}")
        elif n > 0:
            bersaglio.danni += n
            _log(partita, fonte.proprietario, "danno", f"{fonte.nome} infligge {n} danni a {bersaglio.nome}")
    for fonte, n in danni_giocatore:
        if n > 0:
            modifica_vita(partita, difensore, -n, f"(attacco di {fonte.nome})")
    azioni_di_stato(partita)


def infliggi_danni(partita: Partita) -> None:
    """Danni simultanei. L'attaccante bloccato dà a ogni bloccante, in ordine, il danno letale prima di passare
    al successivo; l'ultimo prende il resto, salvo travolgere (il resto va al giocatore). Un attaccante bloccato
    senza travolgere non colpisce il giocatore, anche se i bloccanti sono già morti."""
    comb = partita.combattimento
    coinvolte = attaccanti_in_campo(partita) + [t[1] for i in comb.bloccanti() if (t := partita.trova_in_campo(i))]
    passi = ["primo", "normale"] if any(c.ha("first strike") for c in coinvolte) else [None]
    for passo in passi:
        _passo_di_danno(partita, passo)
        if partita.vincitore:
            break
    comb.danni_inflitti = True
    partita.priorita = partita.attivo
    partita.passaggi = 0


def dopo_doppio_passaggio(partita: Partita) -> bool:
    """Gestisce il doppio passaggio a pila vuota durante il combattimento.
    Ritorna True se ha fatto avanzare il combattimento, False se la fase deve finire."""
    comb = partita.combattimento
    if partita.fase != Fase.COMBATTIMENTO or comb is None:
        return False
    if comb.attaccanti and not comb.bloccanti_dichiarati:
        inizia_blocchi(partita)
        return True
    if comb.bloccanti_dichiarati and not comb.danni_inflitti:
        infliggi_danni(partita)
        return True
    return False


def inizia(partita: Partita) -> None:
    partita.combattimento = Combattimento()
