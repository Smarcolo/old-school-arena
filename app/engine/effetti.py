"""Effetti di istantanei e stregonerie, registrati per nome della carta, e tipi di bersaglio.

Una funzione effetto riceve (partita, oggetto_pila) e applica l'effetto usando le funzioni di azioni.py.
`bersaglio` è una chiave di TIPI_BERSAGLIO, o None se la magia non bersaglia.
Finché una carta non è registrata qui, il motore non permette di lanciarla.
"""
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Effetto:
    funzione: Callable
    bersaglio: str | None = None
    max_bersagli: int = 1  # 0 = quanti se ne vuole (Fireball)
    costo_per_bersaglio: str = ""  # mana in più per ogni bersaglio oltre il primo


EFFETTI: dict[str, Effetto] = {}


def effetto(nome: str, bersaglio: str | None = None, max_bersagli: int = 1, costo_per_bersaglio: str = ""):
    def registra(funzione: Callable) -> Callable:
        EFFETTI[nome] = Effetto(funzione, bersaglio, max_bersagli, costo_per_bersaglio)
        return funzione
    return registra


def _creatura(o) -> bool:
    from app.engine.stato import Carta
    return isinstance(o, Carta) and o.is_creatura


def _di_colore(colore: str):
    from app.engine.stato import Carta, OggettoPila

    def controlla(partita, o, fonte) -> bool:
        if isinstance(o, OggettoPila):
            return o.abilita is None and o.innesco is None and colore in o.carta.colori
        return isinstance(o, Carta) and partita.trova_in_campo(o.id) is not None and colore in o.colori
    return controlla


def _controllore(partita, fonte) -> str | None:
    """Chi controlla la carta che bersaglia: il proprietario, o chi la tiene in mano o l'ha messa in pila."""
    from app.engine.zone import Zona
    if fonte is None:
        return None
    if fonte.proprietario:
        return fonte.proprietario
    for g in partita.giocatori:
        if fonte in g[Zona.MANO] or fonte in g[Zona.CAMPO]:
            return g.nome
    return next((o.controllore for o in partita.pila if o.carta is fonte), None)


def _tipi():
    from app.engine.stato import Carta, Giocatore, OggettoPila

    def in_campo(partita, o) -> bool:
        return isinstance(o, Carta) and partita.trova_in_campo(o.id) is not None

    return {
        "qualsiasi": ("una creatura o un giocatore", lambda p, o, f: isinstance(o, Giocatore) or (in_campo(p, o) and o.is_creatura)),
        "creatura": ("una creatura", lambda p, o, f: in_campo(p, o) and o.is_creatura),
        "giocatore": ("un giocatore", lambda p, o, f: isinstance(o, Giocatore)),
        "creatura_non_nera_non_artefatto": ("una creatura non nera e non artefatto", lambda p, o, f: in_campo(p, o)
                                            and o.is_creatura and "B" not in o.colori and "Artifact" not in o.tipo_attuale),
        "artefatto": ("un artefatto", lambda p, o, f: in_campo(p, o) and "Artifact" in o.tipo_attuale),
        "artefatto_o_incantesimo": ("un artefatto o un incantesimo", lambda p, o, f: in_campo(p, o)
                                    and ("Artifact" in o.tipo or "Enchantment" in o.tipo)),
        "terra": ("una terra", lambda p, o, f: in_campo(p, o) and o.is_terra),
        "permanente": ("un permanente", lambda p, o, f: in_campo(p, o)),
        "artefatto_creatura_o_terra": ("un artefatto, una creatura o una terra", lambda p, o, f: in_campo(p, o)
                                       and ("Artifact" in o.tipo or o.is_creatura or o.is_terra)),
        "assembly_worker": ("una creatura Assembly-Worker", lambda p, o, f: in_campo(p, o) and o.is_creatura
                            and "Assembly-Worker" in o.tipo_attuale),
        "magia": ("una magia in pila", lambda p, o, f: isinstance(o, OggettoPila) and o.abilita is None and o.innesco is None),
        "blu": ("una magia o un permanente blu", _di_colore("U")),
        "rosso": ("una magia o un permanente rosso", _di_colore("R")),
        "carta_tuo_cimitero": ("una carta nel tuo cimitero", lambda p, o, f: isinstance(o, Carta)
                               and (g := p.proprietario_cimitero(o)) is not None and g.nome == _controllore(p, f)),
    }


def nome_tipo(tipo: str) -> str:
    return _tipi()[tipo][0]


def bersaglio_legale(partita, tipo: str | None, rif: str, fonte=None) -> bool:
    """fonte: la carta che bersaglia; una creatura con protezione dal suo colore non è un bersaglio legale."""
    from app.engine.stato import Carta
    oggetto = partita.risolvi_bersaglio(rif)
    if oggetto is None or tipo is None or tipo not in _tipi():
        return False
    if isinstance(oggetto, Carta) and partita.trova_in_campo(oggetto.id) and oggetto.protetta_da(fonte):
        return False
    return bool(_tipi()[tipo][1](partita, oggetto, fonte))
