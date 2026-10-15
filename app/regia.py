"""Regia della partita umano contro AI: esegue i comandi, fa agire l'AI quando ha la priorità e salta
in automatico le priorità dell'umano in cui non c'è niente da decidere."""
from app.ai import avversaria
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni
from app.engine.stato import Partita
from app.engine.validazione import FASI_PRINCIPALI

MAX_PASSI = 1000  # protezione contro cicli infiniti


def deve_fermarsi(partita: Partita, umano: str) -> bool:
    """L'umano decide quando c'è qualcosa in pila o nelle fasi principali del suo turno.
    Il resto (mantenimento, pescata, turno dell'AI a pila vuota) scorre da solo."""
    if partita.pila:
        return True
    return partita.giocatore_attivo.nome == umano and partita.fase in FASI_PRINCIPALI


def avanza(partita: Partita, umano: str, ai: str, fino_a_fine_turno: bool = False) -> None:
    turno = partita.turno
    for _ in range(MAX_PASSI):
        if partita.vincitore:
            return
        if partita.giocatore_con_priorita.nome == ai:
            avversaria.agisci(partita, ai)
            continue
        if fino_a_fine_turno and partita.turno == turno:  # fa risolvere anche la pila, senza rispondere
            azioni.passa_priorita(partita, umano)
            continue
        if deve_fermarsi(partita, umano):
            return
        azioni.passa_priorita(partita, umano)
    raise RuntimeError("la regia non riesce a far avanzare la partita")


def esegui_comando(partita: Partita, umano: str, ai: str, testo: str, giudice=None) -> str:
    cmd = analizza(testo)
    if cmd.azione == "fineturno":
        if partita.giocatore_attivo.nome != umano:
            return "Non è il tuo turno."
        avanza(partita, umano, ai, fino_a_fine_turno=True)
        return "Turno passato."
    messaggio = esegui(partita, umano, cmd, giudice)
    avanza(partita, umano, ai)
    return messaggio
