from app.engine.mana import analizza_costo, mana_prodotto, paga, piano_pagamento
from app.engine.stato import Carta

FOREST = lambda: Carta("Forest", "Basic Land — Forest")
MOUNTAIN = lambda: Carta("Mountain", "Basic Land — Mountain")
ELFI = lambda: Carta("Llanowar Elves", "Creature — Elf Druid", "{G}", 1, 1, "{T}: Add {G}.")
VUOTA = dict.fromkeys("WUBRGC", 0)


def test_analizza_costo():
    assert analizza_costo("{2}{G}{G}") == {"generico": 2, "G": 2}
    assert analizza_costo("") == {"generico": 0}


def test_mana_prodotto():
    assert mana_prodotto(FOREST()) == "G"
    assert mana_prodotto(ELFI()) == "G"
    assert mana_prodotto(Carta("Grizzly Bears", "Creature — Bear")) is None


def test_paga():
    assert paga({**VUOTA, "G": 2}, analizza_costo("{1}{G}"))["G"] == 0
    assert paga({**VUOTA, "R": 2}, analizza_costo("{1}{G}")) is None
    # il generico usa prima l'incolore
    assert paga({**VUOTA, "G": 1, "C": 1}, analizza_costo("{1}"))["G"] == 1


def test_piano_preferisce_terre_per_il_generico():
    elfi, forest, mountain = ELFI(), FOREST(), MOUNTAIN()
    piano = piano_pagamento(VUOTA, [(elfi, "G"), (forest, "G"), (mountain, "R")], analizza_costo("{1}{R}"))
    assert mountain in piano and elfi not in piano and len(piano) == 2


def test_piano_impossibile():
    assert piano_pagamento(VUOTA, [(MOUNTAIN(), "R")], analizza_costo("{G}")) is None


def test_piano_usa_prima_la_riserva():
    assert piano_pagamento({**VUOTA, "G": 1}, [(FOREST(), "G")], analizza_costo("{G}")) == []
