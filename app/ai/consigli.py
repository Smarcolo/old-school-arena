"""Consigli di sideboard per l'umano tra una partita e l'altra: guardando le carte dell'avversaria viste finora
(non la sua lista intera, come in un torneo vero) propone cosa mettere dentro e cosa togliere, spiegando perché.

Le carte si giudicano dal testo Oracle (non da un elenco fisso), così funziona anche con carte nuove:
- odio per un colore («target blue spell», «red permanent», Circle of Protection: X) se l'avversaria gioca quel colore;
- distruzione di artefatti / incantesimi se ne ha mostrati;
- rimozioni per creature (Swords, Terror, danni, Wrath) se gioca molte creature; Terror no contro creature nere
  o artefatto;
- creature e contromagie contro un mazzo con poche creature (controllo).
Escono le carte che contro quell'avversaria servono meno (per gli stessi criteri al contrario), poi le meno preziose.
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from app.engine.carte_implementate import CARTE_MIGLIORI, valore_carta
from app.engine.stato import Carta

COLORI_INGLESE = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
NOMI_COLORE = {"W": "bianco", "U": "blu", "B": "nero", "R": "rosso", "G": "verde"}


@dataclass
class Situazione:
    """Cosa si è visto dell'avversaria."""
    colori: Counter = field(default_factory=Counter)  # colore -> carte viste di quel colore
    esempi: dict = field(default_factory=dict)  # categoria -> nomi visti
    artefatti: int = 0
    incantesimi: int = 0
    creature: int = 0
    creature_nere_o_artefatto: int = 0
    volanti: int = 0
    magie: int = 0  # istantanei e stregonerie

    def nota(self, categoria: str, nome: str) -> None:
        self.esempi.setdefault(categoria, [])
        if nome not in self.esempi[categoria]:
            self.esempi[categoria].append(nome)

    def come(self, categoria: str) -> str:
        nomi = self.esempi.get(categoria, [])
        return f" ({', '.join(nomi[:3])})" if nomi else ""


def leggi_avversaria(viste: Counter, info: dict[str, Carta]) -> Situazione:
    s = Situazione()
    for nome, n in viste.items():
        c = info.get(nome)
        if c is None or c.is_terra:
            continue
        for colore in c.colori:
            s.colori[colore] += n
            s.nota(colore, nome)
        if "Artifact" in c.tipo:
            s.artefatti += n
            s.nota("artefatti", nome)
        if "Enchantment" in c.tipo:
            s.incantesimi += n
            s.nota("incantesimi", nome)
        if c.is_creatura:
            s.creature += n
            s.nota("creature", nome)
            if "B" in c.colori or "Artifact" in c.tipo:
                s.creature_nere_o_artefatto += n
            if "flying" in c.testo.lower():
                s.volanti += n
        if "Instant" in c.tipo or "Sorcery" in c.tipo:
            s.magie += n
    return s


def _colori_odiati(c: Carta) -> set[str]:
    testo = c.testo.lower()
    trovati = {COLORI_INGLESE[m] for m in re.findall(r"target (white|blue|black|red|green) (?:spell|permanent)", testo)}
    trovati |= {COLORI_INGLESE[m] for m in re.findall(r"(white|blue|black|red|green) permanent", testo)}
    if m := re.match(r"Circle of Protection: (White|Blue|Black|Red|Green)", c.nome):
        trovati.add(COLORI_INGLESE[m.group(1).lower()])
    return trovati


def _ruoli(c: Carta) -> set[str]:
    """A cosa serve la carta contro un avversario."""
    testo = c.testo.lower()
    ruoli = set()
    if _colori_odiati(c):
        ruoli.add("colore")
    if re.search(r"destroy (?:target|all) artifacts?|artifact.{0,20}destroy", testo):
        ruoli.add("artefatti")
    if re.search(r"destroy (?:target|all) (?:artifact or )?enchantments?|target artifact or enchantment", testo):
        ruoli.add("incantesimi")
    if (re.search(r"(?:destroy|exile) (?:target|all) (?:nonblack |nonartifact |non-black )*creatures?", testo)
            or re.search(r"deals? \w+ damage to (?:any target|target creature|each creature)", testo)):
        ruoli.add("rimozione")
    if "counter target spell" in testo:
        ruoli.add("contromagia")
    if c.is_creatura:
        ruoli.add("minaccia")
    return ruoli


