import pytest

from app.ai.avversaria import decidi_mulligan
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, mulligan
from app.engine.stato import Carta, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona
from app.regia import esegui_comando


def terra():
    return Carta("Forest", "Basic Land — Forest")


def orso():
    return Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2)


@pytest.fixture
def p():
    return nuova_partita({"A": [terra() for _ in range(20)] + [orso() for _ in range(20)],
                          "B": [terra() for _ in range(20)] + [orso() for _ in range(20)]}, seed=17, mulligan=True)


def test_niente_mosse_durante_il_mulligan(p):
    assert mulligan.in_corso(p)
    foresta = terra()
    p.giocatore("A")[Zona.MANO].append(foresta)
    with pytest.raises(AzioneIllegale, match="mulligan"):
        azioni.gioca_terra(p, "A", foresta)
    with pytest.raises(AzioneIllegale, match="mulligan"):
        azioni.passa_priorita(p, "A")


def test_london(p):
    a = p.giocatore("A")
    mulligan.fai_mulligan(p, "A")
    mulligan.fai_mulligan(p, "A")
    assert len(a[Zona.MANO]) == 7 and len(a[Zona.GRIMORIO]) == 33
    mulligan.tieni(p, "A")
    with pytest.raises(AzioneIllegale, match="esattamente 2"):
        mulligan.metti_in_fondo(p, "A", a[Zona.MANO][:1])
    via = a[Zona.MANO][:2]
    mulligan.metti_in_fondo(p, "A", via)
    assert len(a[Zona.MANO]) == 5
    assert {c.id for c in a[Zona.GRIMORIO][:2]} == {c.id for c in via}  # in fondo: si pesca dalla fine della lista
    assert p.mulligan["A"].finito and mulligan.in_corso(p)  # B non ha ancora deciso
    mulligan.tieni(p, "B")
    assert not mulligan.in_corso(p)
    azioni.passa_priorita(p, "A")  # ora si gioca


def test_tenere_senza_mulligan(p):
    mulligan.tieni(p, "A")
    assert p.mulligan["A"].finito and len(p.giocatore("A")[Zona.MANO]) == 7
    with pytest.raises(AzioneIllegale, match="già tenuto"):
        mulligan.fai_mulligan(p, "A")


def test_comandi(p):
    assert esegui(p, "A", analizza("mulligan")) == "Mulligan: nuova mano di 7 carte."
    assert "metti in fondo 1 carta." in esegui(p, "A", analizza("tengo"))
    nome = p.giocatore("A")[Zona.MANO][0].nome
    assert esegui(p, "A", analizza(f"in fondo {nome}")) == "Carte messe in fondo al mazzo."


def test_ai_tiene_una_mano_normale_e_rifa_quella_senza_terre():
    p = nuova_partita({"A": [terra() for _ in range(20)], "AI": [orso() for _ in range(30)] + [terra() for _ in range(10)]},
                      seed=18, mulligan=True)
    ai = p.giocatore("AI")
    ai[Zona.GRIMORIO].extend(ai[Zona.MANO])
    ai[Zona.MANO][:] = [orso() for _ in range(7)]  # mano senza terre
    decidi_mulligan(p, "AI")
    assert p.mulligan["AI"].fatti == 1
    ai[Zona.MANO][:] = [terra(), terra(), terra(), orso(), orso(), orso(), orso()]
    decidi_mulligan(p, "AI")
    assert p.mulligan["AI"].tenuta and p.mulligan["AI"].da_mettere_in_fondo == 1
    decidi_mulligan(p, "AI")
    assert p.mulligan["AI"].finito and len(ai[Zona.MANO]) == 6


def test_regia_aspetta_l_umano_e_fa_decidere_l_ai():
    p = nuova_partita({"Tu": [terra() for _ in range(40)], "AI": [terra() for _ in range(20)] + [orso() for _ in range(20)]},
                      seed=19, mulligan=True)
    msg = esegui_comando(p, "Tu", "AI", "mano")
    assert "«tengo» oppure «mulligan»" in msg
    esegui_comando(p, "Tu", "AI", "tengo")
    assert not mulligan.in_corso(p) and p.mulligan["AI"].finito
