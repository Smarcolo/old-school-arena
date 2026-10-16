"""Abilità innescate lette dal testo Oracle. Riconosce solo frasi complete e note: meglio non innescare che
innescare male. Forme gestite («NAME» è il nome della carta):

Momento:  «At the beginning of your upkeep, ...»            (mantenimento di chi la controlla)
          «At the beginning of each opponent's upkeep, ...» / «the chosen player's upkeep» (dell'avversario)
          «At the beginning of each player's upkeep, ...» / «each upkeep» (di ogni giocatore)
          «At the beginning of each player's draw step, ...» / «your draw step»
          «At the beginning of the end step, ...» / «your end step»
          «When NAME enters the battlefield, ...»
Condizione: «..., if NAME is untapped, ...» (controllata anche alla risoluzione)
Effetti:  «NAME deals N damage to you» · «you lose N life» · «you gain N life»
          «NAME deals X damage to that player, where X is the number of cards in their hand minus N» (Black Vise)
          «NAME deals X damage to that player, where X is N minus the number of cards in their hand» (The Rack)
          «you gain X life, where X is the number of cards in your hand minus N» (Ivory Tower)
          «that player draws an additional card» · «you draw a card» · «draw a card»
          «sacrifice NAME» · «sacrifice NAME unless you pay {..}» · «NAME deals N damage to you unless you pay {..}»
"""
import re
from dataclasses import dataclass

from app.engine.stato import Carta

_COSTO = r"((?:\{[^}]+\})+)"
_MOMENTI = [
    (r"your upkeep", "mantenimento", "tuo"),
    (r"each opponent's upkeep|the chosen player's upkeep", "mantenimento", "avversario"),
    (r"each player's upkeep|each upkeep", "mantenimento", "ogni"),
    (r"your draw step", "pescata", "tuo"),
    (r"each player's draw step", "pescata", "ogni"),
    (r"your end step", "finale", "tuo"),
    (r"the end step", "finale", "ogni"),
]


@dataclass
class Innesco:
    testo: str
    momento: str  # "mantenimento", "pescata", "finale", "entra"
    chi: str  # di chi deve essere il turno: "tuo", "avversario", "ogni" ("tuo" anche per «entra»)
    effetto: str
    n: int = 0
    costo: str = ""  # per «unless you pay»
    se_stappata: bool = False


def _effetti(nome: str) -> list[tuple[re.Pattern, str]]:
    n = rf"(?:{re.escape(nome)}|it)"
    return [
        (re.compile(rf"^{n} deals (\d+) damage to you unless you pay {_COSTO}$", re.I), "danno_te_salvo_paga"),
        (re.compile(rf"^sacrifice {n} unless you pay {_COSTO}$", re.I), "sacrifica_salvo_paga"),
        (re.compile(rf"^{n} deals (\d+) damage to you$", re.I), "danno_te"),
        (re.compile(r"^you lose (\d+) life$", re.I), "perdi_vita"),
        (re.compile(r"^you gain (\d+) life$", re.I), "guadagna_vita"),
        (re.compile(rf"^{n} deals X damage to that player, where X is the number of cards in their hand minus (\d+)$", re.I), "danno_mano_meno"),
        (re.compile(rf"^{n} deals X damage to that player, where X is (\d+) minus the number of cards in their hand$", re.I), "danno_meno_mano"),
        (re.compile(r"^you gain X life, where X is the number of cards in your hand minus (\d+)$", re.I), "vita_mano_meno"),
        (re.compile(r"^that player draws an additional card$", re.I), "pesca_quel_giocatore"),
        (re.compile(r"^(?:you )?draws? a card$", re.I), "pesca_tu"),
        (re.compile(rf"^sacrifice {n}$", re.I), "sacrifica"),
    ]


def _effetto(nome: str, testo: str) -> tuple[str, int, str] | None:
    for regex, tipo in _effetti(nome):
        if m := regex.match(testo):
            gruppi = m.groups()
            numero = next((int(g) for g in gruppi if g and g.isdigit()), 0)
            costo = next((g for g in gruppi if g and g.startswith("{")), "")
            return tipo, numero, costo
    return None


def analizza_inneschi(carta: Carta) -> list[Innesco]:
    trovati = []
    nome = re.escape(carta.nome)
    for riga in carta.testo.splitlines():
        riga = riga.strip()
        corpo = riga.rstrip(".")
        if m := re.match(rf"^When {nome} enters the battlefield, (.+)$", corpo, re.I):
            if e := _effetto(carta.nome, m.group(1)):
                trovati.append(Innesco(riga, "entra", "tuo", *e))
            continue
        m = re.match(r"^At the beginning of (.+?), (?:if (.+?) is untapped, )?(.+)$", corpo, re.I)
        if not m:
            continue
        momento = next(((mo, chi) for pattern, mo, chi in _MOMENTI if re.fullmatch(pattern, m.group(1), re.I)), None)
        condizione_ok = m.group(2) is None or m.group(2).lower() in (carta.nome.lower(), "it")
        if momento and condizione_ok and (e := _effetto(carta.nome, m.group(3))):
            trovati.append(Innesco(riga, momento[0], momento[1], *e, se_stappata=m.group(2) is not None))
    return trovati


def riga_capita(carta: Carta, riga: str) -> bool:
    riga = riga.strip()
    if re.fullmatch(rf"As {re.escape(carta.nome)} enters the battlefield, choose an opponent\.", riga, re.I):
        return True  # in due giocatori l'avversario è uno solo
    return any(i.testo == riga for i in analizza_inneschi(carta))
