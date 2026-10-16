"""Sideboard dell'avversaria tra una partita e l'altra: mette dentro le risposte alle carte che ha visto giocare
e toglie le sue carte meno preziose (mai terre né carte fondamentali)."""
from collections import Counter

from app.engine.carte_implementate import CARTE_MIGLIORI, valore_carta


def _quante(viste: Counter, info: dict, condizione) -> int:
    return sum(n for nome, n in viste.items() if nome in info and condizione(info[nome]))


def scegli_cambi(sideboard: dict[str, int], mazzo: dict[str, int], viste_avversario: Counter,
                 info: dict) -> tuple[dict[str, int], dict[str, int]]:
    """info: {nome carta: Carta} per conoscere tipi e colori. Ritorna (entra, esce)."""
    blu = _quante(viste_avversario, info, lambda c: "U" in c.colori)
    rosso = _quante(viste_avversario, info, lambda c: "R" in c.colori)
    artefatti = _quante(viste_avversario, info, lambda c: "Artifact" in c.tipo)
    incantesimi = _quante(viste_avversario, info, lambda c: "Enchantment" in c.tipo)
    creature = _quante(viste_avversario, info, lambda c: c.is_creatura)
    utili = {
        "Red Elemental Blast": blu >= 3, "Blue Elemental Blast": rosso >= 3,
        "Disenchant": artefatti + incantesimi >= 2, "Shatter": artefatti >= 2,
        "Swords to Plowshares": creature >= 4, "Terror": creature >= 4, "Wrath of God": creature >= 6,
        "Counterspell": True, "Psionic Blast": creature >= 3,
    }
    entra: Counter = Counter()
    for nome, q in sideboard.items():
        if utili.get(nome):
            entra[nome] = q
    candidati = sorted((n for n, q in mazzo.items() for _ in range(q)
                        if n in info and not info[n].is_terra and n not in CARTE_MIGLIORI and n not in entra),
                       key=lambda n: valore_carta(info[n]))
    quanti = min(sum(entra.values()), len(candidati))
    esce = Counter(candidati[:quanti])
    while sum(entra.values()) > quanti:  # meno uscite possibili del previsto: entra solo quello che ci sta
        ultimo = next(reversed(entra))
        entra[ultimo] -= 1
        if entra[ultimo] == 0:
            del entra[ultimo]
    return dict(entra), dict(esce)
