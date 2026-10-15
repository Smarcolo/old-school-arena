"""Zone di gioco. Nel 93/94 la zona d'esilio si chiama 'rimosse dal gioco'."""
from enum import Enum


class Zona(str, Enum):
    GRIMORIO = "grimorio"
    MANO = "mano"
    CAMPO = "campo"
    CIMITERO = "cimitero"
    RIMOSSE = "rimosse"
    PILA = "pila"
