"""Effetti di istantanei e stregonerie, registrati per nome della carta.

Una funzione effetto riceve (partita, oggetto_pila) e applica l'effetto usando le funzioni di azioni.py.
`bersaglio` dice cosa può bersagliare: "qualsiasi" (creatura o giocatore), "creatura", "giocatore" o None.
Finché una carta non è registrata qui, il motore non permette di lanciarla.
"""
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Effetto:
    funzione: Callable
    bersaglio: str | None = None


EFFETTI: dict[str, Effetto] = {}


def effetto(nome: str, bersaglio: str | None = None):
    def registra(funzione: Callable) -> Callable:
        EFFETTI[nome] = Effetto(funzione, bersaglio)
        return funzione
    return registra


def bersaglio_legale(partita, tipo: str | None, rif: str, fonte=None) -> bool:
    """fonte: la carta che bersaglia; una creatura con protezione dal suo colore non è un bersaglio legale."""
    from app.engine.stato import Carta, Giocatore  # evita import circolari
    oggetto = partita.risolvi_bersaglio(rif)
    if oggetto is None or tipo is None:
        return False
    if isinstance(oggetto, Carta) and oggetto.protetta_da(fonte):
        return False
    if tipo == "giocatore":
        return isinstance(oggetto, Giocatore)
    if tipo == "creatura":
        return isinstance(oggetto, Carta) and oggetto.is_creatura
    return isinstance(oggetto, Giocatore) or oggetto.is_creatura
