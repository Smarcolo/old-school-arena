import pytest
from collections import Counter

from app.ai.sideboard import scegli_cambi
from app.engine import azioni
from app.engine.stato import PAREGGIO, Carta
from app.engine.zone import Zona
from app.incontro import Incontro, Lista


def costruisci(lista):
    return [Carta(nome, "Basic Land — Forest" if nome == "Forest" else "Instant", "{U}") for nome, q in lista.items()
            for _ in range(q)]


def nuovo(seed=3):
    return Incontro(["A", "B"], {"A": Lista({"Forest": 20}, {"Counterspell": 2}), "B": Lista({"Forest": 20})},
                    costruisci, seed=seed)


def test_moneta_poi_inizia_chi_perde():
    inc = nuovo()
    assert inc.partita.giocatore_attivo.nome == inc.lancio_moneta
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    inc.registra_esito()
    assert inc.vittorie == {"A": 0, "B": 1} and inc.esiti == ["B"]
    inc.prossima()
    assert inc.numero == 2 and inc.partita.giocatore_attivo.nome == "A"
    azioni.concedi(inc.partita, "B")
    inc.registra_esito()
    inc.prossima()
    assert inc.numero == 3 and inc.partita.giocatore_attivo.nome == "B"
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    assert inc.vincitore == "B" and inc.vittorie == {"A": 1, "B": 2}


def test_moneta_equa():
    assert {nuovo(s).lancio_moneta for s in range(20)} == {"A", "B"}


def test_mazzi_nuovi_a_ogni_partita():
    inc = nuovo(4)
    ids_prima = {c.id for z in inc.partita.giocatore("A").zone.values() for c in z}
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    inc.prossima()
    ids_dopo = {c.id for z in inc.partita.giocatore("A").zone.values() for c in z}
    assert not ids_prima & ids_dopo and len(ids_dopo) == 20


def test_sideboard_tra_le_partite():
    inc = nuovo()
    with pytest.raises(ValueError, match="tra una partita"):
        inc.cambia_sideboard("A", {"Counterspell": 1}, {"Forest": 1})
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    with pytest.raises(ValueError, match="tante carte"):
        inc.cambia_sideboard("A", {"Counterspell": 2}, {"Forest": 1})
    with pytest.raises(ValueError, match="in sideboard non hai"):
        inc.cambia_sideboard("A", {"Counterspell": 3}, {"Forest": 3})
    inc.cambia_sideboard("A", {"Counterspell": 2}, {"Forest": 2})
    assert inc.liste["A"].mazzo == {"Forest": 18, "Counterspell": 2} and inc.liste["A"].sideboard == {"Forest": 2}
    inc.prossima()
    tutte = [c.nome for z in inc.partita.giocatore("A").zone.values() for c in z]
    assert tutte.count("Counterspell") == 2 and len(tutte) == 20


def test_carte_viste():
    inc = nuovo()
    inc.partita.giocatore("B")[Zona.CIMITERO].append(Carta("Lightning Bolt", "Instant", "{R}"))
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    assert inc.viste["B"]["Lightning Bolt"] == 1


def test_sideboard_dell_avversaria():
    info = {"Red Elemental Blast": Carta("Red Elemental Blast", "Instant", "{R}"),
            "Disenchant": Carta("Disenchant", "Instant", "{1}{W}"),
            "Gray Ogre": Carta("Gray Ogre", "Creature — Ogre", "{2}{R}", 2, 2),
            "Hill Giant": Carta("Hill Giant", "Creature — Giant", "{3}{R}", 3, 3),
            "Mountain": Carta("Mountain", "Basic Land — Mountain"),
            "Counterspell": Carta("Counterspell", "Instant", "{U}{U}"),
            "Serendib Efreet": Carta("Serendib Efreet", "Creature — Efreet", "{2}{U}", 3, 4)}
    viste = Counter({"Counterspell": 3, "Serendib Efreet": 2})  # l'avversario gioca blu
    entra, esce = scegli_cambi({"Red Elemental Blast": 2, "Disenchant": 2}, {"Mountain": 17, "Gray Ogre": 2, "Hill Giant": 2},
                               viste, info)
    assert entra == {"Red Elemental Blast": 2} and esce == {"Gray Ogre": 2}


def test_partita_pari_non_conta_e_ricomincia_lo_stesso():
    inc = nuovo(seed=4)
    primo = inc.primo
    for g in inc.partita.giocatori:
        g.vita = 0
    azioni.azioni_di_stato(inc.partita)
    inc.registra_esito()
    assert inc.partita.vincitore == PAREGGIO and sum(inc.vittorie.values()) == 0
    inc.prossima()
    assert inc.numero == 2 and inc.primo == primo
