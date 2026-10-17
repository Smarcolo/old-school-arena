import pytest

from app.ai.avversaria import agisci
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni
from app.engine.stato import Carta, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def terra(nome="Mountain"):
    return Carta(nome, f"Basic Land — {nome}")


def bolt():
    return Carta("Lightning Bolt", "Instant", "{R}", testo="Lightning Bolt deals 3 damage to any target.")


def growth():
    return Carta("Giant Growth", "Instant", "{G}")


def orso():
    return Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2)


def giant():
    return Carta("Hill Giant", "Creature — Giant", "{3}{R}", 3, 3)


@pytest.fixture
def p():
    """A (rosso) nel suo turno con Bolt in mano; B (verde) ha un orso in campo e Giant Growth in mano."""
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra("Forest") for _ in range(20)]}, seed=2)
    a, b = partita.giocatore("A"), partita.giocatore("B")
    a[Zona.CAMPO].extend([terra(), terra()])
    a[Zona.MANO].extend([bolt(), bolt()])
    b[Zona.CAMPO].extend([orso(), terra("Forest")])
    b[Zona.MANO].append(growth())
    return partita


def rif(p, nome, chi):
    return f"carta:{azioni.trova_in_zona(p, chi, Zona.CAMPO, nome).id}"


def passano_entrambi(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_bolt_uccide_una_creatura(p):
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [rif(p, "grizzly bears", "B")])
    passano_entrambi(p)
    assert azioni.trova_in_zona(p, "B", Zona.CIMITERO, "grizzly bears")
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "lightning bolt")


def test_bolt_al_giocatore(p):
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), ["giocatore:B"])
    passano_entrambi(p)
    assert p.giocatore("B").vita == 17


def test_bolt_senza_bersaglio_non_si_lancia(p):
    with pytest.raises(AzioneIllegale, match="bisogno di un bersaglio"):
        azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"))


def test_giant_growth_solo_su_creature(p):
    p.priorita = 1
    with pytest.raises(AzioneIllegale, match="serve una creatura"):
        azioni.lancia(p, "B", azioni.trova_in_zona(p, "B", Zona.MANO, "giant growth"), ["giocatore:A"])


def test_giant_growth_in_risposta_salva_l_orso(p):
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [rif(p, "grizzly bears", "B")])
    azioni.passa_priorita(p, "A")
    azioni.lancia(p, "B", azioni.trova_in_zona(p, "B", Zona.MANO, "giant growth"), [rif(p, "grizzly bears", "B")])
    passano_entrambi(p)  # risolve Giant Growth
    passano_entrambi(p)  # risolve Bolt
    orso_ = azioni.trova_in_zona(p, "B", Zona.CAMPO, "grizzly bears")
    assert orso_ and orso_.danni == 3 and orso_.costituzione_attuale == 5
    # a fine turno danni e bonus spariscono
    while p.turno == 1:
        azioni.passa_fase(p)
    assert orso_.danni == 0 and orso_.forza_attuale == 2


def test_magia_neutralizzata_se_il_bersaglio_sparisce(p):
    orso_rif = rif(p, "grizzly bears", "B")
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [orso_rif])
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [orso_rif])
    passano_entrambi(p)  # il secondo Bolt uccide l'orso
    passano_entrambi(p)  # il primo non ha più bersaglio
    assert any(e.tipo == "neutralizzata" for e in p.registro.eventi)
    assert p.giocatore("B").vita == 20


def test_comando_con_bersaglio(p):
    assert "in pila" in esegui(p, "A", analizza("gioca lightning bolt su grizzly bears"))
    assert p.pila[-1].bersagli == [rif(p, "grizzly bears", "B")]
    assert "Non trovo" in esegui(p, "A", analizza("gioca lightning bolt su black lotus"))
    assert "in pila" in esegui(p, "A", analizza("gioca lightning bolt su avversaria"))
    assert p.pila[-1].bersagli == ["giocatore:B"]


def test_ai_bolta_la_creatura(p):
    agisci(p, "A")
    assert p.pila[-1].carta.nome == "Lightning Bolt" and p.pila[-1].bersagli == [rif(p, "grizzly bears", "B")]
    agisci(p, "A")  # non spreca il secondo Bolt sullo stesso orso: passa
    assert len(p.pila) == 1 and p.giocatore_con_priorita.nome == "B"


def test_ai_risponde_a_giant_growth(p):
    p.attivo = p.priorita = 1  # turno di B
    b_orso = rif(p, "grizzly bears", "B")
    azioni.lancia(p, "B", azioni.trova_in_zona(p, "B", Zona.MANO, "giant growth"), [b_orso])
    azioni.passa_priorita(p, "B")
    agisci(p, "A")
    assert p.pila[-1].carta.nome == "Lightning Bolt"


def test_ai_bolta_la_faccia_senza_creature(p):
    azioni.distruggi(p, azioni.trova_in_zona(p, "B", Zona.CAMPO, "grizzly bears"))
    agisci(p, "A")  # prima gioca la terra
    agisci(p, "A")
    assert p.pila[-1].bersagli == ["giocatore:B"]
