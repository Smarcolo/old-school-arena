"""Effetti delle carte implementate (istantanei e stregonerie), dal loro testo Oracle.
Importato da azioni.py così il registro è sempre pieno. Le semplificazioni sono scritte nel commento della carta."""
from app.engine import mana
from app.engine.effetti import effetto
from app.engine.stato import Carta, Giocatore, OggettoPila
from app.engine.zone import Zona

# Priorità quando un effetto deve scegliere una carta da solo (Demonic Tutor dell'AI, scelte automatiche)
CARTE_MIGLIORI = ["Ancestral Recall", "Time Walk", "Black Lotus", "Timetwister", "Mind Twist", "Balance",
                  "Wheel of Fortune", "Demonic Tutor", "Mana Drain", "Counterspell", "Swords to Plowshares",
                  "Lightning Bolt", "Sol Ring"]


def _az():
    from app.engine import azioni
    return azioni


def _bersaglio(partita, oggetto):
    return partita.risolvi_bersaglio(oggetto.bersagli[0])


def valore_carta(c: Carta) -> tuple:
    """Più alto = più preziosa. Serve alle scelte automatiche."""
    if c.nome in CARTE_MIGLIORI:
        return (2, -CARTE_MIGLIORI.index(c.nome))
    return (1 if not c.is_terra else 0, mana.valore(c.costo) + (c.forza or 0))


def scegli_migliore(carte: list[Carta]) -> Carta:
    return max(carte, key=valore_carta)


# --- Danni -------------------------------------------------------------------------------------

@effetto("Lightning Bolt", bersaglio="qualsiasi")
def lightning_bolt(partita, oggetto):
    _az().infliggi_danno(partita, oggetto.carta, oggetto.bersagli[0], 3)


@effetto("Psionic Blast", bersaglio="qualsiasi")
def psionic_blast(partita, oggetto):
    """Psionic Blast deals 4 damage to any target and 2 damage to you."""
    _az().infliggi_danno(partita, oggetto.carta, oggetto.bersagli[0], 4)
    _az().modifica_vita(partita, oggetto.controllore, -2, "(Psionic Blast)")


@effetto("Fireball", bersaglio="qualsiasi")
def fireball(partita, oggetto):
    """X danni a un bersaglio. Semplificazione: la divisione tra più bersagli (pagando {1} in più) non c'è."""
    _az().infliggi_danno(partita, oggetto.carta, oggetto.bersagli[0], oggetto.x)


def _danni_a_tutti(partita, oggetto, filtro_volare: bool):
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if c.is_creatura and c.ha("flying") == filtro_volare:
                _az().infliggi_danno(partita, oggetto.carta, f"carta:{c.id}", oggetto.x)
    for g in partita.giocatori:
        _az().modifica_vita(partita, g.nome, -oggetto.x, f"({oggetto.carta.nome})")


@effetto("Earthquake")
def earthquake(partita, oggetto):
    """X danni a ogni creatura senza volare e a ogni giocatore."""
    _danni_a_tutti(partita, oggetto, filtro_volare=False)


@effetto("Hurricane")
def hurricane(partita, oggetto):
    """X danni a ogni creatura con volare e a ogni giocatore."""
    _danni_a_tutti(partita, oggetto, filtro_volare=True)


# --- Rimozione ---------------------------------------------------------------------------------

@effetto("Swords to Plowshares", bersaglio="creatura")
def swords_to_plowshares(partita, oggetto):
    """Exile target creature. Its controller gains life equal to its power."""
    creatura = _bersaglio(partita, oggetto)
    controllore = partita.trova_in_campo(creatura.id)[0].nome
    forza = creatura.forza_attuale
    _az().rimuovi_dal_gioco(partita, creatura, "(Swords to Plowshares)")
    if forza > 0:
        _az().modifica_vita(partita, controllore, forza, "(Swords to Plowshares)")


@effetto("Terror", bersaglio="creatura_non_nera_non_artefatto")
def terror(partita, oggetto):
    """Destroy target nonartifact, nonblack creature. It can't be regenerated."""
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Terror)", rigenerabile=False)


@effetto("Disenchant", bersaglio="artefatto_o_incantesimo")
def disenchant(partita, oggetto):
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Disenchant)")


@effetto("Shatter", bersaglio="artefatto")
def shatter(partita, oggetto):
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Shatter)")


@effetto("Stone Rain", bersaglio="terra")
def stone_rain(partita, oggetto):
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Stone Rain)")


@effetto("Sinkhole", bersaglio="terra")
def sinkhole(partita, oggetto):
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Sinkhole)")


@effetto("Ice Storm", bersaglio="terra")
def ice_storm(partita, oggetto):
    _az().distruggi(partita, _bersaglio(partita, oggetto), "(Ice Storm)")


@effetto("Unsummon", bersaglio="creatura")
def unsummon(partita, oggetto):
    _az().torna_in_mano(partita, _bersaglio(partita, oggetto))


@effetto("Boomerang", bersaglio="permanente")
def boomerang(partita, oggetto):
    _az().torna_in_mano(partita, _bersaglio(partita, oggetto))


def _distruggi_tutti(partita, condizione, motivo, rigenerabile):
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if condizione(c):
                _az().distruggi(partita, c, motivo, rigenerabile=rigenerabile)


@effetto("Wrath of God")
def wrath_of_god(partita, oggetto):
    """Destroy all creatures. They can't be regenerated."""
    _distruggi_tutti(partita, lambda c: c.is_creatura, "(Wrath of God)", rigenerabile=False)


