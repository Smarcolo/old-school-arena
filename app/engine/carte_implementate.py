"""Effetti delle carte implementate (istantanei e stregonerie), dal loro testo Oracle.
Importato da azioni.py così il registro è sempre pieno. Le semplificazioni sono scritte nel commento della carta."""
from app.engine import mana
from app.engine.effetti import bersaglio_legale, effetto
from app.engine.stato import Carta, OggettoPila
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
    _az().infliggi_danno(partita, oggetto.carta, f"giocatore:{oggetto.controllore}", 2)


@effetto("Fireball", bersaglio="qualsiasi", max_bersagli=0, costo_per_bersaglio="{1}")
def fireball(partita, oggetto):
    """X danni divisi in parti uguali (per difetto) tra i bersagli; costa {1} in più per ogni bersaglio oltre il
    primo. La divisione si fa al lancio: se un bersaglio non è più valido, la sua parte va persa."""
    parte = oggetto.x // len(oggetto.bersagli)
    for rif in oggetto.bersagli:
        if bersaglio_legale(partita, "qualsiasi", rif, oggetto.carta):
            _az().infliggi_danno(partita, oggetto.carta, rif, parte)


@effetto("Disintegrate", bersaglio="qualsiasi")
def disintegrate(partita, oggetto):
    """X danni. Se il bersaglio è una creatura, in questo turno non può rigenerare e, se muore, è rimossa dal gioco."""
    rif = oggetto.bersagli[0]
    if rif.startswith("carta:") and (t := partita.trova_in_campo(rif.removeprefix("carta:"))):
        t[1].disintegrata = True
    _az().infliggi_danno(partita, oggetto.carta, rif, oggetto.x)


def _danni_a_tutti(partita, oggetto, filtro_volare: bool):
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if c.is_creatura and c.ha("flying") == filtro_volare:
                _az().infliggi_danno(partita, oggetto.carta, f"carta:{c.id}", oggetto.x)
    for g in partita.giocatori:
        _az().infliggi_danno(partita, oggetto.carta, f"giocatore:{g.nome}", oggetto.x)


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
        partita.mana_ritardato.append((oggetto.controllore, valore, partita.turno, partita.fase))


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

PASSI_BALANCE = [  # (zona, quali carte, azione, cosa chiedere)
    (Zona.CAMPO, lambda c: c.is_terra, "distruggi", "una terra da sacrificare"),
    (Zona.MANO, lambda c: True, "scarta", "una carta da scartare"),
    (Zona.CAMPO, lambda c: c.is_creatura, "distruggi", "una creatura da sacrificare"),
]


@effetto("Balance")
def balance(partita, oggetto):
    """Terre, poi carte in mano, poi creature scendono al numero del giocatore che ne ha meno. Chi è in
    scelte_manuali sceglie una carta alla volta (Scelta "scegli" con seguito); per l'AI si tengono le migliori."""
    continua_balance(partita, 0)


def continua_balance(partita, passo: int) -> None:
    """Riprende Balance dal passo indicato. Il minimo si può ricalcolare dopo ogni carta tolta: chi ce l'ha non
    perde niente e gli altri scendono solo fino a lì."""
    attivo = partita.giocatore_attivo.nome
    for indice in range(passo, len(PASSI_BALANCE)):
        zona, condizione, azione, cosa = PASSI_BALANCE[indice]
        quante = {g.nome: [c for c in g[zona] if condizione(c)] for g in partita.giocatori}
        minimo = min(len(v) for v in quante.values())
        for nome in sorted(quante, key=lambda n: n != attivo):
            carte = quante[nome]
            da_togliere = len(carte) - minimo
            if da_togliere <= 0:
                continue
            if nome in partita.scelte_manuali and minimo > 0:
                _az().scegli_o_decidi(partita, nome, "Balance", azione, carte,
                                      f"Balance: scegli {cosa} (ancora {da_togliere})", seguito=("balance", indice))
                return
            for c in sorted(carte, key=valore_carta)[:da_togliere]:
                _az()._applica_scelta(partita, nome, azione, c, "Balance")


# --- Recall e Sylvan Library ---------------------------------------------------------------------

@effetto("Recall", rimuovi_dal_gioco=True)
def recall(partita, oggetto):
    """Scarti X carte, poi riprendi dal cimitero una carta per ogni carta scartata. Recall è rimossa dal gioco."""
    continua_recall(partita, oggetto.controllore, oggetto.x, 0, 0)


def continua_recall(partita, chi: str, x: int, scartate: int, riprese: int) -> None:
    g = partita.giocatore(chi)
    if scartate < x and g[Zona.MANO]:
        _az().scegli_o_decidi(partita, chi, "Recall", "scarta", list(g[Zona.MANO]),
                              f"Recall: scegli una carta da scartare ({scartate + 1} di {x})",
                              seguito=("recall", chi, x, scartate + 1, riprese))
        return
    scartate = min(scartate, x)
    if riprese < scartate and g[Zona.CIMITERO]:
        _az().scegli_o_decidi(partita, chi, "Recall", "riprendi", list(g[Zona.CIMITERO]),
                              f"Recall: scegli una carta da riprendere dal cimitero ({riprese + 1} di {scartate})",
                              seguito=("recall", chi, x, scartate, riprese + 1))


def continua_sylvan(partita, chi: str, fatte: int, gestite: tuple) -> None:
    """Sylvan Library dopo aver pescato le due carte in più: per due carte pescate in questo turno, paghi 4 vita
    o la rimetti in cima al grimorio. (Pescare le due carte in più conviene sempre: si possono rimettere quelle.)"""
    g = partita.giocatore(chi)
    pescate = [c for c in g[Zona.MANO] if c.pescata_nel_turno == partita.turno and c.id not in gestite]
    if fatte >= 2 or not pescate:
        return
    if chi not in partita.scelte_manuali:  # AI: rimette in cima le meno preziose, senza pagare vita
        for c in sorted(pescate, key=valore_carta)[:2 - fatte]:
            _az()._applica_scelta(partita, chi, "in_cima", c, "Sylvan Library")
        return
    opzioni = {}
    for c in pescate:
        opzioni[f"in_cima:{c.id}"] = f"Rimetti in cima: {c.nome}"
    for c in pescate:
        opzioni[f"tieni_pagando:{c.id}"] = f"Tieni {c.nome} pagando 4 vita"
    from app.engine.stato import Scelta
    partita.scelta = Scelta(chi, testo=f"Sylvan Library: scegli cosa fare con una carta pescata ({fatte + 1} di 2)",
                            tipo="scegli", dati={"carte": opzioni, "fonte": "Sylvan Library", "azione": "in_cima",
                                                 "seguito": ("sylvan", chi, fatte + 1, gestite)})


# Scelte che riprendono un effetto a metà. Per "sylvan" l'ultimo argomento (carte già gestite) riceve anche
# la carta appena scelta (vedi azioni.rispondi_scegli).
SEGUITI = {"balance": continua_balance, "recall": continua_recall, "sylvan": continua_sylvan}


# --- Creature e potenziamenti ------------------------------------------------------------------

@effetto("Giant Growth", bersaglio="creatura")
def giant_growth(partita, oggetto):
    creatura = _bersaglio(partita, oggetto)
    creatura.bonus_forza += 3
    creatura.bonus_costituzione += 3
