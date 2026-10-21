"""Effetti statici di incantesimi: aure e incantesimi globali. Riconosce solo frasi complete e note:

Aure («Enchant creature»):  «Enchanted creature gets +X/+Y.» · «Enchanted creature has flying.»
                            «Enchanted creature gets +X/+Y and has first strike.»
Globali:                    «White creatures get +1/+1.» (un colore)

`aggiorna(partita)` ricalcola da zero i bonus statici di tutte le creature: va chiamata dopo ogni cambiamento
del campo (lo fa `azioni.azioni_di_stato`).
"""
import re
from dataclasses import dataclass, field

from app.engine.stato import COLORI_INGLESE, Carta, Partita, parole_chiave_da_testo
from app.engine.zone import Zona

_BONUS = r"(?P<f>[+-]\d+)/(?P<c>[+-]\d+)"
_AURA = re.compile(rf"^Enchanted creature (?:gets {_BONUS}(?: and has (?P<p1>.+))?|has (?P<p2>.+))\.$", re.I)
_GLOBALE = re.compile(rf"^(?P<colore>White|Blue|Black|Red|Green) creatures get {_BONUS}\.$", re.I)


@dataclass
class EffettoStatico:
    testo: str
    tipo: str  # "aura" o "globale"
    forza: int = 0
    costituzione: int = 0
    parole: set[str] = field(default_factory=set)
    colore: str = ""


def _parole(testo: str | None) -> set[str] | None:
    """«flying and first strike» / «flying, first strike» -> parole chiave riconosciute, None se non tutte note."""
    if not testo:
        return set()
    parti = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", testo.lower()) if p.strip()]
    trovate = parole_chiave_da_testo(", ".join(parti))
    return trovate if len(trovate) == len(parti) else None


def is_aura_creatura(carta: Carta) -> bool:
    return "Aura" in carta.tipo and any(r.strip().lower() == "enchant creature" for r in carta.testo.splitlines())


def analizza_statici(carta: Carta) -> list[EffettoStatico]:
    if "Enchantment" not in carta.tipo:
        return []
    effetti = []
    for riga in carta.testo.splitlines():
        riga = riga.strip()
        if is_aura_creatura(carta) and (m := _AURA.match(riga)):
            parole = _parole(m["p1"] or m["p2"])
            if parole is not None:
                effetti.append(EffettoStatico(riga, "aura", int(m["f"] or 0), int(m["c"] or 0), parole))
        elif m := _GLOBALE.match(riga):
            effetti.append(EffettoStatico(riga, "globale", int(m["f"]), int(m["c"]), colore=COLORI_INGLESE[m["colore"].lower()]))
    return effetti


def riga_capita(carta: Carta, riga: str) -> bool:
    from app.engine import speciali
    riga = riga.strip()
    if riga.lower() == "enchant creature" and "Aura" in carta.tipo:
        return True
    if riga == "Players play with the top card of their libraries revealed.":  # Field of Dreams: lo mostra il tavolo
        return True
    if speciali.riga_capita(carta, riga):
        return True
    return any(e.testo == riga for e in analizza_statici(carta))


def aggiorna(partita: Partita) -> None:
    from app.engine import speciali
    creature = [c for g in partita.giocatori for c in g[Zona.CAMPO] if c.is_creatura]
    for g in partita.giocatori:
        for c in g[Zona.CAMPO]:
            if not c.is_creatura:  # anche una Mishra's Factory tornata terra perde i bonus di prima
                c.statico_forza = c.statico_costituzione = 0
                c.parole_extra = set()
                continue
            c.statico_forza, c.statico_costituzione = speciali.bonus_condizionale(partita, g.nome, c)
            c.parole_extra = {"forestwalk"} if c.passaforeste_fino_al_turno > partita.turno else set()
    for g in partita.giocatori:
        for incantesimo in g[Zona.CAMPO]:
            for e in analizza_statici(incantesimo):
                if e.tipo == "aura":
                    trovato = partita.trova_in_campo(incantesimo.attaccata_a) if incantesimo.attaccata_a else None
                    bersagli = [trovato[1]] if trovato and trovato[1].is_creatura else []
                else:
                    bersagli = [c for c in creature if e.colore in c.colori]
                for c in bersagli:
                    c.statico_forza += e.forza
                    c.statico_costituzione += e.costituzione
                    c.parole_extra |= e.parole
