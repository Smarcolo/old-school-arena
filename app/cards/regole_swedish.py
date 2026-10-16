"""Regole di costruzione del mazzo (Swedish 93/94). I valori stanno in regole_swedish.json."""
import json
from dataclasses import dataclass, field
from pathlib import Path

FILE_REGOLE = Path(__file__).with_name("regole_swedish.json")
TERRE_BASE = {"Plains", "Island", "Swamp", "Mountain", "Forest"}


@dataclass
class RegoleMazzo:
    set_ammessi: list[str]
    minimo_carte_mazzo: int = 60
    massimo_sideboard: int = 15
    massimo_copie: int = 4
    bandite: list[str] = field(default_factory=list)
    ristrette: list[str] = field(default_factory=list)
    mana_burn: bool = True
    verificato: bool = False
    eccezioni_alle_regole_attuali: list[str] = field(default_factory=list)


def carica_regole(percorso: Path = FILE_REGOLE) -> RegoleMazzo:
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    dati.pop("_nota", None)
    return RegoleMazzo(**dati)


def valida_mazzo(mazzo: dict[str, int], sideboard: dict[str, int], regole: RegoleMazzo) -> list[str]:
    """Ritorna l'elenco dei problemi (vuoto se il mazzo è legale). Le copie si contano su mazzo + sideboard."""
    problemi = []
    totale = sum(mazzo.values())
    if totale < regole.minimo_carte_mazzo:
        problemi.append(f"il mazzo ha {totale} carte, minimo {regole.minimo_carte_mazzo}")
    if sum(sideboard.values()) > regole.massimo_sideboard:
        problemi.append(f"la sideboard supera {regole.massimo_sideboard} carte")

    copie: dict[str, int] = {}
    for lista in (mazzo, sideboard):
        for nome, n in lista.items():
            copie[nome] = copie.get(nome, 0) + n
    bandite = {n.lower() for n in regole.bandite}
    ristrette = {n.lower() for n in regole.ristrette}
    for nome, n in sorted(copie.items()):
        if nome in TERRE_BASE:
            continue
        if nome.lower() in bandite:
            problemi.append(f"{nome} è bandita")
        elif nome.lower() in ristrette and n > 1:
            problemi.append(f"{nome} è ristretta: massimo 1 copia (ne hai {n})")
        elif n > regole.massimo_copie:
            problemi.append(f"{nome}: massimo {regole.massimo_copie} copie (ne hai {n})")
    return problemi