@effetto("Armageddon")
def armageddon(partita, oggetto):
    _distruggi_tutti(partita, lambda c: c.is_terra, "(Armageddon)", rigenerabile=True)


# --- Contromagie -------------------------------------------------------------------------------

@effetto("Counterspell", bersaglio="magia")
def counterspell(partita, oggetto):
    _az().neutralizza(partita, _bersaglio(partita, oggetto), "Counterspell")


@effetto("Mana Drain", bersaglio="magia")
def mana_drain(partita, oggetto):
    """Counter target spell. At the beginning of your next main phase, add an amount of {C} equal to that spell's
    mana value."""
    magia = _bersaglio(partita, oggetto)
    _az().neutralizza(partita, magia, "Mana Drain")
    if (valore := mana.valore(magia.carta.costo)) > 0:
        partita.mana_ritardato.append((oggetto.controllore, valore))


def _elemental_blast(colore_nome):
    def risolvi(partita, oggetto):
        """Choose one — Counter target <colore> spell; or Destroy target <colore> permanent."""
        bersaglio = _bersaglio(partita, oggetto)
        if isinstance(bersaglio, OggettoPila):
            _az().neutralizza(partita, bersaglio, oggetto.carta.nome)
        else:
            _az().distruggi(partita, bersaglio, f"({oggetto.carta.nome})")
    return risolvi


effetto("Red Elemental Blast", bersaglio="blu")(_elemental_blast("blu"))
effetto("Blue Elemental Blast", bersaglio="rosso")(_elemental_blast("rosso"))


# --- Carte, mano, grimorio ---------------------------------------------------------------------

@effetto("Ancestral Recall", bersaglio="giocatore")
def ancestral_recall(partita, oggetto):
    _az().pesca(partita, _bersaglio(partita, oggetto).nome, 3)


@effetto("Braingeyser", bersaglio="giocatore")
def braingeyser(partita, oggetto):
    _az().pesca(partita, _bersaglio(partita, oggetto).nome, oggetto.x)


@effetto("Timetwister")
def timetwister(partita, oggetto):
    """Each player shuffles their hand and graveyard into their library, then draws seven cards."""
    for g in partita.giocatori:
        _az().mescola_nel_grimorio(partita, g.nome, Zona.MANO, Zona.CIMITERO)
    for g in partita.giocatori:
        _az().pesca(partita, g.nome, 7)


@effetto("Wheel of Fortune")
def wheel_of_fortune(partita, oggetto):
    """Each player discards their hand, then draws seven cards."""
    for g in partita.giocatori:
        for c in list(g[Zona.MANO]):
            _az().scarta(partita, g.nome, c, "(Wheel of Fortune)")
    for g in partita.giocatori:
        _az().pesca(partita, g.nome, 7)


@effetto("Mind Twist", bersaglio="giocatore")
def mind_twist(partita, oggetto):
    """Target player discards X cards at random."""
    _az().scarta_a_caso(partita, _bersaglio(partita, oggetto).nome, oggetto.x, "(Mind Twist)")


@effetto("Demonic Tutor")
def demonic_tutor(partita, oggetto):
    _az().cerca_nel_grimorio(partita, oggetto.controllore, oggetto.carta, scegli_migliore)


@effetto("Regrowth", bersaglio="carta_tuo_cimitero")
def regrowth(partita, oggetto):
    carta = _bersaglio(partita, oggetto)
    g = partita.proprietario_cimitero(carta)
    g[Zona.CIMITERO].remove(carta)
    g[Zona.MANO].append(carta)
    _az()._log(partita, g.nome, "in_mano", f"{carta.nome} torna in mano a {g.nome} (Regrowth)")


# --- Turni e mana ------------------------------------------------------------------------------

@effetto("Time Walk")
def time_walk(partita, oggetto):
    """Take an extra turn after this one."""
    partita.turni_extra.append(oggetto.controllore)
    _az()._log(partita, oggetto.controllore, "turno_extra", f"{oggetto.controllore} giocherà un turno in più")


@effetto("Dark Ritual")
def dark_ritual(partita, oggetto):
    _az().aggiungi_mana(partita, oggetto.controllore, "B", 3, "(Dark Ritual)")


# --- Balance -----------------------------------------------------------------------------------

@effetto("Balance")
def balance(partita, oggetto):
    """Terre, carte in mano e creature scendono al numero del giocatore che ne ha meno.
    Semplificazione: le scelte sono automatiche (si tengono le carte di valore più alto) per entrambi i giocatori."""
    for zona, condizione, azione in (
            (Zona.CAMPO, lambda c: c.is_terra, "sacrifica"),
            (Zona.MANO, lambda c: True, "scarta"),
            (Zona.CAMPO, lambda c: c.is_creatura, "sacrifica")):
        quante = {g.nome: [c for c in g[zona] if condizione(c)] for g in partita.giocatori}
        minimo = min(len(v) for v in quante.values())
        for nome, carte in quante.items():
            for c in sorted(carte, key=valore_carta)[:len(carte) - minimo]:
                if azione == "scarta":
                    _az().scarta(partita, nome, c, "(Balance)")
                else:
                    _az().distruggi(partita, c, "(Balance: sacrificata)", rigenerabile=False)


# --- Creature e potenziamenti ------------------------------------------------------------------

@effetto("Giant Growth", bersaglio="creatura")
def giant_growth(partita, oggetto):
    creatura = _bersaglio(partita, oggetto)
    creatura.bonus_forza += 3
    creatura.bonus_costituzione += 3
