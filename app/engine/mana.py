"""Costi di mana, riserva e pagamento. Colori: W U B R G, più C per il mana incolore."""
import re

from app.engine.stato import Carta

COLORI = "WUBRG"
TERRE_BASE = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
_ABILITA_MANA = re.compile(r"\{T\}: Add \{([WUBRGC])\}")


def analizza_costo(costo: str) -> dict[str, int]:
    """'{2}{G}{G}' -> {'generico': 2, 'G': 2}. X vale 0 finché non gestiamo le magie con X."""
    risultato = {"generico": 0}
    for simbolo in re.findall(r"\{([^}]+)\}", costo):
        if simbolo.isdigit():
            risultato["generico"] += int(simbolo)
        elif simbolo in COLORI:
            risultato[simbolo] = risultato.get(simbolo, 0) + 1
    return risultato


def mana_prodotto(carta: Carta) -> str | None:
    """Colore prodotto tappando la carta, se ha un'abilità di mana semplice."""
    for sottotipo, colore in TERRE_BASE.items():
        if "Basic Land" in carta.tipo and sottotipo in carta.tipo:
            return colore
    m = _ABILITA_MANA.search(carta.testo)
    return m.group(1) if m else None


def formatta(riserva: dict[str, int]) -> str:
    return "".join(f"{{{c}}}" * n for c, n in riserva.items() if n) or "vuota"


def paga(riserva: dict[str, int], costo: dict[str, int]) -> dict[str, int] | None:
    """Ritorna la riserva dopo il pagamento, o None se non basta. Il generico usa prima l'incolore,
    poi i colori più abbondanti."""
    resto = dict(riserva)
    for colore, n in costo.items():
        if colore == "generico":
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


def piano_pagamento(riserva: dict[str, int], fonti: list[tuple[Carta, str]], costo: dict[str, int]) -> list[Carta] | None:
    """Sceglie quali fonti di mana tappare per pagare il costo, usando prima la riserva.
    Per il generico preferisce le terre alle creature. None se il costo non è pagabile."""
    simulata = dict(riserva)
    disponibili = list(fonti)
    scelte: list[Carta] = []

    def usa(fonte: tuple[Carta, str]) -> None:
        disponibili.remove(fonte)
        scelte.append(fonte[0])
        simulata[fonte[1]] = simulata.get(fonte[1], 0) + 1

    for colore, n in costo.items():
        if colore == "generico":
            continue
        while simulata.get(colore, 0) < n:
            fonte = next((f for f in disponibili if f[1] == colore), None)
            if fonte is None:
                return None
            usa(fonte)
    disponibili.sort(key=lambda f: f[0].is_creatura)
    while paga(simulata, costo) is None:
        if not disponibili:
            return None
        usa(disponibili[0])
    return scelte
