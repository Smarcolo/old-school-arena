"""Quando e su cosa l'avversaria lancia le magie (e usa le abilità) diverse da creature, terre e Lightning Bolt.
Ogni politica riceve (partita, nome, carta) e ritorna (bersagli, x) se vuole lanciarla adesso, altrimenti None."""
from app.engine import mana
from app.engine.abilita import analizza_abilita
from app.engine.carte_implementate import CARTE_MIGLIORI, valore_carta
from app.engine.effetti import bersaglio_legale
from app.engine.stato import Carta, Fase, OggettoPila, Partita
from app.engine.validazione import FASI_PRINCIPALI, puo_attivare, puo_lanciare
from app.engine.zone import Zona

TERRE_BASE = {"Plains", "Island", "Swamp", "Mountain", "Forest"}


def _mia_principale(p: Partita, nome: str) -> bool:
    return p.giocatore_attivo.nome == nome and p.fase in FASI_PRINCIPALI and not p.pila


def _fine_turno_avversario(p: Partita, nome: str) -> bool:
    return p.giocatore_attivo.nome != nome and p.fase == Fase.FINALE and not p.pila


def _x_massimo(p: Partita, nome: str, carta: Carta, bersagli: list[str]) -> int:
    for x in range(20, -1, -1):
        if puo_lanciare(p, nome, carta, bersagli, x) is None:
            return x
    return -1


def _forza_totale(p: Partita, chi: str) -> int:
    return sum(c.forza_attuale for c in p.giocatore(chi)[Zona.CAMPO] if c.is_creatura)


def _migliore_creatura_avversaria(p: Partita, nome: str, fonte: Carta, tipo: str) -> Carta | None:
    avv = p.avversario_di(nome)
    candidate = [c for c in avv[Zona.CAMPO] if c.is_creatura and bersaglio_legale(p, tipo, f"carta:{c.id}", fonte)]
    return max(candidate, key=lambda c: (c.forza_attuale, c.costituzione_attuale)) if candidate else None


def contromagia(p: Partita, nome: str, carta: Carta):
    if not p.pila:
        return None
    cima = p.pila[-1]
    if cima.controllore == nome or cima.abilita or cima.innesco:
        return None
    rif = f"pila:{cima.id}"
    tipo = {"Counterspell": "magia", "Mana Drain": "magia", "Red Elemental Blast": "blu",
            "Blue Elemental Blast": "rosso"}[carta.nome]
    if not bersaglio_legale(p, tipo, rif, carta):
        return None
    mi_colpisce = any(rif_b.startswith("giocatore:" + nome) or
                      (rif_b.startswith("carta:") and (t := p.trova_in_campo(rif_b[6:])) and t[0].nome == nome)
                      for rif_b in cima.bersagli)
    if mana.valore(cima.carta.costo) >= 2 or mi_colpisce or cima.carta.nome in CARTE_MIGLIORI:
        return [rif], 0
    return None


def rimozione(p: Partita, nome: str, carta: Carta):
    tipo = "creatura_non_nera_non_artefatto" if carta.nome == "Terror" else "creatura"
    comb = p.combattimento
    if comb and comb.attaccanti and p.giocatore_attivo.nome != nome and not p.pila:
        in_campo = [p.trova_in_campo(i) for i in comb.attaccanti]
        attaccanti = [t[1] for t in in_campo if t and bersaglio_legale(p, tipo, f"carta:{t[1].id}", carta)]
        if attaccanti:
            return [f"carta:{max(attaccanti, key=lambda c: c.forza_attuale).id}"], 0
    if _mia_principale(p, nome) and (c := _migliore_creatura_avversaria(p, nome, carta, tipo)) and c.forza_attuale >= 2:
        return [f"carta:{c.id}"], 0
    return None


