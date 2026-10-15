import pytest

from app.cards import database
from app.engine.stato import Carta, nuova_partita


@pytest.fixture
def conn(tmp_path):
    c = database.connetti(tmp_path / "carte.sqlite")
    database.carica_carte_base(c)
    return c


def mazzo(n_terre=20, n_orsi=20):
    return ([Carta("Forest", "Basic Land — Forest") for _ in range(n_terre)]
            + [Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2) for _ in range(n_orsi)])


@pytest.fixture
def partita():
    return nuova_partita({"A": mazzo(), "B": mazzo()}, seed=1)
