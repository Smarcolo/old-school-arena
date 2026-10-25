"""Costi di mana, fonti di mana, riserva e pagamento. Colori: W U B R G, più C per il mana incolore.

Fonti riconosciute:
- terre con tipi base nella riga del tipo (Forest, ma anche le doppie «Land — Plains Island»): uno dei loro colori;
- «{T}: Add {G}.» · «{T}: Add {C}{C}.» (Sol Ring) · «{T}: Add {U} or {W}.» · «{T}: Add one mana of any color.»;
- «{T}, Sacrifice NAME: Add three mana of any one color.» (Black Lotus);
- «Whenever NAME becomes tapped, it deals 1 damage to you.» (City of Brass) aggiunge il danno alla fonte.
"""
import re
from dataclasses import dataclass

from app.engine.stato import Carta

COLORI = "WUBRG"
TERRE_BASE = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
_RIGA_MANA = re.compile(r"^\(?\{T\}(?:, Sacrifice (?P<sacrifica>[^:]+))?: Add (?P<cosa>.+?)\.\)?$")
_DANNO_TAPPATA = re.compile(r"^Whenever (?P<nome>.+) becomes tapped, it deals (?P<n>\d+) damage to you\.$")
_NUMERI = {"one": 1, "two": 2, "three": 3}


@dataclass
class FonteMana:
    carta: Carta
    colori: str  # colori tra cui scegliere ("G", "UW", "WUBRG", "C")
    quantita: int = 1
    sacrifica: bool = False
    danno: int = 0

    @property
    def costo_d_uso(self) -> tuple:
        """Più è alto, più conviene tenerla per ultima."""
        return (self.sacrifica, self.danno, self.carta.is_creatura, len(self.colori))


def _cosa_produce(cosa: str) -> tuple[str, int] | None:
    simboli = re.findall(r"\{([WUBRGC])\}", cosa)
    if re.fullmatch(r"(\{[WUBRGC]\})+", cosa) and len(set(simboli)) == 1:
        return simboli[0], len(simboli)
    if re.fullmatch(r"\{[WUBRGC]\}(?:, \{[WUBRGC]\})*,? or \{[WUBRGC]\}", cosa):
        return "".join(simboli), 1
    if m := re.fullmatch(r"(one|two|three) mana of any (?:one )?color", cosa):
        return COLORI, _NUMERI[m.group(1)]
    return None


def riga_di_mana(riga: str) -> bool:
    riga = riga.strip()
    m = _RIGA_MANA.match(riga)
    return bool((m and _cosa_produce(m["cosa"])) or _DANNO_TAPPATA.match(riga))


_GIA_LETTE: dict[tuple, tuple | None] = {}


def mana_prodotto(carta: Carta) -> FonteMana | None:
    """La fonte di mana della carta (la prima abilità di mana riconosciuta), o None. La lettura del testo
    dipende solo da nome, testo e tipo: si ricorda."""
    chiave = (carta.nome, carta.testo, carta.tipo)
    if chiave not in _GIA_LETTE:
        fonte = _mana_prodotto(carta)
        _GIA_LETTE[chiave] = fonte and (fonte.colori, fonte.quantita, fonte.sacrifica, fonte.danno)
    letta = _GIA_LETTE[chiave]
    return FonteMana(carta, *letta) if letta else None


def _mana_prodotto(carta: Carta) -> FonteMana | None:
    danno = 0
    for riga in carta.testo.splitlines():
        if (d := _DANNO_TAPPATA.match(riga.strip())) and d["nome"] in (carta.nome, "it"):
            danno = int(d["n"])
    for riga in carta.testo.splitlines():
        m = _RIGA_MANA.match(riga.strip())
        if m and (prodotto := _cosa_produce(m["cosa"])):
            sacrifica = bool(m["sacrifica"])
            if sacrifica and m["sacrifica"] not in (carta.nome, "it"):
                continue
            return FonteMana(carta, prodotto[0], prodotto[1], sacrifica, danno)
    if carta.is_terra:
        colori = "".join(c for tipo, c in TERRE_BASE.items() if re.search(rf"\b{tipo}\b", carta.tipo.split("—")[-1]))
        if "—" in carta.tipo and colori:
            return FonteMana(carta, colori, 1, False, danno)
    return None


_COME_TERRE_AVVERSARIE = re.compile(r"^\{T\}: Add one mana of any color that a land an opponent controls could produce\.$")


def riga_da_terre_avversarie(riga: str) -> bool:
    return bool(_COME_TERRE_AVVERSARIE.match(riga.strip()))


