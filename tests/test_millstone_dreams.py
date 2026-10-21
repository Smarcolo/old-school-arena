"""Carte del mazzo Millstone Dreams (Mr. Pox, TCDecks): Millstone, Recall, Field of Dreams, Sylvan Library,
Fellwar Stone, Chaos Orb, Mirror Universe; e la lista incollata da TCDecks."""
import pytest

from app.cards import mazzi
from app.engine import azioni
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale, fonti_di_mana
from app.engine.zone import Zona

MULTI = "Land — Plains Island Swamp Mountain Forest"
TESTI = {
    "Millstone": ("Artifact", "{2}", "{2}, {T}: Target player mills two cards."),
    "Mirror Universe": ("Artifact", "{6}", "{T}, Sacrifice Mirror Universe: Exchange life totals with target opponent. "
                                           "Activate only during your upkeep."),
    "Chaos Orb": ("Artifact", "{2}", "{1}, {T}: If Chaos Orb is on the battlefield, flip Chaos Orb onto the battlefield "
                                     "from a height of at least one foot. Destroy each nontoken permanent touched by Chaos "
                                     "Orb. Then destroy Chaos Orb."),
    "Fellwar Stone": ("Artifact", "{2}", "{T}: Add one mana of any color that a land an opponent controls could produce."),
    "Recall": ("Sorcery", "{X}{X}{U}", "Discard X cards, then return a card from your graveyard to your hand for each "
                                       "card discarded this way. Exile Recall."),
    "Sylvan Library": ("Enchantment", "{1}{G}", "At the beginning of your draw step, you may draw two additional cards. If "
                       "you do, choose two cards in your hand drawn this turn. For each of those cards, pay 4 life or put "
                       "the card on top of your library."),
    "Field of Dreams": ("World Enchantment", "{W}", "Players play with the top card of their libraries revealed."),
}


def carta(nome):
    tipo, costo, testo = TESTI[nome]
    return Carta(nome, tipo, costo, None, None, testo)


@pytest.fixture
def p():
    partita = nuova_partita({"A": [Carta(f"A{i}", "Instant", "{U}") for i in range(30)],
                             "B": [Carta(f"B{i}", "Instant", "{U}") for i in range(30)]}, seed=4)
    partita.turno = 3
    partita.fase = Fase.PRINCIPALE_1
    for g in partita.giocatori:
        g[Zona.CAMPO].extend(Carta("Terra", MULTI) for _ in range(8))
    return partita


def in_campo(p, chi, c):
    c.proprietario, c.entrata_nel_turno = chi, 1
    p.giocatore(chi)[Zona.CAMPO].append(c)
    return c


def risolvi(p):
    while p.pila and not p.scelta:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_lista_copiata_da_tcdecks():
    testo = ("Mr. Pox playing Millstone Dreams\tPosition: 2\nDeck Name: Millstone Dreams\tSideboard\nInstants [5]\n"
             "4 Counterspell\n1 Ancestral Recall\nLand [2]\n2 Tundra\n4 Serra Angel\n3 Blue Elemental Blast\n")
    mazzo, side, errori = mazzi.analizza_testo(testo)
    assert mazzo == {"Counterspell": 4, "Ancestral Recall": 1, "Tundra": 2}
    assert side == {"Serra Angel": 4, "Blue Elemental Blast": 3} and errori == []


def test_millstone(p):
    ms = in_campo(p, "A", carta("Millstone"))
    prima = len(p.giocatore("B")[Zona.GRIMORIO])
    azioni.attiva(p, "A", ms, analizza_abilita(ms)[0], ["giocatore:B"])
    risolvi(p)
    assert len(p.giocatore("B")[Zona.GRIMORIO]) == prima - 2 and len(p.giocatore("B")[Zona.CIMITERO]) == 2


def test_mirror_universe_solo_nel_mantenimento(p):
    mu = in_campo(p, "A", carta("Mirror Universe"))
    p.giocatore("A").vita, p.giocatore("B").vita = 3, 18
    ab = analizza_abilita(mu)[0]
    with pytest.raises(AzioneIllegale, match="mantenimento"):
        azioni.attiva(p, "A", mu, ab, ["giocatore:B"])
    p.fase = Fase.MANTENIMENTO
    with pytest.raises(AzioneIllegale):
        azioni.attiva(p, "A", mu, ab, ["giocatore:A"])  # solo un avversario
    azioni.attiva(p, "A", mu, ab, ["giocatore:B"])
    risolvi(p)
    assert (p.giocatore("A").vita, p.giocatore("B").vita) == (18, 3) and mu in p.giocatore("A")[Zona.CIMITERO]


