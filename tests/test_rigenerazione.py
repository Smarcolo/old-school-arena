import pytest

from app.ai.avversaria import agisci, scegli_bloccanti
from app.cards import mazzi
from app.engine import azioni, combattimento
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.zone import Zona


def scheletri():
    return Carta("Drudge Skeletons", "Creature — Skeleton", "{1}{B}", 1, 1, "{B}: Regenerate Drudge Skeletons.")


def palude():
    return Carta("Swamp", "Basic Land — Swamp")


def cr(nome, f, c):
    return Carta(nome, "Creature — Test", "{1}", f, c)


@pytest.fixture
def p():
    partita = nuova_partita({"A": [palude() for _ in range(20)], "B": [palude() for _ in range(20)]}, seed=12)
    partita.turno = 3
    return partita


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def scudo(p, chi, carta):
    azioni.attiva(p, chi, carta, analizza_abilita(carta)[0])
    passano(p)


def test_riconosce_rigenerazione():
    ab = analizza_abilita(scheletri())[0]
    assert (ab.tipo, ab.costo_mana, ab.tappa) == ("rigenera", "{B}", False)


def test_scudo_salva_dai_danni_e_tappa(p):
    s = scheletri()
    p.giocatore("A")[Zona.CAMPO].extend([s, palude()])
    scudo(p, "A", s)
    assert s.scudi_rigenerazione == 1
    azioni.infliggi_danno(p, cr("Fonte", 1, 1), f"carta:{s.id}", 3)
    azioni.azioni_di_stato(p)
    assert s in p.giocatore("A")[Zona.CAMPO] and s.danni == 0 and s.tappata and s.scudi_rigenerazione == 0
    assert any(e.tipo == "rigenera" for e in p.registro.eventi)


def test_senza_scudo_muore(p):
    s = scheletri()
    p.giocatore("A")[Zona.CAMPO].append(s)
    azioni.infliggi_danno(p, cr("Fonte", 1, 1), f"carta:{s.id}", 1)
    azioni.azioni_di_stato(p)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "drudge skeletons")


def test_sacrificio_non_si_rigenera(p):
    s = scheletri()
    s.scudi_rigenerazione = 1
    p.giocatore("A")[Zona.CAMPO].append(s)
    azioni.distruggi(p, s, "(sacrificata)", rigenerabile=False)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "drudge skeletons")


def test_scudo_dura_fino_a_fine_turno(p):
    s = scheletri()
    p.giocatore("A")[Zona.CAMPO].extend([s, palude()])
    scudo(p, "A", s)
    while p.turno == 3:
        azioni.passa_fase(p)
    assert s.scudi_rigenerazione == 0


def test_bloccante_rigenerato_esce_dal_combattimento(p):
    gigante = cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].append(gigante)
    s = scheletri()
    p.giocatore("B")[Zona.CAMPO].extend([s, palude()])
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [gigante])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(s, gigante)])
    azioni.passa_priorita(p, "A")
    scudo(p, "B", s)  # B attiva lo scudo prima dei danni
    passano(p)  # danni
    assert s in p.giocatore("B")[Zona.CAMPO] and s.tappata
    assert p.giocatore("B").vita == 20  # il gigante resta bloccato


def test_ai_rigenera_in_risposta_al_bolt(p):
    s = scheletri()
    p.giocatore("A")[Zona.CAMPO].extend([s, palude()])
    p.attivo = p.priorita = 1
    p.giocatore("B")[Zona.CAMPO].append(Carta("Mountain", "Basic Land — Mountain"))
    p.giocatore("B")[Zona.MANO].append(Carta("Lightning Bolt", "Instant", "{R}"))
    azioni.lancia(p, "B", azioni.trova_in_zona(p, "B", Zona.MANO, "lightning bolt"), [f"carta:{s.id}"])
    azioni.passa_priorita(p, "B")
    agisci(p, "A")
    assert p.pila[-1].descrizione == "abilità di Drudge Skeletons"
    passano(p)
    passano(p)
    assert s in p.giocatore("A")[Zona.CAMPO]


def test_ai_rigenera_in_combattimento_e_blocca_contando_sullo_scudo(p):
    p.attivo = p.priorita = 1  # attacca B
    p.turno = 4
    orso = cr("Orso", 2, 2)
    p.giocatore("B")[Zona.CAMPO].append(orso)
    s = scheletri()
    p.giocatore("A")[Zona.CAMPO].extend([s, palude()])
    passano(p)
    combattimento.dichiara_attaccanti(p, "B", [orso])
    passano(p)
    blocchi = scegli_bloccanti(p, "A")
    assert [(b.nome, a.nome) for b, a in blocchi] == [("Drudge Skeletons", "Orso")]
    combattimento.dichiara_bloccanti(p, "A", blocchi)
    azioni.passa_priorita(p, "B")
    agisci(p, "A")
    assert p.pila[-1].descrizione == "abilità di Drudge Skeletons"


def test_analisi_mazzo_capisce_la_rigenerazione(conn):
    a = mazzi.analizza(conn, {"Drudge Skeletons": 4, "Will-o'-the-Wisp": 4, "Swamp": 52}, {})
    assert not any("Skeletons" in x or "Wisp" in x for x in a["avvisi"])
