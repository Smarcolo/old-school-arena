import pytest

from app.ai.avversaria import scegli_attaccanti, scegli_bloccanti
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona
from app.regia import esegui_comando


def creatura(nome, f, c):
    return Carta(nome, "Creature — Test", "{1}", f, c)


def terra():
    return Carta("Forest", "Basic Land — Forest")


@pytest.fixture
def p():
    """Turno 3 di A, fase principale 1. A: orso 2/2 e gigante 3/3. B: elfo 1/1 e muro 0/4."""
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra() for _ in range(20)]}, seed=4)
    partita.turno = 3
    partita.giocatore("A")[Zona.CAMPO].extend([creatura("Orso", 2, 2), creatura("Gigante", 3, 3)])
    partita.giocatore("B")[Zona.CAMPO].extend([creatura("Elfo", 1, 1), creatura("Muro", 0, 4)])
    return partita


def vai_al_combattimento(p):
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.fase == Fase.COMBATTIMENTO and p.combattimento is not None


def c(p, chi, nome):
    return azioni.trova_in_zona(p, chi, Zona.CAMPO, nome)


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_attacco_non_bloccato(p):
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso"), c(p, "A", "gigante")])
    assert c(p, "A", "orso").tappata
    passano(p)
    assert p.combattimento.attesa_bloccanti and p.giocatore_con_priorita.nome == "B"
    combattimento.dichiara_bloccanti(p, "B", [])
    passano(p)
    assert p.giocatore("B").vita == 15
    passano(p)
    assert p.fase == Fase.PRINCIPALE_2 and p.combattimento is None


def test_blocchi_e_danni(p):
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso"), c(p, "A", "gigante")])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(c(p, "B", "muro"), c(p, "A", "gigante")), (c(p, "B", "elfo"), c(p, "A", "orso"))])
    passano(p)
    assert p.giocatore("B").vita == 20
    assert c(p, "B", "elfo") is None and c(p, "B", "muro").danni == 3
    assert c(p, "A", "orso").danni == 1


def test_doppio_blocco_divide_i_danni(p):
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "gigante")])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(c(p, "B", "elfo"), c(p, "A", "gigante")), (c(p, "B", "muro"), c(p, "A", "gigante"))])
    passano(p)
    assert c(p, "B", "elfo") is None  # 1 danno letale all'elfo
    assert c(p, "B", "muro").danni == 2  # il resto al muro
    assert c(p, "A", "gigante").danni == 1


def test_creatura_appena_entrata_non_attacca(p):
    c(p, "A", "orso").entrata_nel_turno = 3
    vai_al_combattimento(p)
    with pytest.raises(AzioneIllegale, match="non può attaccare"):
        combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso")])


def test_tappata_non_blocca(p):
    c(p, "B", "muro").tappata = True
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "gigante")])
    passano(p)
    with pytest.raises(AzioneIllegale, match="tappata"):
        combattimento.dichiara_bloccanti(p, "B", [(c(p, "B", "muro"), c(p, "A", "gigante"))])


def test_senza_bloccanti_possibili_si_salta_il_blocco(p):
    for x in p.giocatore("B")[Zona.CAMPO]:
        x.tappata = True
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso")])
    passano(p)
    assert p.combattimento.bloccanti_dichiarati and not p.combattimento.attesa_bloccanti


def test_nessun_attacco_chiude_la_fase(p):
    vai_al_combattimento(p)
    passano(p)
    assert p.fase == Fase.PRINCIPALE_2


def test_giant_growth_dopo_i_blocchi(p):
    p.giocatore("A")[Zona.MANO].append(Carta("Giant Growth", "Instant", "{G}"))
    p.giocatore("A")[Zona.CAMPO].append(terra())
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso")])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(c(p, "B", "muro"), c(p, "A", "orso"))])
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "giant growth"), [f"carta:{c(p, 'A', 'orso').id}"])
    passano(p)  # risolve Giant Growth
    passano(p)  # danni: orso 5/5 contro muro 0/4
    assert c(p, "B", "muro") is None


def test_comandi_attacca_e_blocca(p):
    vai_al_combattimento(p)
    assert esegui(p, "A", analizza("attacca con orso e gigante")) == "Attacchi con Orso, Gigante."
    passano(p)
    msg = esegui(p, "B", analizza("blocca gigante con muro; orso con elfo"))
    assert msg.startswith("Blocchi:") and len(p.combattimento.bloccanti()) == 2


def test_comando_attacca_con_tutto_e_passa_come_nessun_blocco(p):
    vai_al_combattimento(p)
    esegui(p, "A", analizza("attacca con tutto"))
    passano(p)
    assert esegui(p, "B", analizza("passa")) == "Non blocchi."


def test_ai_non_attacca_contro_un_muro(p):
    vai_al_combattimento(p)
    # il Muro 0/4 blocca l'orso 2/2 senza morire e senza ucciderlo: l'orso non rischia, attacca
    # l'elfo 1/1 non uccide nessuno; quindi entrambi attaccano
    assert {x.nome for x in scegli_attaccanti(p, "A")} == {"Orso", "Gigante"}
    p.giocatore("B")[Zona.CAMPO].append(creatura("Ogre", 3, 3))
    # l'Ogre 3/3 ucciderebbe l'orso senza morire: l'orso resta a casa
    assert {x.nome for x in scegli_attaccanti(p, "A")} == {"Gigante"}


def test_ai_blocca_bene(p):
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso"), c(p, "A", "gigante")])
    passano(p)
    blocchi = {(b.nome, a.nome) for b, a in scegli_bloccanti(p, "B")}
    assert ("Muro", "Gigante") in blocchi  # sopravvive al più forte
    assert ("Elfo", "Orso") not in blocchi  # non regala l'elfo


def test_ai_blocca_in_emergenza(p):
    p.giocatore("B").vita = 2  # il Muro ferma il Gigante, ma i 2 danni dell'Orso sarebbero letali
    vai_al_combattimento(p)
    combattimento.dichiara_attaccanti(p, "A", [c(p, "A", "orso"), c(p, "A", "gigante")])
    passano(p)
    assert len(scegli_bloccanti(p, "B")) == 2


def test_regia_ferma_l_umano_per_bloccare():
    p = nuova_partita({"Tu": [terra() for _ in range(20)], "AI": [terra() for _ in range(20)]}, seed=5)
    p.giocatore("AI")[Zona.CAMPO].append(creatura("Gigante", 3, 3))
    p.giocatore("Tu")[Zona.CAMPO].append(creatura("Muro", 0, 4))
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.giocatore_attivo.nome == "AI" and p.combattimento.attesa_bloccanti
    esegui_comando(p, "Tu", "AI", "blocca gigante con muro")
    assert p.giocatore("Tu").vita == 20 and p.giocatore_attivo.nome == "Tu" and p.turno == 3