def test_chaos_orb(p):
    orb = in_campo(p, "A", carta("Chaos Orb"))
    drago = in_campo(p, "B", Carta("Drago", "Creature — Dragon", "{4}{R}{R}", 5, 5))
    azioni.attiva(p, "A", orb, analizza_abilita(orb)[0], [f"carta:{drago.id}"])
    risolvi(p)
    assert drago in p.giocatore("B")[Zona.CIMITERO] and orb in p.giocatore("A")[Zona.CIMITERO]


def test_fellwar_stone_prende_i_colori_delle_terre_avversarie(p):
    for g in p.giocatori:
        g[Zona.CAMPO].clear()
    in_campo(p, "B", Carta("Mountain", "Basic Land — Mountain"))
    in_campo(p, "B", Carta("Tropical Island", "Land — Forest Island"))
    pietra = in_campo(p, "A", carta("Fellwar Stone"))
    (fonte,) = fonti_di_mana(p, "A")
    assert sorted(fonte.colori) == ["G", "R", "U"]
    azioni.tappa(p, "A", pietra, "U")
    assert p.giocatore("A").riserva["U"] == 1


def test_recall_con_scelte(p):
    p.scelte_manuali = {"A"}
    a = p.giocatore("A")
    walk = Carta("Time Walk", "Sorcery", "{1}{U}")
    a[Zona.CIMITERO].append(walk)
    a[Zona.MANO][:] = [Carta("Inutile1", "Instant", "{U}"), Carta("Inutile2", "Instant", "{U}"), Carta("Tieni", "Instant", "{U}")]
    rec = carta("Recall")
    a[Zona.MANO].append(rec)
    azioni.lancia(p, "A", rec, [], x=1)
    risolvi(p)
    assert p.scelta and "scartare" in p.scelta.testo
    inutile = a[Zona.MANO][0]
    azioni.rispondi_scegli(p, "A", inutile.id)
    assert p.scelta and "riprendere" in p.scelta.testo
    azioni.rispondi_scegli(p, "A", walk.id)
    assert walk in a[Zona.MANO] and inutile in a[Zona.CIMITERO] and rec in a[Zona.RIMOSSE] and p.scelta is None


def test_sylvan_library(p):
    p.scelte_manuali = {"A"}
    a = p.giocatore("A")
    in_campo(p, "A", carta("Sylvan Library"))
    p.fase, p.turno = Fase.FINALE, 4
    p.attivo = p.priorita = 1  # fine turno di B: il prossimo è di A
    while not p.scelta:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    pescate = [c for c in a[Zona.MANO] if c.pescata_nel_turno == p.turno]
    assert len(pescate) == 3  # la pescata normale più le due di Sylvan Library
    azioni.rispondi_scegli(p, "A", f"in_cima:{pescate[0].id}")
    assert p.scelta and f"in_cima:{pescate[0].id}" not in p.scelta.dati["carte"]
    vita = a.vita
    azioni.rispondi_scegli(p, "A", f"tieni_pagando:{pescate[1].id}")
    assert p.scelta is None and a.vita == vita - 4
    assert a[Zona.GRIMORIO][-1] is pescate[0] and pescate[1] in a[Zona.MANO]


def test_sylvan_library_ai_rimette_due_carte(p):
    b = p.giocatore("B")
    in_campo(p, "B", carta("Sylvan Library"))
    mano_prima = len(b[Zona.MANO])
    p.fase = Fase.FINALE
    while not (p.giocatore_attivo.nome == "B" and p.fase == Fase.PRINCIPALE_1):
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    assert len(b[Zona.MANO]) == mano_prima + 1  # pesca 3, ne rimette 2


def test_un_solo_incantesimo_del_mondo(p):
    f1 = in_campo(p, "A", carta("Field of Dreams"))
    f2 = carta("Field of Dreams")
    p.giocatore("B")[Zona.MANO].append(f2)
    p.attivo = p.priorita = 1
    azioni.lancia(p, "B", f2)
    risolvi(p)
    assert f1 in p.giocatore("A")[Zona.CIMITERO] and f2 in p.giocatore("B")[Zona.CAMPO]
