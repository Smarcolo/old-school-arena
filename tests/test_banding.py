import pytest

from app.ai.avversaria import scegli_bande
from app.cards import mazzi
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def eroe(nome="Eroe"):
    return Carta(nome, "Creature — Human Soldier", "{W}", 1, 1, "Banding")


def cr(nome, f, c, testo=""):
    return Carta(nome, "Creature — Test", "{1}", f, c, testo)


def terra():
    return Carta("Plains", "Basic Land — Plains")


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra() for _ in range(20)]}, seed=16)
    partita.turno = 3
    return partita


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def al_combattimento(p):
    passano(p)
    assert p.fase == Fase.COMBATTIMENTO


def test_regole_della_banda(p):
    e, orso, gigante = eroe(), cr("Orso", 2, 2), cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].extend([e, orso, gigante])
    al_combattimento(p)
    with pytest.raises(AzioneIllegale, match="al massimo una"):
        combattimento.dichiara_attaccanti(p, "A", [e, orso, gigante], [[e, orso, gigante]])
    with pytest.raises(AzioneIllegale, match="solo creature che attaccano"):
        combattimento.dichiara_attaccanti(p, "A", [e], [[e, orso]])
    combattimento.dichiara_attaccanti(p, "A", [e, orso, gigante], [[e, orso]])
    assert p.combattimento.bande == [[e.id, orso.id]]


def test_chi_blocca_un_membro_blocca_tutta_la_banda(p):
    e, gigante = eroe(), cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].extend([e, gigante])
    muro = cr("Muro", 0, 6)
    p.giocatore("B")[Zona.CAMPO].append(muro)
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [e, gigante], [[e, gigante]])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(muro, e)])
    assert p.combattimento.blocchi == {e.id: [muro.id], gigante.id: [muro.id]}
    passano(p)
    assert p.giocatore("B").vita == 20  # tutta la banda è bloccata
    assert muro.danni == 4  # 1 dell'eroe + 3 del gigante


def test_l_attaccante_divide_i_danni_del_bloccante(p):
    e, gigante = eroe(), cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].extend([e, gigante])
    orco = cr("Orco", 2, 2)
    p.giocatore("B")[Zona.CAMPO].append(orco)
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [e, gigante], [[e, gigante]])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(orco, e)])  # blocca "l'eroe"...
    passano(p)
    # ...ma i 2 danni dell'orco li assegna A: vanno sul gigante, che sopravvive; l'eroe è salvo
    assert e in p.giocatore("A")[Zona.CAMPO] and gigante.danni == 2
    assert azioni.trova_in_zona(p, "B", Zona.CIMITERO, "orco")


def test_banding_in_difesa_divide_i_danni_dell_attaccante(p):
    gigante = cr("Gigante", 3, 3, "Trample")
    p.giocatore("A")[Zona.CAMPO].append(gigante)
    e, muro = eroe(), cr("Muro", 0, 5)
    p.giocatore("B")[Zona.CAMPO].extend([e, muro])
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [gigante])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(e, gigante), (muro, gigante)])
    passano(p)
    # B divide i 3 danni: tutti sul muro; niente travolgere oltre, l'eroe sopravvive
    assert e in p.giocatore("B")[Zona.CAMPO] and muro.danni == 3 and p.giocatore("B").vita == 20


def test_senza_banding_l_ordine_resta_quello_normale(p):
    gigante = cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].append(gigante)
    elfo, muro = cr("Elfo", 1, 1), cr("Muro", 0, 5)
    p.giocatore("B")[Zona.CAMPO].extend([elfo, muro])
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [gigante])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(elfo, gigante), (muro, gigante)])
    passano(p)
    assert azioni.trova_in_zona(p, "B", Zona.CIMITERO, "elfo") and muro.danni == 2


def test_comando_attacca_in_banda(p):
    e, orso = eroe(), cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].extend([e, orso])
    al_combattimento(p)
    msg = esegui(p, "A", analizza("attacca con eroe + orso"))
    assert "In banda: Eroe + Orso" in msg and p.combattimento.bande == [[e.id, orso.id]]


def test_ai_forma_la_banda_con_il_piu_forte():
    e, orso, gigante = eroe(), cr("Orso", 2, 2), cr("Gigante", 3, 3)
    assert scegli_bande([e, orso, gigante]) == [[e, gigante]]
    assert scegli_bande([orso, gigante]) == []


def test_analisi_mazzo_capisce_il_banding(conn):
    a = mazzi.analizza(conn, {"Benalish Hero": 4, "Timber Wolves": 4, "Plains": 26, "Forest": 26}, {})
    assert not any("Hero" in x or "Wolves" in x for x in a["avvisi"])


def test_divisione_manuale_in_attacco(p):
    p.scelte_manuali = {"A"}
    e, gigante = eroe(), cr("Gigante", 3, 3)
    p.giocatore("A")[Zona.CAMPO].extend([e, gigante])
    orco = cr("Orco", 2, 2)
    p.giocatore("B")[Zona.CAMPO].append(orco)
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [e, gigante], [[e, gigante]])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(orco, gigante)])
    passano(p)
    assert p.scelta and p.scelta.tipo == "danni" and p.scelta.giocatore == "A"
    assert set(p.scelta.dati["candidate"]) == {e.id, gigante.id} and p.scelta.dati["danni"] == 2
    with pytest.raises(AzioneIllegale, match="esattamente 2"):
        combattimento.assegna_danni(p, "A", {e.id: 1})
    assert esegui(p, "A", analizza("danni 1 su eroe, 1 su gigante")) == "Danni divisi."
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "eroe") and gigante.danni == 1
    assert p.combattimento.danni_inflitti and p.scelta is None


def test_divisione_manuale_in_difesa_con_attacca_per_primo(p):
    p.scelte_manuali = {"B"}
    arcieri = cr("Arcieri", 2, 1, "First strike")
    p.giocatore("A")[Zona.CAMPO].append(arcieri)
    e, muro = eroe(), cr("Muro", 0, 5)
    p.giocatore("B")[Zona.CAMPO].extend([e, muro])
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [arcieri])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(e, arcieri), (muro, arcieri)])
    passano(p)
    assert p.scelta.giocatore == "B" and p.scelta.dati["nome_fonte"] == "Arcieri"
    esegui(p, "B", analizza("danni su muro"))
    # primo passo: 2 danni sul muro; secondo passo: l'eroe (1/1) infligge 1 danno agli arcieri, che muoiono
    assert muro.danni == 2 and e in p.giocatore("B")[Zona.CAMPO]
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "arcieri")


def test_una_sola_candidata_niente_domanda(p):
    p.scelte_manuali = {"A", "B"}
    e = eroe()
    p.giocatore("A")[Zona.CAMPO].append(e)
    orco = cr("Orco", 2, 2)
    p.giocatore("B")[Zona.CAMPO].append(orco)
    al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [e])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(orco, e)])
    passano(p)
    assert p.scelta is None and p.combattimento.danni_inflitti
