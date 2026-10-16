import pytest

from app.ai.avversaria import agisci, scegli_attaccanti
from app.cards import mazzi
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni
from app.engine.inneschi import analizza_inneschi
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona
from app.regia import esegui_comando

JUZAM = ("Juzám Djinn", "Creature — Djinn", "{2}{B}{B}", 5, 5, "At the beginning of your upkeep, Juzám Djinn deals 1 damage to you.")
VISE = ("Black Vise", "Artifact", "{1}", None, None,
        "As Black Vise enters the battlefield, choose an opponent.\nAt the beginning of the chosen player's upkeep, "
        "Black Vise deals X damage to that player, where X is the number of cards in their hand minus 4.")
MINE = ("Howling Mine", "Artifact", "{2}", None, None,
        "At the beginning of each player's draw step, if Howling Mine is untapped, that player draws an additional card.")
BALL = ("Ball Lightning", "Creature — Elemental", "{R}{R}{R}", 6, 1, "Trample, haste\nAt the beginning of the end step, sacrifice Ball Lightning.")
FORCE = ("Force of Nature", "Creature — Elemental", "{2}{G}{G}{G}{G}", 8, 8,
         "Trample\nAt the beginning of your upkeep, Force of Nature deals 8 damage to you unless you pay {G}{G}{G}{G}.")
TOWER = ("Ivory Tower", "Artifact", "{1}", None, None,
         "At the beginning of your upkeep, you gain X life, where X is the number of cards in your hand minus 4.")


def carta(dati):
    return Carta(*dati)


def foresta():
    return Carta("Forest", "Basic Land — Forest")


@pytest.fixture
def p():
    return nuova_partita({"A": [foresta() for _ in range(30)], "B": [foresta() for _ in range(30)]}, seed=8)


def fino_a(p, fase, turno):
    """Avanza risolvendo da solo pile e scelte (paga se può) fino all'inizio di quella fase di quel turno."""
    for _ in range(200):
        if p.turno == turno and p.fase == fase:
            return
        if p.scelta:
            azioni.rispondi_scelta(p, p.scelta.giocatore, azioni.puo_pagare_scelta(p))
        else:
            azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    raise AssertionError("non arriva mai")


def test_riconoscimento():
    assert [i.effetto for i in analizza_inneschi(carta(JUZAM))] == ["danno_te"]
    vise = analizza_inneschi(carta(VISE))[0]
    assert (vise.momento, vise.chi, vise.n) == ("mantenimento", "avversario", 4)
    assert analizza_inneschi(carta(MINE))[0].se_stappata
    lord = Carta("Lord of the Pit", "Creature", testo="At the beginning of your upkeep, sacrifice a creature other than "
                 "Lord of the Pit. If you can't, Lord of the Pit deals 7 damage to you.")
    assert analizza_inneschi(lord) == []


def test_juzam_colpisce_nel_proprio_mantenimento(p):
    p.giocatore("A")[Zona.CAMPO].append(carta(JUZAM))
    fino_a(p, Fase.PESCATA, 2)  # mantenimento di B: niente
    assert p.giocatore("A").vita == 20
    fino_a(p, Fase.PESCATA, 3)  # mantenimento di A
    assert p.giocatore("A").vita == 19


def test_black_vise_colpisce_l_avversario_con_la_mano_piena(p):
    p.giocatore("A")[Zona.CAMPO].append(carta(VISE))
    fino_a(p, Fase.MANTENIMENTO, 2)
    assert [o.descrizione for o in p.pila] == ["innesco di Black Vise"]
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "A")
    assert p.giocatore("B").vita == 17  # 7 carte in mano - 4
    fino_a(p, Fase.PESCATA, 3)
    assert p.giocatore("A").vita == 20  # non colpisce chi la controlla


def test_howling_mine_solo_se_stappata(p):
    mine = carta(MINE)
    p.giocatore("A")[Zona.CAMPO].append(mine)
    fino_a(p, Fase.PRINCIPALE_1, 2)
    assert len(p.giocatore("B")[Zona.MANO]) == 9  # 7 + pescata + Howling Mine
    mine.tappata = True
    fino_a(p, Fase.PRINCIPALE_1, 3)
    mine.tappata = True  # A la stappa nel suo stap: la ritappo prima della pescata del turno dopo
    fino_a(p, Fase.PRINCIPALE_1, 4)
    assert len(p.giocatore("B")[Zona.MANO]) == 10


