"""Regia della partita umano contro AI: esegue i comandi, fa agire l'AI quando ha la priorità e salta
in automatico le priorità dell'umano in cui non c'è niente da decidere."""
from app.ai import avversaria
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento, mulligan
from app.engine.abilita import analizza_abilita
from app.engine.stato import Partita
from app.engine.validazione import FASI_PRINCIPALI, puo_attivare, puo_lanciare
from app.engine.zone import Zona

MAX_PASSI = 1000  # protezione contro cicli infiniti


def ha_istantanei(partita: Partita, umano: str) -> bool:
    """Ha un istantaneo lanciabile o un'abilità attivabile adesso?"""
    g = partita.giocatore(umano)
    return (any(c.is_istantaneo and puo_lanciare(partita, umano, c) is None for c in g[Zona.MANO])
            or any(puo_attivare(partita, umano, c, ab) is None for c in g[Zona.CAMPO] for ab in analizza_abilita(c)))


def deve_fermarsi(partita: Partita, umano: str) -> bool:
    """Vedi sotto; in più: le scelte in sospeso dell'umano lo fermano sempre, e un innesco in cima alla pila
    lo ferma solo se può rispondere (altrimenti si risolve da solo, resta nel registro)."""
    if partita.scelta:
        return partita.scelta.giocatore == umano
    if partita.pila and partita.pila[-1].innesco and not ha_istantanei(partita, umano):
        return False
    return _deve_fermarsi(partita, umano)


def _deve_fermarsi(partita: Partita, umano: str) -> bool:
    """L'umano decide quando: c'è qualcosa in pila; è nelle fasi principali del suo turno; deve dichiarare
    attaccanti o bloccanti; i blocchi sono fatti e può ancora lanciare un istantaneo prima dei danni.
    Il resto (mantenimento, pescata, turno dell'AI a pila vuota) scorre da solo."""
    if partita.pila:
        return True
    if combattimento.deve_dichiarare_bloccanti(partita, umano) or combattimento.deve_dichiarare_attaccanti(partita, umano):
        return True
    comb = partita.combattimento
    if comb and comb.bloccanti_dichiarati and not comb.danni_inflitti and comb.attaccanti:
        return ha_istantanei(partita, umano)
    return partita.giocatore_attivo.nome == umano and partita.fase in FASI_PRINCIPALI


def avanza(partita: Partita, umano: str, ai: str, fino_a_fine_turno: bool = False) -> None:
    turno = partita.turno
    for _ in range(MAX_PASSI):
        if partita.vincitore:
            return
        if mulligan.in_corso(partita):
            if not partita.mulligan[ai].finito:
                avversaria.decidi_mulligan(partita, ai)
                continue
            return  # tocca all'umano
        if partita.scelta:
            if partita.scelta.giocatore != ai:
                return
            avversaria.decidi_scelta(partita, ai)
            continue
        if partita.giocatore_con_priorita.nome == ai:
            avversaria.agisci(partita, ai)
            continue
        if fino_a_fine_turno and partita.turno == turno:  # fa risolvere anche la pila, senza rispondere
            if combattimento.deve_dichiarare_attaccanti(partita, umano):
                combattimento.dichiara_attaccanti(partita, umano, [])
            azioni.passa_priorita(partita, umano)
            continue
        if deve_fermarsi(partita, umano):
            return
        azioni.passa_priorita(partita, umano)
    raise RuntimeError("la regia non riesce a far avanzare la partita")


def suggerimento(partita: Partita, umano: str) -> str:
    """Cosa può fare l'umano adesso, detto in una riga."""
    if partita.vincitore:
        return f"Partita finita: vince {partita.vincitore}."
    if partita.mulligan and not partita.mulligan[umano].finito:
        stato = partita.mulligan[umano]
        if stato.tenuta:
            n = stato.da_mettere_in_fondo
            return f"Scegli {n} {'carta' if n == 1 else 'carte'} da mettere in fondo al mazzo: «in fondo <carta>, <carta>»."
        return "Mano iniziale: «tengo» oppure «mulligan»."
    if partita.scelta and partita.scelta.giocatore == umano:
        if partita.scelta.tipo == "cerca":
            return f"{partita.scelta.dati['fonte']}: scegli una carta dal grimorio con «scelgo <carta>»."
        if partita.scelta.tipo == "scegli":
            return f"{partita.scelta.testo}: «scelgo <carta>»."
        if partita.scelta.tipo == "danni":
            return f"Banding: {partita.scelta.testo}. «danni su <creatura>» o «danni 2 su <creatura>, 1 su <altra>»."
        return f"Scegli: {partita.scelta.testo} «paga» o «non pago»."
    if combattimento.deve_dichiarare_bloccanti(partita, umano):
        nomi = ", ".join(c.nome for c in combattimento.attaccanti_in_campo(partita))
        return f"Ti attaccano con {nomi}: dichiara i bloccanti o «nessun blocco»."
    if combattimento.deve_dichiarare_attaccanti(partita, umano):
        return "Combattimento: «attacca con ...», «attacca con tutto» o «non attacco»."
    if partita.pila:
        cima = partita.pila[-1]
        if cima.controllore != umano:
            return f"{cima.controllore} ha messo in pila {cima.descrizione}: puoi rispondere o passare."
        return f"{cima.descrizione} è in pila: passa per farla risolvere."
    comb = partita.combattimento
    if comb and comb.bloccanti_dichiarati and not comb.danni_inflitti and comb.attaccanti:
        return "Blocchi fatti: puoi lanciare un istantaneo o attivare un'abilità prima dei danni, o passare."
    return ""


def esegui_comando(partita: Partita, umano: str, ai: str, testo: str, giudice=None) -> str:
    cmd = analizza(testo)
    if cmd.azione == "fineturno":
        if mulligan.in_corso(partita):
            return "Prima finisci il mulligan. " + suggerimento(partita, umano)
        if partita.giocatore_attivo.nome != umano:
            return "Non è il tuo turno."
        avanza(partita, umano, ai, fino_a_fine_turno=True)
        return " ".join(filter(None, ["Turno passato.", suggerimento(partita, umano)]))
    messaggio = esegui(partita, umano, cmd, giudice)
    avanza(partita, umano, ai)
    return " ".join(filter(None, [messaggio, suggerimento(partita, umano)]))
