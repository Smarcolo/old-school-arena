"""Combattimento 93/94, semplificato: dichiarazione attaccanti, bloccanti, danni simultanei.

Flusso dentro la fase di combattimento:
1. Il giocatore attivo, con la priorità e la pila vuota, dichiara gli attaccanti (si tappano). Se entrambi
   passano senza attaccanti dichiarati, la fase finisce.
2. Quando entrambi passano dopo la dichiarazione, il difensore deve dichiarare i bloccanti (anche nessuno).
3. Quando entrambi passano dopo i blocchi, si infliggono i danni; dopo un altro doppio passaggio la fase finisce.
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
    if partita.ha_debolezza_da_evocazione(carta):
        return f"{carta.nome} è entrata in questo turno e non può attaccare"
    return None


def puo_bloccare(partita: Partita, giocatore: str, carta: Carta) -> str | None:
    if carta not in partita.giocatore(giocatore)[Zona.CAMPO] or not carta.is_creatura:
        return f"{carta.nome} non è una tua creatura in campo"
    if carta.tappata:
        return f"{carta.nome} è tappata e non può bloccare"
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


def dichiara_attaccanti(partita: Partita, giocatore: str, attaccanti: list[Carta]) -> None:
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
    for c in attaccanti:
        c.tappata = True
    comb.attaccanti = [c.id for c in attaccanti]
    comb.attaccanti_dichiarati = True
    partita.passaggi = 0
    nomi = ", ".join(c.nome for c in attaccanti) or "nessuna creatura"
    _log(partita, giocatore, "attacco", f"{giocatore} attacca con {nomi}")


def dichiara_bloccanti(partita: Partita, giocatore: str, blocchi: list[tuple[Carta, Carta]]) -> None:
    """blocchi: coppie (bloccante, attaccante). Più bloccanti possono bloccare lo stesso attaccante."""
    comb = partita.combattimento
    if comb is None or not comb.attesa_bloccanti:
        raise AzioneIllegale("ora non si dichiarano bloccanti")
    if partita.giocatore_attivo.nome == giocatore:
        raise AzioneIllegale("blocca il giocatore che difende")
    usati = set()
    for bloccante, attaccante in blocchi:
        if motivo := puo_bloccare(partita, giocatore, bloccante):
            raise AzioneIllegale(motivo)
        if bloccante.id in usati:
            raise AzioneIllegale(f"{bloccante.nome} può bloccare una sola creatura")
        if attaccante.id not in comb.attaccanti or not partita.trova_in_campo(attaccante.id):
            raise AzioneIllegale(f"{attaccante.nome} non sta attaccando")
        usati.add(bloccante.id)
    for bloccante, attaccante in blocchi:
        comb.blocchi.setdefault(attaccante.id, []).append(bloccante.id)
        _log(partita, giocatore, "blocco", f"{bloccante.nome} blocca {attaccante.nome}")
    if not blocchi:
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
    if not attaccanti_in_campo(partita) or not possibili_bloccanti(partita, difensore):
        dichiara_bloccanti(partita, difensore, [])


def infliggi_danni(partita: Partita) -> None:
    """Danni simultanei. L'attaccante bloccato divide i danni tra i bloccanti nell'ordine dato, dando a ognuno
    il danno letale prima di passare al successivo. Un attaccante bloccato non colpisce il giocatore,
    anche se i bloccanti sono già morti."""
    from app.engine.azioni import azioni_di_stato, modifica_vita
    comb = partita.combattimento
    attivo = partita.giocatore_attivo.nome
    difensore = partita.avversario_di(attivo).nome
    danni_creature: list[tuple[Carta, Carta, int]] = []  # (fonte, bersaglio, danni)
    danni_giocatore: list[tuple[Carta, int]] = []
    for attaccante in attaccanti_in_campo(partita):
        if attaccante.id in comb.blocchi:
            bloccanti = [t[1] for i in comb.blocchi[attaccante.id] if (t := partita.trova_in_campo(i))]
            restante = attaccante.forza_attuale
            for n, b in enumerate(bloccanti):
                quota = restante if n == len(bloccanti) - 1 else min(restante, max(0, b.costituzione_attuale - b.danni))
                danni_creature.append((attaccante, b, quota))
                restante -= quota
                danni_creature.append((b, attaccante, b.forza_attuale))
        else:
            danni_giocatore.append((attaccante, attaccante.forza_attuale))
    for fonte, bersaglio, n in danni_creature:
        if n > 0:
            bersaglio.danni += n
            _log(partita, fonte.proprietario, "danno", f"{fonte.nome} infligge {n} danni a {bersaglio.nome}")
    for fonte, n in danni_giocatore:
        if n > 0:
            modifica_vita(partita, difensore, -n, f"(attacco di {fonte.nome})")
    comb.danni_inflitti = True
    azioni_di_stato(partita)
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
