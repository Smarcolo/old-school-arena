"""Parser dei comandi in italiano. Trasforma il testo in un Comando; l'esecuzione sta in esegui.py."""
import re
from dataclasses import dataclass


@dataclass
class Comando:
    azione: str
    argomento: str = ""
    numero: int | None = None


SINONIMI = {
    "pesca": "pesca",
    "passa": "passa", "avanti": "passa", "ok": "passa",
    "mano": "mano", "mostra mano": "mano",
    "stato": "stato", "campo": "stato",
    "aiuto": "aiuto", "help": "aiuto", "?": "aiuto",
}

PATTERN = [
    (re.compile(r"^(?:gioca|metti)\s+(?:la\s+terra\s+|terra\s+)?(.+)$"), "gioca"),
    (re.compile(r"^tappa\s+(.+)$"), "tappa"),
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
            return Comando(azione, argomento=valore)
    return Comando("sconosciuto", argomento=testo.strip())
