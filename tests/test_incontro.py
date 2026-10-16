from app.engine import azioni
from app.engine.stato import Carta
from app.incontro import Incontro


def mazzi():
    return {"A": [Carta("Forest", "Basic Land — Forest") for _ in range(20)],
            "B": [Carta("Forest", "Basic Land — Forest") for _ in range(20)]}


def test_moneta_poi_inizia_chi_perde():
    inc = Incontro(["A", "B"], mazzi, seed=3)
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
    risultati = {Incontro(["A", "B"], mazzi, seed=s).lancio_moneta for s in range(20)}
    assert risultati == {"A", "B"}


def test_mazzi_nuovi_a_ogni_partita():
    inc = Incontro(["A", "B"], mazzi, seed=4)
    ids_prima = {c.id for z in inc.partita.giocatore("A").zone.values() for c in z}
    azioni.concedi(inc.partita, "A")
    inc.registra_esito()
    inc.prossima()
    ids_dopo = {c.id for z in inc.partita.giocatore("A").zone.values() for c in z}
    assert not ids_prima & ids_dopo and len(ids_dopo) == 20
