"""Abilità attivate lette dal testo Oracle. Forme riconosciute (il nome della carta può essere scritto per esteso):

- «{R}: Shivan Dragon gets +1/+0 until end of turn.»          -> pompa sé stessa
- «{T}: Prodigal Sorcerer deals 1 damage to any target.»       -> danno a un bersaglio
- «...deals N damage to target creature.» / «...target player.»

Le abilità di mana («{T}: Add {G}.») stanno in mana.py e non usano la pila. Tutto il resto per ora è ignorato.
"""
import re
from dataclasses import dataclass

from app.engine.stato import Carta

_RIGA = re.compile(r"^((?:\{[^}]+\})+):\s*(.+)$")
_POMPA = re.compile(r"^(?P<nome>.+) gets (?P<f>[+-]\d+)/(?P<c>[+-]\d+) until end of turn\.$")
_DANNO = re.compile(r"^(?P<nome>.+) deals (?P<n>\d+) damage to (?P<bersaglio>any target|target creature|target player)\.$")
_BERSAGLI = {"any target": "qualsiasi", "target creature": "creatura", "target player": "giocatore"}


@dataclass
class AbilitaAttivata:
    indice: int  # posizione tra le abilità attivate della carta
    testo: str
    costo_mana: str  # es. "{R}" o "" se costa solo {T}
    tappa: bool
    tipo: str  # "pompa" o "danno"
    forza: int = 0
    costituzione: int = 0
    danni: int = 0
    bersaglio: str | None = None


def _di_se_stessa(nome_nel_testo: str, carta: Carta) -> bool:
    return nome_nel_testo.lower() in (carta.nome.lower(), "this creature", "cardname", "~")


def analizza_abilita(carta: Carta) -> list[AbilitaAttivata]:
    trovate = []
    for riga in carta.testo.splitlines():
        m = _RIGA.match(riga.strip())
        if not m or m.group(2).startswith("Add {"):
            continue
        simboli = re.findall(r"\{[^}]+\}", m.group(1))
        tappa = "{T}" in simboli
        costo = "".join(s for s in simboli if s != "{T}")
        effetto = m.group(2).strip()
        base = dict(indice=len(trovate), testo=riga.strip(), costo_mana=costo, tappa=tappa)
        if (p := _POMPA.match(effetto)) and _di_se_stessa(p["nome"], carta):
            trovate.append(AbilitaAttivata(**base, tipo="pompa", forza=int(p["f"]), costituzione=int(p["c"])))
        elif (d := _DANNO.match(effetto)) and _di_se_stessa(d["nome"], carta):
            trovate.append(AbilitaAttivata(**base, tipo="danno", danni=int(d["n"]), bersaglio=_BERSAGLI[d["bersaglio"]]))
    return trovate


def riga_capita(carta: Carta, riga: str) -> bool:
    """True se la riga di testo è un'abilità attivata che il motore sa usare."""
    return any(a.testo == riga.strip() for a in analizza_abilita(carta))
