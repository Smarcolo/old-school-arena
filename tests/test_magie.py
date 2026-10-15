import pytest

from app.engine import azioni
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def forest():
    return Carta("Forest", "Basic Land — Forest")


def orso():
    return Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2)


def elfi():
    return Carta("Llanowar Elves", "Creature — Elf Druid", "{G}", 1, 1, "{T}: Add {G}.")


@pytest.fixture
def p():
    """A nel turno 1, fase principale, con 2 Forest in campo e un orso e degli elfi in mano."""
    partita = nuova_partita({"A": [forest() for _ in range(20)], "B": [forest() for _ in range(20)]}, seed=1)
    a = partita.giocatore("A")
    a[Zona.CAMPO].extend([forest(), forest()])
    a[Zona.MANO].extend([orso(), elfi()])
    return partita


def carta(p, nome, zona=Zona.MANO, chi="A"):
    return azioni.trova_in_zona(p, chi, zona, nome)


def test_lancia_creatura_va_in_pila_e_tappa_le_terre(p):
    azioni.lancia(p, "A", carta(p, "grizzly bears"))
    assert [o.carta.nome for o in p.pila] == ["Grizzly Bears"]
    assert all(c.tappata for c in p.giocatore("A")[Zona.CAMPO])
    assert p.giocatore_con_priorita.nome == "A"  # chi lancia mantiene la priorità


def test_entrambi_passano_e_la_creatura_si_risolve(p):
    azioni.lancia(p, "A", carta(p, "grizzly bears"))
    azioni.passa_priorita(p, "A")
    assert p.giocatore_con_priorita.nome == "B" and p.pila
    azioni.passa_priorita(p, "B")
    assert not p.pila
    orso_in_campo = carta(p, "grizzly bears", Zona.CAMPO)
    assert orso_in_campo and p.ha_debolezza_da_evocazione(orso_in_campo)
    assert p.fase == Fase.PRINCIPALE_1 and p.giocatore_con_priorita.nome == "A"


def test_senza_mana_non_si_lancia(p):
    for c in p.giocatore("A")[Zona.CAMPO]:
        c.tappata = True
    with pytest.raises(AzioneIllegale, match="abbastanza mana"):
        azioni.lancia(p, "A", carta(p, "grizzly bears"))
    assert carta(p, "grizzly bears")  # resta in mano


def test_creature_non_si_lanciano_nel_turno_avversario(p):
    p.giocatore("B")[Zona.MANO].append(orso())
    p.priorita = 1
    with pytest.raises(AzioneIllegale, match="solo nel tuo turno"):
        azioni.lancia(p, "B", carta(p, "grizzly bears", chi="B"))


def test_serve_la_priorita(p):
    with pytest.raises(AzioneIllegale, match="priorità"):
        azioni.passa_priorita(p, "B")


def test_istantaneo_senza_effetto_non_si_lancia(p):
    p.giocatore("A")[Zona.MANO].append(Carta("Healing Salve", "Instant", "{W}"))
    with pytest.raises(AzioneIllegale, match="non è ancora implementato"):
        azioni.lancia(p, "A", carta(p, "healing salve"))


def test_debolezza_da_evocazione_e_turno_dopo(p):
    azioni.lancia(p, "A", carta(p, "llanowar elves"))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    e = carta(p, "llanowar elves", Zona.CAMPO)
    with pytest.raises(AzioneIllegale, match="entrata in questo turno"):
        azioni.tappa(p, "A", e)
    while not (p.turno == 3 and p.fase == Fase.PRINCIPALE_1):
        azioni.passa_fase(p)
    azioni.tappa(p, "A", e)
    assert p.giocatore("A").riserva["G"] == 1


def test_mana_burn(p):
    azioni.tappa(p, "A", carta(p, "forest", Zona.CAMPO))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.fase == Fase.COMBATTIMENTO
    assert p.giocatore("A").vita == 19 and p.giocatore("A").riserva["G"] == 0


def test_mana_in_riserva_paga_il_costo(p):
    azioni.tappa(p, "A", carta(p, "forest", Zona.CAMPO))
    azioni.lancia(p, "A", carta(p, "llanowar elves"))
    assert p.giocatore("A").riserva["G"] == 0
    assert sum(c.tappata for c in p.giocatore("A")[Zona.CAMPO]) == 1


def test_fase_non_cambia_con_pila_piena(p):
    azioni.lancia(p, "A", carta(p, "grizzly bears"))
    with pytest.raises(AzioneIllegale, match="pila"):
        azioni.passa_fase(p)