def da_terre_avversarie(carta: Carta) -> bool:
    """Fellwar Stone: il colore dipende dalle terre dell'avversario (vedi fonte_in_partita)."""
    return "an opponent controls could produce" in carta.testo and any(
        riga_da_terre_avversarie(r) for r in carta.testo.splitlines())


def fonte_in_partita(carta: Carta, terre_avversarie: list[Carta]) -> FonteMana | None:
    """Come mana_prodotto, ma sa anche i colori che dipendono dalla partita (Fellwar Stone)."""
    if da_terre_avversarie(carta):
        colori = "".join(c for c in COLORI if any(c in f.colori for t in terre_avversarie
                                                   if t.is_terra and (f := mana_prodotto(t))))
        return FonteMana(carta, colori, 1, False, 0) if colori else None
    return mana_prodotto(carta)


def analizza_costo(costo: str) -> dict[str, int]:
    """'{2}{G}{G}' -> {'generico': 2, 'G': 2}; 'X' conta quante X ci sono (es. Fireball: {'X': 1})."""
    risultato = {"generico": 0}
    for simbolo in re.findall(r"\{([^}]+)\}", costo):
        if simbolo.isdigit():
            risultato["generico"] += int(simbolo)
        elif simbolo in COLORI or simbolo == "X":
            risultato[simbolo] = risultato.get(simbolo, 0) + 1
    return risultato


def con_x(costo: dict[str, int], x: int) -> dict[str, int]:
    """Il costo da pagare scelto X: ogni {X} diventa x mana generico."""
    risultato = {k: v for k, v in costo.items() if k != "X"}
    risultato["generico"] = risultato.get("generico", 0) + costo.get("X", 0) * x
    return risultato


def valore(costo: str) -> int:
    """Costo di mana convertito (X vale 0)."""
    c = analizza_costo(costo)
    return sum(v for k, v in c.items() if k != "X")


def formatta(riserva: dict[str, int]) -> str:
    return "".join(f"{{{c}}}" * n for c, n in riserva.items() if n) or "vuota"


def paga(riserva: dict[str, int], costo: dict[str, int]) -> dict[str, int] | None:
    """Ritorna la riserva dopo il pagamento, o None se non basta. Il generico usa prima l'incolore,
    poi i colori più abbondanti."""
    resto = dict(riserva)
    for colore, n in costo.items():
        if colore in ("generico", "X"):
            continue
        if resto.get(colore, 0) < n:
            return None
        resto[colore] -= n
    generico = costo.get("generico", 0)
    for colore in sorted(resto, key=lambda c: (c != "C", -resto[c])):
        presi = min(generico, resto[colore])
        resto[colore] -= presi
        generico -= presi
    return resto if generico == 0 else None


def piano_pagamento(riserva: dict[str, int], fonti: list[FonteMana], costo: dict[str, int]) -> list[tuple[FonteMana, str]] | None:
    """Sceglie quali fonti usare (e per quale colore) per pagare il costo, usando prima la riserva.
    Per i colori usa prima le fonti meno flessibili; Lotus, City of Brass e creature solo se servono.
    Se una scelta porta a un vicolo cieco (Tundra e Plateau per {W}{U}) torna indietro e prova un'altra fonte;
    tra fonti identiche ne prova una sola. None se il costo non è pagabile."""

    def generico(simulata: dict[str, int], disponibili: list[FonteMana]) -> list[tuple[FonteMana, str]] | None:
        simulata, scelte = dict(simulata), []
        for fonte in disponibili:
            if paga(simulata, costo) is not None:
                break
            colore = "C" if "C" in fonte.colori else fonte.colori[0]
            scelte.append((fonte, colore))
            simulata[colore] = simulata.get(colore, 0) + fonte.quantita
        return scelte if paga(simulata, costo) is not None else None

    def cerca(simulata: dict[str, int], disponibili: list[FonteMana]) -> list[tuple[FonteMana, str]] | None:
        colore = next((c for c in COLORI if simulata.get(c, 0) < costo.get(c, 0)), None)
        if colore is None:
            return generico(simulata, disponibili)
        provate = set()
        for fonte in disponibili:
            firma = (fonte.colori, fonte.quantita, fonte.costo_d_uso)
            if colore not in fonte.colori or firma in provate:
                continue
            provate.add(firma)
            resto = cerca({**simulata, colore: simulata.get(colore, 0) + fonte.quantita},
                          [f for f in disponibili if f is not fonte])
            if resto is not None:
                return [(fonte, colore)] + resto
        return None

    return cerca(dict(riserva), sorted(fonti, key=lambda f: f.costo_d_uso))
