import pytest

from app.ai import avversaria, previsione
from app.engine import combattimento
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.zone import Zona


def cr(nome, f, c):
    return Carta(nome, "Creature — Test", "{1}", f, c)


def terra():
    return Carta("Forest", "Basic Land — Forest", "", None, None, "({T}: Add {G}.)")


@pytest.fixture
def con_previsione(monkeypatch):
    monkeypatch.setattr(previsione, "ABILITATA", True)


def partita_in_combattimento():
    p = nuova_partita({"AI": [terra() for _ in range(30)], "B": [terra() for _ in range(30)]}, seed=7)
    p.mulligan = None
    p.turno = 6
    return p


def test_attacco_con_previsione(con_previsione):
    """Con la previsione accesa l'AI dichiara un attacco valido: qui attaccare con il 5/5 non rischia niente."""
    p = partita_in_combattimento()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO].extend([cr("Grosso", 5, 5), cr("Piccolo", 1, 1)])
    b[Zona.CAMPO].append(cr("Muro", 0, 6))
    for c in ai[Zona.CAMPO]:
        c.entrata_nel_turno = 1
    p.attivo = p.priorita = p.giocatori.index(ai)
    p.fase = Fase.COMBATTIMENTO
    combattimento.inizia(p)
    assert combattimento.deve_dichiarare_attaccanti(p, "AI")
    avversaria.agisci(p, "AI")
    assert p.combattimento.attaccanti_dichiarati
    assert ai[Zona.CAMPO][0].id in p.combattimento.attaccanti


def test_le_copie_non_toccano_la_partita_vera(con_previsione):
    p = partita_in_combattimento()
    p.giocatore("AI")[Zona.CAMPO].append(cr("Orso", 2, 2))
    mano_b = [c.id for c in p.giocatore("B")[Zona.MANO]]
    scelta = previsione.migliore(p, "AI", ["a", "b"], lambda copia, o: copia.giocatore("B")[Zona.MANO].clear())
    assert scelta == "a"  # a parità vince la scelta delle regole
    assert [c.id for c in p.giocatore("B")[Zona.MANO]] == mano_b
    assert not previsione._in_corso


def test_valuta():
    p = partita_in_combattimento()
    pari = previsione.valuta(p, "AI")
    p.giocatore("B").vita = 5
    assert previsione.valuta(p, "AI") > pari + 0.3
    p.giocatore("B").vita = 20
    p.giocatore("AI").vita = 3
    assert previsione.valuta(p, "AI") < pari - 0.3
    p.vincitore = "AI"
    assert previsione.valuta(p, "AI") == 1.0


def test_spenta_nei_tornei_simulati(con_previsione):
    with previsione.spenta():
        assert not previsione.attiva()
    assert previsione.attiva()
