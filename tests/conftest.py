import os
import tempfile

# Prima di importare l'app: database in una cartella temporanea, non in data/.
os.environ.setdefault("OSA_DATI", tempfile.mkdtemp(prefix="osa-test-"))

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


@pytest.fixture(autouse=True)
def _senza_previsione(monkeypatch):
    """L'AI nei test usa le sue regole veloci; la previsione ha i suoi test (test_previsione.py)."""
    from app.ai import previsione
    monkeypatch.setattr(previsione, "ABILITATA", False)
