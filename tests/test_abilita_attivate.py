import pytest

from app.ai.avversaria import agisci
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def terra(tipo="Mountain"):
    return Carta(tipo, f"Basic Land — {tipo}")


def drago():
    return Carta("Shivan Dragon", "Creature — Dragon", "{4}{R}{R}", 5, 5, "Flying\n{R}: Shivan Dragon gets +1/+0 until end of turn.")


def stregone():
    return Carta("Prodigal Sorcerer", "Creature — Human Wizard", "{2}{U}", 1, 1, "{T}: Prodigal Sorcerer deals 1 damage to any target.")


def cr(nome, f, c):
    return Carta(nome, "Creature — Test", "{1}", f, c)


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra("Forest") for _ in range(20)]}, seed=7)
    partita.turno = 3
    return partita


def metti(p, chi, *carte):
    p.giocatore(chi)[Zona.CAMPO].extend(carte)
    return carte[0] if len(carte) == 1 else carte


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_firebreathing(p):
    d = metti(p, "A", drago())
    metti(p, "A", terra(), terra())
    ab = analizza_abilita(d)[0]
    azioni.attiva(p, "A", d, ab)
    azioni.attiva(p, "A", d, ab)
    assert len(p.pila) == 2 and p.pila[-1].descrizione == "abilità di Shivan Dragon"
    passano(p)
    passano(p)
    assert d.forza_attuale == 7 and d in p.giocatore("A")[Zona.CAMPO]
    with pytest.raises(AzioneIllegale, match="abbastanza mana"):
        azioni.attiva(p, "A", d, ab)
    while p.turno == 3:
        azioni.passa_fase(p)
    assert d.forza_attuale == 5


def test_stregone_tappa_e_colpisce(p):
    s = metti(p, "A", stregone())
    orso = metti(p, "B", cr("Elfo", 1, 1))
    azioni.attiva(p, "A", s, analizza_abilita(s)[0], [f"carta:{orso.id}"])
    assert s.tappata
    passano(p)
    assert azioni.trova_in_zona(p, "B", Zona.CIMITERO, "elfo")
    with pytest.raises(AzioneIllegale, match="tappata"):
        azioni.attiva(p, "A", s, analizza_abilita(s)[0], ["giocatore:B"])


def test_stregone_appena_entrato_non_tappa(p):
    s = metti(p, "A", stregone())
    s.entrata_nel_turno = p.turno
    with pytest.raises(AzioneIllegale, match="entrata in questo turno"):
        azioni.attiva(p, "A", s, analizza_abilita(s)[0], ["giocatore:B"])


def test_abilita_senza_bersaglio_richiesto(p):
    s = metti(p, "A", stregone())
    with pytest.raises(AzioneIllegale, match="bisogno di un bersaglio"):
        azioni.attiva(p, "A", s, analizza_abilita(s)[0], [])


def test_comando_attiva(p):
    metti(p, "A", stregone())
    assert "in pila" in esegui(p, "A", analizza("attiva prodigal sorcerer su avversaria"))
    passano(p)
    assert p.giocatore("B").vita == 19
    metti(p, "A", cr("Orso", 2, 2))
    assert "non ha abilità" in esegui(p, "A", analizza("attiva orso"))


def test_ai_pompa_l_attaccante_non_bloccato(p):
    d = metti(p, "A", drago())
    metti(p, "A", terra(), terra())
    passano(p)  # al combattimento
    combattimento.dichiara_attaccanti(p, "A", [d])
    passano(p)  # B non può bloccare un volatore: blocchi saltati
    agisci(p, "A")
    agisci(p, "A")
    assert len(p.pila) == 2  # due {R}, due attivazioni


def test_ai_stregone_uccide_creatura_e_poi_colpisce_a_fine_turno(p):
    p.attivo = p.priorita = 1  # turno di B
    s = metti(p, "A", stregone())
    elfo = metti(p, "B", cr("Elfo", 1, 1))
    p.priorita = 0
    agisci(p, "A")
    assert p.pila[-1].bersagli == [f"carta:{elfo.id}"]
    p.pila.clear()
    s.tappata = False
    azioni.distruggi(p, elfo)
    agisci(p, "A")  # niente da uccidere e non è la fase finale: passa
    assert not p.pila
    p.fase, p.priorita, p.passaggi = Fase.FINALE, 0, 0
    agisci(p, "A")
    assert p.pila[-1].bersagli == ["giocatore:B"]


def test_ai_salva_con_giant_growth(p):
    p.attivo = p.priorita = 1
    gigante = metti(p, "A", cr("Gigante", 3, 3))
    metti(p, "A", terra("Forest"))
    p.giocatore("A")[Zona.MANO].append(Carta("Giant Growth", "Instant", "{G}"))
    p.giocatore("B")[Zona.MANO].append(Carta("Lightning Bolt", "Instant", "{R}"))
    metti(p, "B", terra())
    azioni.lancia(p, "B", azioni.trova_in_zona(p, "B", Zona.MANO, "lightning bolt"), [f"carta:{gigante.id}"])
    azioni.passa_priorita(p, "B")
    agisci(p, "A")
    assert p.pila[-1].carta.nome == "Giant Growth"
    passano(p)
    passano(p)
    assert gigante in p.giocatore("A")[Zona.CAMPO]
