"""Regole di singole carte che non rientrano nelle famiglie generiche (abilità attivate, inneschi, statici).
Ogni regola è riconosciuta dalla frase Oracle esatta.

- Moat: «Creatures without flying can't attack.»
- Ali from Cairo: «Damage that would reduce your life total to less than 1 reduces it to 1 instead.»
- Juggernaut: «NAME attacks each combat if able.» · «NAME can't be blocked by Walls.»
- Kird Ape, Sedge Troll: «NAME gets +X/+Y as long as you control a Forest.»
- Sengir Vampire: «Whenever a creature dealt damage by NAME this turn dies, put a +1/+1 counter on NAME.»
- Triskelion: «NAME enters the battlefield with three +1/+1 counters on it.»
"""
import re

from app.engine.stato import Carta, Partita
from app.engine.zone import Zona

MOAT = "Creatures without flying can't attack."
ALI = "Damage that would reduce your life total to less than 1 reduces it to 1 instead."
_NUMERI = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def _righe(carta: Carta) -> list[str]:
    return [r.strip() for r in carta.testo.splitlines()]


def _nome(carta: Carta) -> str:
    return re.escape(carta.nome)


def _riga_con_nome(carta: Carta, modello: str) -> str:
    return modello.replace("NAME", carta.nome)


def moat_in_campo(partita: Partita) -> bool:
    return any(MOAT in _righe(c) for g in partita.giocatori for c in g[Zona.CAMPO])


def ali_protegge(partita: Partita, giocatore: str) -> bool:
    return any(ALI in _righe(c) for c in partita.giocatore(giocatore)[Zona.CAMPO])


def deve_attaccare(carta: Carta) -> bool:
    return _riga_con_nome(carta, "NAME attacks each combat if able.") in _righe(carta)


def non_bloccabile_da_muri(carta: Carta) -> bool:
    return _riga_con_nome(carta, "NAME can't be blocked by Walls.") in _righe(carta)


_CONDIZIONALE = r"^{nome} gets \+(\d+)/\+(\d+) as long as you control an? (Plains|Island|Swamp|Mountain|Forest)\.$"


def bonus_condizionale(partita: Partita, controllore: str, carta: Carta) -> tuple[int, int]:
    for riga in _righe(carta):
        if m := re.match(_CONDIZIONALE.format(nome=_nome(carta)), riga):
            terre = partita.giocatore(controllore)[Zona.CAMPO]
            if any(t.is_terra and m.group(3) in t.tipo for t in terre):
                return int(m.group(1)), int(m.group(2))
    return 0, 0


def cresce_quando_muore_un_danneggiato(carta: Carta) -> bool:
    return _riga_con_nome(carta, "Whenever a creature dealt damage by NAME this turn dies, put a +1/+1 counter on NAME.") \
        in _righe(carta)


def segnalini_iniziali(carta: Carta) -> int:
    for riga in _righe(carta):
        if m := re.match(rf"^{_nome(carta)} enters the battlefield with (\w+) \+1/\+1 counters? on it\.$", riga):
            return _NUMERI.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else 0)
    return 0


def riga_capita(carta: Carta, riga: str) -> bool:
    riga = riga.strip()
    return (riga in (MOAT, ALI)
            or riga in (_riga_con_nome(carta, "NAME attacks each combat if able."),
                        _riga_con_nome(carta, "NAME can't be blocked by Walls."),
                        _riga_con_nome(carta, "Whenever a creature dealt damage by NAME this turn dies, put a +1/+1 counter on NAME."))
            or bool(re.match(_CONDIZIONALE.format(nome=_nome(carta)), riga))
            or bool(re.match(rf"^{_nome(carta)} enters the battlefield with \w+ \+1/\+1 counters? on it\.$", riga)))