def distruggi_permanente(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    tipo = {"Disenchant": "artefatto_o_incantesimo", "Shatter": "artefatto", "Stone Rain": "terra",
            "Sinkhole": "terra", "Ice Storm": "terra"}[carta.nome]
    avv = p.avversario_di(nome)
    candidate = [c for c in avv[Zona.CAMPO] if bersaglio_legale(p, tipo, f"carta:{c.id}", carta)
                 and not (tipo == "terra" and c.nome in TERRE_BASE)]
    if not candidate:
        return None
    return [f"carta:{max(candidate, key=valore_carta).id}"], 0


def pescate(p: Partita, nome: str, carta: Carta):
    mano = len(p.giocatore(nome)[Zona.MANO]) - 1
    if carta.nome == "Ancestral Recall" and (_fine_turno_avversario(p, nome) or (_mia_principale(p, nome) and mano <= 2)):
        return [f"giocatore:{nome}"], 0
    if carta.nome == "Braingeyser" and (_fine_turno_avversario(p, nome) or _mia_principale(p, nome)):
        x = _x_massimo(p, nome, carta, [f"giocatore:{nome}"])
        return ([f"giocatore:{nome}"], x) if x >= 3 else None
    if carta.nome in ("Timetwister", "Wheel of Fortune") and _mia_principale(p, nome) and mano <= 1:
        return [], 0
    return None


def tutor_e_turni(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    if carta.nome == "Time Walk" and p.fase == Fase.PRINCIPALE_1:
        return [], 0
    if carta.nome == "Demonic Tutor":
        return [], 0
    if carta.nome == "Regrowth":
        cimitero = [c for c in p.giocatore(nome)[Zona.CIMITERO] if not c.is_terra]
        if cimitero:
            return [f"cimitero:{max(cimitero, key=valore_carta).id}"], 0
    return None


def mind_twist(p: Partita, nome: str, carta: Carta):
    avv = p.avversario_di(nome).nome
    if _mia_principale(p, nome) and len(p.giocatore(avv)[Zona.MANO]) >= 2:
        x = min(_x_massimo(p, nome, carta, [f"giocatore:{avv}"]), len(p.giocatore(avv)[Zona.MANO]))
        if x >= 2:
            return [f"giocatore:{avv}"], x
    return None


def danni_x(p: Partita, nome: str, carta: Carta):
    """Fireball / Psionic Blast: alla faccia se è letale, altrimenti sulla creatura migliore che muore."""
    avv = p.avversario_di(nome)
    faccia = f"giocatore:{avv.nome}"
    if carta.nome == "Psionic Blast":
        if p.giocatore(nome).vita <= 6:
            return None
        if avv.vita <= 4:
            return [faccia], 0
        if (c := _creatura_che_muore(p, nome, carta, 4)) and _mia_principale(p, nome):
            return [f"carta:{c.id}"], 0
        return None
    x = _x_massimo(p, nome, carta, [faccia])
    if x >= avv.vita:
        return [faccia], x
    if _mia_principale(p, nome) and (c := _creatura_che_muore(p, nome, carta, x)):
        return [f"carta:{c.id}"], c.costituzione_attuale - c.danni
    return None


def _creatura_che_muore(p: Partita, nome: str, fonte: Carta, danni: int) -> Carta | None:
    candidate = [c for c in p.avversario_di(nome)[Zona.CAMPO] if c.is_creatura
                 and bersaglio_legale(p, "qualsiasi", f"carta:{c.id}", fonte)
                 and 0 < c.costituzione_attuale - c.danni <= danni and c.forza_attuale >= 2]
    return max(candidate, key=lambda c: (c.forza_attuale, c.costituzione_attuale)) if candidate else None


def spazza(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    avv = p.avversario_di(nome).nome
    mie, sue = _forza_totale(p, nome), _forza_totale(p, avv)
    if carta.nome == "Wrath of God" and sue >= mie + 4 and len([c for c in p.giocatore(avv)[Zona.CAMPO] if c.is_creatura]) >= 2:
        return [], 0
    if carta.nome == "Armageddon" and mie >= 5 and sue == 0:
        return [], 0
    return None


POLITICHE = {
    "Counterspell": contromagia, "Mana Drain": contromagia, "Red Elemental Blast": contromagia,
    "Blue Elemental Blast": contromagia,
    "Swords to Plowshares": rimozione, "Terror": rimozione,
    "Disenchant": distruggi_permanente, "Shatter": distruggi_permanente, "Stone Rain": distruggi_permanente,
    "Sinkhole": distruggi_permanente, "Ice Storm": distruggi_permanente,
    "Ancestral Recall": pescate, "Braingeyser": pescate, "Timetwister": pescate, "Wheel of Fortune": pescate,
    "Time Walk": tutor_e_turni, "Demonic Tutor": tutor_e_turni, "Regrowth": tutor_e_turni,
    "Mind Twist": mind_twist, "Fireball": danni_x, "Psionic Blast": danni_x,
    "Wrath of God": spazza, "Armageddon": spazza,
}


def scegli_magia(p: Partita, nome: str):
    """La prima magia della mano che una politica vuole lanciare adesso: (carta, bersagli, x) o None."""
    for carta in list(p.giocatore(nome)[Zona.MANO]):
        politica = POLITICHE.get(carta.nome)
        if politica is None or puo_lanciare(p, nome, carta) is not None:
            continue
        scelta = politica(p, nome, carta)
        if scelta and puo_lanciare(p, nome, carta, scelta[0], scelta[1]) is None:
            return carta, scelta[0], scelta[1]
    return None


def scegli_abilita(p: Partita, nome: str):
    """Abilità di utilità: Strip Mine su una terra non base, Library of Alexandria e Jayemdae Tome a fine turno
    avversario, Icy Manipulator sulla creatura migliore avversaria nel suo mantenimento."""
    avv = p.avversario_di(nome)
    for c in list(p.giocatore(nome)[Zona.CAMPO]):
        for ab in analizza_abilita(c):
            if puo_attivare(p, nome, c, ab) is not None:
                continue
            if ab.tipo == "distruggi" and ab.bersaglio == "terra" and _mia_principale(p, nome):
                bersagli = [t for t in avv[Zona.CAMPO] if t.is_terra and t.nome not in TERRE_BASE]
                if bersagli:
                    return c, ab, [f"carta:{max(bersagli, key=valore_carta).id}"]
            if ab.tipo == "pesca" and _fine_turno_avversario(p, nome):
                return c, ab, []
            if (ab.tipo == "tappa" and p.giocatore_attivo.nome == avv.nome and p.fase == Fase.MANTENIMENTO
                    and not p.pila):
                creature = [t for t in avv[Zona.CAMPO] if t.is_creatura and not t.tappata
                            and bersaglio_legale(p, ab.bersaglio, f"carta:{t.id}", c)]
                if creature:
                    return c, ab, [f"carta:{max(creature, key=lambda t: t.forza_attuale).id}"]
    return None
