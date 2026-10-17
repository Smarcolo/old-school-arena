import pytest

from app.engine import azioni
from app.engine.mana import analizza_costo, con_x, mana_prodotto, paga, piano_pagamento, riga_di_mana
from app.engine.stato import Carta, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

FOREST = lambda: Carta("Forest", "Basic Land — Forest")
MOUNTAIN = lambda: Carta("Mountain", "Basic Land — Mountain")
ELFI = lambda: Carta("Llanowar Elves", "Creature — Elf Druid", "{G}", 1, 1, "{T}: Add {G}.")
TUNDRA = lambda: Carta("Tundra", "Land — Plains Island", testo="({T}: Add {W} or {U}.)")
SOL_RING = lambda: Carta("Sol Ring", "Artifact", "{1}", testo="{T}: Add {C}{C}.")
LOTUS = lambda: Carta("Black Lotus", "Artifact", "{0}", testo="{T}, Sacrifice Black Lotus: Add three mana of any one color.")
CITY = lambda: Carta("City of Brass", "Land", testo="Whenever City of Brass becomes tapped, it deals 1 damage to you.\n{T}: Add one mana of any color.")
MOX = lambda: Carta("Mox Jet", "Artifact", "{0}", testo="{T}: Add {B}.")
VUOTA = dict.fromkeys("WUBRGC", 0)


def fonti(*carte):
    return [mana_prodotto(c) for c in carte]


def test_analizza_costo():
    assert analizza_costo("{2}{G}{G}") == {"generico": 2, "G": 2}
    assert analizza_costo("") == {"generico": 0}
    assert analizza_costo("{X}{R}") == {"generico": 0, "X": 1, "R": 1}
    assert con_x(analizza_costo("{X}{R}"), 4) == {"generico": 4, "R": 1}


def test_fonti_riconosciute():
    assert mana_prodotto(FOREST()).colori == "G"
    assert mana_prodotto(ELFI()).colori == "G"
    assert mana_prodotto(TUNDRA()).colori == "WU"
    assert (mana_prodotto(SOL_RING()).colori, mana_prodotto(SOL_RING()).quantita) == ("C", 2)
    lotus = mana_prodotto(LOTUS())
    assert (lotus.colori, lotus.quantita, lotus.sacrifica) == ("WUBRG", 3, True)
    city = mana_prodotto(CITY())
    assert (city.colori, city.danno) == ("WUBRG", 1)
    assert mana_prodotto(Carta("Volcanic Island", "Land — Island Mountain")).colori == "UR"
    assert mana_prodotto(Carta("Grizzly Bears", "Creature — Bear")) is None
    assert riga_di_mana("{T}: Add {C}{C}.") and not riga_di_mana("{T}: Draw a card.")


def test_paga():
    assert paga({**VUOTA, "G": 2}, analizza_costo("{1}{G}"))["G"] == 0
    assert paga({**VUOTA, "R": 2}, analizza_costo("{1}{G}")) is None
    assert paga({**VUOTA, "G": 1, "C": 1}, analizza_costo("{1}"))["G"] == 1


def test_piano_preferisce_terre_e_tiene_lotus_per_ultimo():
    elfi, forest, mountain, lotus = ELFI(), FOREST(), MOUNTAIN(), LOTUS()
    piano = piano_pagamento(VUOTA, fonti(lotus, elfi, forest, mountain), analizza_costo("{1}{R}"))
    usate = [f.carta for f, _ in piano]
    assert mountain in usate and forest in usate and lotus not in usate and elfi not in usate


def test_lotus_quando_serve():
    piano = piano_pagamento(VUOTA, fonti(LOTUS()), analizza_costo("{U}{U}{U}"))
    assert [c for _, c in piano] == ["U"]


def test_doppia_paga_il_colore_che_serve():
    piano = piano_pagamento(VUOTA, fonti(TUNDRA(), FOREST()), analizza_costo("{U}{G}"))
    assert sorted(c for _, c in piano) == ["G", "U"]


def test_sol_ring_paga_due_generici():
    piano = piano_pagamento(VUOTA, fonti(SOL_RING(), FOREST()), analizza_costo("{2}"))
    assert len(piano) == 1 and piano[0][0].carta.nome == "Sol Ring"


def test_piano_impossibile_e_riserva():
    assert piano_pagamento(VUOTA, fonti(MOUNTAIN()), analizza_costo("{G}")) is None
    assert piano_pagamento({**VUOTA, "G": 1}, fonti(FOREST()), analizza_costo("{G}")) == []


@pytest.fixture
def p():
    return nuova_partita({"A": [FOREST() for _ in range(20)], "B": [FOREST() for _ in range(20)]}, seed=20)


def test_tappare_lotus_e_city(p):
    a = p.giocatore("A")
    lotus, city = LOTUS(), CITY()
    a[Zona.CAMPO].extend([lotus, city])
    azioni.tappa(p, "A", lotus, "R")
    assert a.riserva["R"] == 3 and azioni.trova_in_zona(p, "A", Zona.CIMITERO, "black lotus")
    azioni.tappa(p, "A", city, "U")
    assert a.riserva["U"] == 1 and a.vita == 19
    with pytest.raises(AzioneIllegale, match="non produce"):
        azioni.tappa(p, "A", (lambda t: (a[Zona.CAMPO].append(t), t)[1])(TUNDRA()), "B")


def test_lancio_con_mox_e_sol_ring(p):
    a = p.giocatore("A")
    a[Zona.CAMPO].extend([MOX(), SOL_RING()])
    juzam = Carta("Juzám Djinn", "Creature — Djinn", "{2}{B}{B}", 5, 5)
    a[Zona.MANO].append(juzam)
    with pytest.raises(AzioneIllegale, match="abbastanza mana"):
        azioni.lancia(p, "A", juzam)  # serve un secondo {B}
    a[Zona.CAMPO].append(Carta("Swamp", "Basic Land — Swamp"))
    azioni.lancia(p, "A", juzam)
    assert all(c.tappata for c in a[Zona.CAMPO])


def test_comando_tappa_per_colore(p):
    from app.commands.esegui import esegui
    from app.commands.parser import analizza
    p.giocatore("A")[Zona.CAMPO].append(TUNDRA())
    assert "{U}" in esegui(p, "A", analizza("tappa tundra per blu"))