def test_ball_lightning_sacrificata_a_fine_turno(p):
    p.giocatore("A")[Zona.CAMPO].append(carta(BALL))
    fino_a(p, Fase.FINALE, 1)
    assert p.pila and p.pila[-1].descrizione == "innesco di Ball Lightning"
    fino_a(p, Fase.STAP, 2)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "ball lightning")


def test_force_of_nature_paga_o_subisce(p):
    a = p.giocatore("A")
    a[Zona.CAMPO].extend([carta(FORCE)] + [foresta() for _ in range(4)])
    for _ in range(2):
        while not (p.turno == 3 and p.scelta):
            azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
        break
    assert p.scelta.giocatore == "A" and p.scelta.costo == "{G}{G}{G}{G}"
    with pytest.raises(AzioneIllegale, match="rispondere"):
        azioni.passa_priorita(p, "A")
    with pytest.raises(AzioneIllegale, match="tocca a A"):
        azioni.rispondi_scelta(p, "B", True)
    assert esegui(p, "A", analizza("paga")) == "Hai pagato."
    assert a.vita == 20 and sum(c.tappata for c in a[Zona.CAMPO]) == 4


def test_force_of_nature_senza_mana(p):
    a = p.giocatore("A")
    a[Zona.CAMPO].append(carta(FORCE))
    while not (p.turno == 3 and p.scelta):
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    with pytest.raises(AzioneIllegale, match="abbastanza mana"):
        azioni.rispondi_scelta(p, "A", True)
    azioni.rispondi_scelta(p, "A", False)
    assert a.vita == 12


def test_ivory_tower(p):
    p.giocatore("A")[Zona.CAMPO].append(carta(TOWER))
    fino_a(p, Fase.PESCATA, 3)
    assert p.giocatore("A").vita == 23  # 7 carte in mano - 4


def test_innesco_quando_entra():
    p = nuova_partita({"A": [foresta() for _ in range(20)], "B": [foresta() for _ in range(20)]}, seed=9)
    a = p.giocatore("A")
    a[Zona.CAMPO].append(foresta())
    a[Zona.MANO].append(Carta("Healer", "Creature — Test", "{G}", 1, 1, "When Healer enters the battlefield, you gain 3 life."))
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "healer"))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.pila[-1].descrizione == "innesco di Healer"
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert a.vita == 23


def test_ai_paga_force_of_nature_e_umano_viene_fermato():
    p = nuova_partita({"Tu": [foresta() for _ in range(30)], "AI": [foresta() for _ in range(30)]}, seed=10)
    p.giocatore("AI")[Zona.CAMPO].extend([carta(FORCE)] + [foresta() for _ in range(4)])
    p.giocatore("Tu")[Zona.CAMPO].append(carta(FORCE))
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.giocatore("AI").vita == 20  # l'AI ha pagato
    # turno 3: l'umano deve scegliere e la regia si ferma
    while p.turno < 3 and not p.scelta:
        esegui_comando(p, "Tu", "AI", "passa" if p.pila or p.combattimento else "fine turno")
    assert p.scelta and p.scelta.giocatore == "Tu"
    vita = p.giocatore("Tu").vita  # l'AI potrebbe averti già attaccato con il suo Force of Nature
    msg = esegui_comando(p, "Tu", "AI", "non pago")
    assert p.giocatore("Tu").vita == vita - 8 and msg.startswith("Non hai pagato.")


def test_ai_attacca_sempre_con_ball_lightning(p):
    p.turno = 3
    ball = carta(BALL)
    p.giocatore("A")[Zona.CAMPO].append(ball)
    p.giocatore("B")[Zona.CAMPO].append(Carta("Muro", "Creature — Wall", "{1}", 0, 8))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert scegli_attaccanti(p, "A") == [ball]


def test_analisi_mazzo_capisce_gli_inneschi(conn):
    a = mazzi.analizza(conn, {"Black Vise": 1, "Ball Lightning": 4, "Juzám Djinn": 4, "Force of Nature": 1, "Forest": 50}, {})
    assert not any(n in x for x in a["avvisi"] for n in ("Black Vise", "Ball Lightning", "Juzám", "Force of Nature"))


def test_vista_mostra_la_scelta_all_umano():
    from app.api.main import vista
    p = nuova_partita({"Tu": [foresta() for _ in range(30)], "Avversaria": [foresta() for _ in range(30)]}, seed=11)
    p.giocatore("Tu")[Zona.CAMPO].append(carta(FORCE))
    while not p.scelta:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    v = vista(p)
    assert v["richiesta"] == "scelta" and v["scelta"]["carta"] == "Force of Nature" and v["scelta"]["costo"] == "{G}{G}{G}{G}"
