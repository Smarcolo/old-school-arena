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


def mana_prodotto(carta: Carta) -> FonteMana | None:
    """La fonte di mana della carta (la prima abilità di mana riconosciuta), o None."""
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
    None se il costo non è pagabile."""
    simulata = dict(riserva)
    disponibili = sorted(fonti, key=lambda f: f.costo_d_uso)
    scelte: list[tuple[FonteMana, str]] = []

    def usa(fonte: FonteMana, colore: str) -> None:
        disponibili.remove(fonte)
        scelte.append((fonte, colore))
        simulata[colore] = simulata.get(colore, 0) + fonte.quantita

    for colore in COLORI:
        while simulata.get(colore, 0) < costo.get(colore, 0):
            fonte = next((f for f in disponibili if colore in f.colori), None)
            if fonte is None:
                return None
            usa(fonte, colore)
    while paga(simulata, costo) is None:
        if not disponibili:
            return None
        fonte = disponibili[0]
        usa(fonte, "C" if "C" in fonte.colori else fonte.colori[0])
    return scelte
