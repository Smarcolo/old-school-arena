"""Parser dei comandi in italiano. Trasforma il testo in un Comando; l'esecuzione sta in esegui.py."""
import re
from dataclasses import dataclass


@dataclass
class Comando:
    azione: str
    argomento: str = ""
    numero: int | None = None
    bersaglio: str = ""


SINONIMI = {
    "pesca": "pesca",
    "passa": "passa", "avanti": "passa", "ok": "passa",
    "mano": "mano", "mostra mano": "mano",
    "stato": "stato", "campo": "stato",
    "mana": "mana", "riserva": "mana",
    "fine turno": "fineturno", "fine": "fineturno",
    "non attacco": "nonattacco", "nessun attacco": "nonattacco", "niente attacco": "nonattacco",
    "tengo": "tengo", "tieni": "tengo", "tengo la mano": "tengo",
    "mulligan": "mulligan", "mulligo": "mulligan",
    "paga": "paga", "pago": "paga", "si": "paga", "sì": "paga",
    "non pago": "nonpago", "non pagare": "nonpago", "no": "nonpago",
    "nessun blocco": "nonblocco", "non blocco": "nonblocco", "niente blocchi": "nonblocco",
    "aiuto": "aiuto", "help": "aiuto", "?": "aiuto",
}

PATTERN = [
    (re.compile(r"^(?:gioca|metti)\s+(?:la\s+terra\s+|terra\s+)?(.+)$"), "gioca"),
    (re.compile(r"^(?:lancia|evoca)\s+(.+)$"), "lancia"),
    (re.compile(r"^(?:attiva|usa)\s+(.+)$"), "attiva"),
    (re.compile(r"^tappa\s+(.+)$"), "tappa"),
    (re.compile(r"^attacca(?:\s+con)?\s*(.*)$"), "attacca"),
    (re.compile(r"^blocca\s+(.+)$"), "blocca"),
    (re.compile(r"^(?:in fondo|metti in fondo|fondo)\s+(.+)$"), "infondo"),
    (re.compile(r"^pesca\s+(\d+)$"), "pesca"),
    (re.compile(r"^(?:vita|punti vita)\s+([+-]?\d+)$"), "vita"),
    (re.compile(r"^(?:giudice|regola|domanda)[:\s]+(.+)$"), "giudice"),
]


def analizza(testo: str) -> Comando:
    t = " ".join(testo.strip().lower().split())
    if t in SINONIMI:
        return Comando(SINONIMI[t])
    for regex, azione in PATTERN:
        m = regex.match(t)
        if m:
            valore = m.group(1)
            if azione in ("pesca", "vita"):
                return Comando(azione, numero=int(valore))
            if azione in ("gioca", "lancia", "attiva") and " su " in valore:
                carta, bersaglio = valore.split(" su ", 1)
                return Comando(azione, argomento=carta, bersaglio=bersaglio)
            return Comando(azione, argomento=valore)
    return Comando("sconosciuto", argomento=testo.strip())