def _quanto_serve(c: Carta, s: Situazione) -> tuple[int, str]:
    """Punteggio (0 = inutile qui) e motivo, per una carta contro questa avversaria."""
    ruoli = _ruoli(c)
    migliore = (0, "")
    def prova(punti: int, motivo: str):
        nonlocal migliore
        if punti > migliore[0]:
            migliore = (punti, motivo)
    for colore in _colori_odiati(c):
        if s.colori[colore] >= 2:
            prova(3 * s.colori[colore], f"l'avversaria gioca {NOMI_COLORE[colore]}{s.come(colore)}")
    if "artefatti" in ruoli and s.artefatti >= 2:
        prova(3 * s.artefatti, f"ha artefatti importanti{s.come('artefatti')}")
    if "incantesimi" in ruoli and s.artefatti + s.incantesimi >= 2:
        prova(3 * (s.artefatti + s.incantesimi), f"ha artefatti o incantesimi{s.come('incantesimi') or s.come('artefatti')}")
    if "rimozione" in ruoli and s.creature >= 4:
        neri = c.nome == "Terror" and s.creature_nere_o_artefatto * 2 >= s.creature
        if not neri:
            prova(2 * s.creature, f"gioca molte creature{s.come('creature')}")
    if "minaccia" in ruoli and s.creature <= 2 and s.magie >= 3:
        prova(6, "contro un mazzo di controllo con poche creature servono minacce")
    if "contromagia" in ruoli and s.magie >= 4:
        prova(5, "gioca molte magie: meglio poterle neutralizzare")
    return migliore


def _quanto_e_debole(c: Carta, s: Situazione) -> tuple[int, str]:
    """Punteggio di inutilità (più alto = da togliere prima) e motivo."""
    ruoli = _ruoli(c)
    odiati = _colori_odiati(c)
    if odiati and not any(s.colori[x] for x in odiati):
        return 10, f"l'avversaria non gioca {'/'.join(NOMI_COLORE[x] for x in odiati)}"
    if ruoli & {"artefatti"} and not ruoli - {"artefatti", "incantesimi"} and s.artefatti == 0 and (
            "incantesimi" not in ruoli or s.incantesimi == 0):
        return 8, "non ha mostrato artefatti" + ("" if "incantesimi" not in ruoli else " né incantesimi")
    if ruoli == {"incantesimi"} and s.incantesimi == 0:
        return 8, "non ha mostrato incantesimi"
    if c.nome == "Terror" and s.creature and s.creature_nere_o_artefatto * 2 >= s.creature:
        return 9, "le sue creature sono nere o artefatto: Terror non le colpisce"
    if "rimozione" in ruoli and "minaccia" not in ruoli and s.creature <= 2:
        return 7, "ha pochissime creature: la rimozione resta in mano"
    if c.nome == "Moat" and s.creature and s.volanti * 2 >= s.creature:
        return 7, "le sue creature volano: Moat non le ferma"
    return 0, ""


def consiglia(sideboard: dict[str, int], mazzo: dict[str, int], viste_avversaria: Counter,
              info: dict[str, Carta]) -> dict:
    """{"entra": {nome: n}, "esce": {nome: n}, "motivi_entra": {nome: motivo}, "motivi_esce": {...},
    "visto": riassunto}. Scambi uno per uno: entrano tante carte quante ne escono."""
    s = leggi_avversaria(viste_avversaria, info)
    candidati_entra = []
    for nome, q in sideboard.items():
        if nome in info:
            punti, motivo = _quanto_serve(info[nome], s)
            if punti:
                candidati_entra += [(punti, nome, motivo)] * q
    candidati_entra.sort(key=lambda t: -t[0])
    candidati_esce = []
    for nome, q in mazzo.items():
        c = info.get(nome)
        if c is None or c.is_terra or nome in CARTE_MIGLIORI:
            continue
        debole, motivo = _quanto_e_debole(c, s)
        serve, _ = _quanto_serve(c, s)
        candidati_esce += [(debole, -serve, valore_carta(c), nome, motivo)] * q
    candidati_esce.sort(key=lambda t: (-t[0], -t[1], t[2]))
    entra, esce, motivi_entra, motivi_esce = Counter(), Counter(), {}, {}
    for (punti, nome_in, motivo_in), (debole, meno_serve, _, nome_out, motivo_out) in zip(candidati_entra, candidati_esce):
        if not debole and -meno_serve >= punti:
            break  # quello che uscirebbe serve quanto quello che entrerebbe: non conviene cambiare
        entra[nome_in] += 1
        esce[nome_out] += 1
        motivi_entra[nome_in] = motivo_in
        motivi_esce[nome_out] = motivo_out or "è la carta che serve meno in questo confronto"
    visto = []
    if s.colori:
        visto.append("colori: " + ", ".join(f"{NOMI_COLORE[c]} {n}" for c, n in s.colori.most_common()))
    visto.append(f"{s.creature} creature, {s.magie} istantanei/stregonerie, {s.artefatti} artefatti, {s.incantesimi} incantesimi")
    return {"entra": dict(entra), "esce": dict(esce), "motivi_entra": motivi_entra, "motivi_esce": motivi_esce,
            "visto": "; ".join(visto), "carte_viste": sum(viste_avversaria.values())}
