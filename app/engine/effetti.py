"""Effetti di istantanei e stregonerie, registrati per nome della carta.

Una funzione effetto riceve (partita, oggetto_pila) e applica l'effetto usando le funzioni di azioni.py.
Finché una carta non è registrata qui, il motore non permette di lanciarla.
"""
from collections.abc import Callable

EFFETTI: dict[str, Callable] = {}


def effetto(nome: str):
    def registra(funzione: Callable) -> Callable:
        EFFETTI[nome] = funzione
        return funzione
    return registra
