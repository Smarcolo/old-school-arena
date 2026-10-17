import json
from pathlib import Path

import pytest

from app.cards import mazzi
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

BASE = {c["nome"]: c for c in json.loads(Path("app/cards/carte_base.json").read_text())}


def carta(nome):
    d = BASE[nome]
    return Carta(d["nome"], d["tipo"], d.get("costo", ""), d.get("forza"), d.get("costituzione"), d.get("testo", ""))


def cr(nome, f, c, costo="{G}", tipo="Creature — Test"):
    return Carta(nome, tipo, costo, f, c)


def terra(tipo="Plains"):
    return Carta(tipo, f"Basic Land — {tipo}")


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(30)], "B": [terra() for _ in range(30)]}, seed=30)
    partita.turno = 3
    return partita


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def risolvi(p):
    while p.pila:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def fino_a(p, turno, fase):
    for _ in range(300):
        if p.turno == turno and p.fase == fase and not p.pila and not p.scelta:
            return
        if p.scelta:
            from app.ai.avversaria import decidi_scelta
            decidi_scelta(p, p.scelta.giocatore)
        else:
            azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    raise AssertionError("non arriva")


def test_moat(p):
    p.giocatore("A")[Zona.CAMPO].extend([carta("Moat"), cr("Orso", 2, 2), carta("Serendib Efreet") if "Serendib Efreet" in BASE else cr("Volante", 1, 1)])
    volante = cr("Uccello", 1, 1)
    volante.testo = "Flying"
    p.giocatore("A")[Zona.CAMPO].append(volante)
    passano(p)
    assert [c.nome for c in combattimento.possibili_attaccanti(p, "A")] == [c.nome for c in p.giocatore("A")[Zona.CAMPO] if c.ha("flying")]


def test_the_abyss(p):
    p.giocatore("B")[Zona.CAMPO].append(carta("The Abyss"))
    debole, forte, golem = cr("Debole", 1, 1), cr("Forte", 5, 5), Carta("Golem", "Artifact Creature — Golem", "{3}", 3, 3)
    forte.scudi_rigenerazione = 1
    p.giocatore("A")[Zona.CAMPO].extend([debole, forte, golem])
    fino_a(p, 4, Fase.PESCATA)  # mantenimento di B: B non ha creature
    assert len([c for c in p.giocatore("A")[Zona.CAMPO] if c.is_creatura]) == 3
    p.scelte_manuali = {"A"}
    for _ in range(50):
        if p.scelta:
            break
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    assert p.scelta.tipo == "scegli" and set(p.scelta.dati["carte"]) == {debole.id, forte.id}  # non l'artefatto
    assert esegui(p, "A", analizza("scelgo forte")) == "Fatto."
    assert forte in p.giocatore("A")[Zona.CIMITERO]  # niente rigenerazione


def test_hypnotic_specter(p):
    specter = carta("Hypnotic Specter")
    p.giocatore("A")[Zona.CAMPO].append(specter)
    prima = len(p.giocatore("B")[Zona.MANO])
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [specter])
    risolvi(p)
    passano(p)  # blocchi: B non ha volanti, saltati
    passano(p)  # danni
    assert p.pila and p.pila[-1].descrizione == "innesco di Hypnotic Specter"
    risolvi(p)
    assert p.giocatore("B").vita == 18 and len(p.giocatore("B")[Zona.MANO]) == prima - 1


def test_sengir_vampire(p):
    sengir = carta("Sengir Vampire")
    p.giocatore("A")[Zona.CAMPO].append(sengir)
    volante = cr("Uccello", 2, 2)
    volante.testo = "Flying"
    p.giocatore("B")[Zona.CAMPO].append(volante)
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [sengir])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(volante, sengir)])
    passano(p)
    assert sengir.segnalini == 0 and p.pila[-1].innesco.effetto == "segnalino_su_se"  # l'innesco va in pila
    passano(p)
    assert sengir.segnalini == 1 and sengir.forza_attuale == 5


def test_erhnam_djinn(p):
    erhnam = carta("Erhnam Djinn")
    p.giocatore("A")[Zona.CAMPO].append(erhnam)
    debole, muro = cr("Debole", 1, 1), Carta("Muro", "Creature — Wall", "{1}", 0, 5)
    p.giocatore("B")[Zona.CAMPO].extend([debole, muro, cr("Forte", 4, 4)])
    fino_a(p, 5, Fase.PESCATA)  # mantenimento di A al turno 5
    assert debole.ha("forestwalk") and not muro.ha("forestwalk")
    fino_a(p, 7, Fase.PESCATA)
    # al mantenimento successivo l'effetto finisce e ne riparte uno nuovo (di nuovo sulla più debole)
    assert debole.passaforeste_fino_al_turno == 9


def test_mishras_factory(p):
    factory = carta("Mishra's Factory")
    p.giocatore("A")[Zona.CAMPO].extend([factory, terra()])
    ab = analizza_abilita(factory)
    assert [x.tipo for x in ab] == ["anima", "pompa_bersaglio"]
    azioni.attiva(p, "A", factory, ab[0])
    risolvi(p)
    assert factory.is_creatura and factory.forza_attuale == 2 and "Assembly-Worker" in factory.tipo_attuale
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [factory])
    assert factory.tappata
    while p.turno == 3:
        azioni.passa_fase(p)
    assert not factory.is_creatura


def test_kird_ape_e_sedge_troll(p):
    ape, troll = carta("Kird Ape"), carta("Sedge Troll")
    p.giocatore("A")[Zona.CAMPO].extend([ape, troll])
    azioni.azioni_di_stato(p)
    assert (ape.forza_attuale, troll.forza_attuale) == (1, 2)
    p.giocatore("A")[Zona.CAMPO].extend([terra("Forest"), terra("Swamp")])
    azioni.azioni_di_stato(p)
    assert (ape.forza_attuale, ape.costituzione_attuale, troll.forza_attuale) == (2, 3, 3)


def test_disrupting_scepter(p):
    scettro = carta("Disrupting Scepter")
    p.giocatore("A")[Zona.CAMPO].extend([scettro, terra(), terra(), terra()])
    ab = analizza_abilita(scettro)[0]
    prima = len(p.giocatore("B")[Zona.MANO])
    azioni.attiva(p, "A", scettro, ab, ["giocatore:B"])
    risolvi(p)
    assert len(p.giocatore("B")[Zona.MANO]) == prima - 1
    p.attivo, p.priorita = 1, 0  # turno di B, ma A ha la priorità
    with pytest.raises(AzioneIllegale, match="solo nel tuo turno"):
        azioni.attiva(p, "A", scettro, ab, ["giocatore:B"])


def test_su_chi(p):
    suchi = carta("Su-Chi")
    p.giocatore("A")[Zona.CAMPO].append(suchi)
    azioni.distruggi(p, suchi)
    risolvi(p)
    assert p.giocatore("A").riserva["C"] == 4


def test_triskelion(p):
    tris = carta("Triskelion")
    p.giocatore("A")[Zona.MANO].append(tris)
    p.giocatore("A")[Zona.CAMPO].extend(terra() for _ in range(6))
    azioni.lancia(p, "A", tris)
    risolvi(p)
    assert tris.segnalini == 3 and tris.forza_attuale == 4
    elfo = cr("Elfo", 1, 1)
    p.giocatore("B")[Zona.CAMPO].append(elfo)
    assert "in pila" in esegui(p, "A", analizza("attiva triskelion su elfo"))
    risolvi(p)
    assert elfo in p.giocatore("B")[Zona.CIMITERO] and tris.segnalini == 2


def test_juggernaut(p):
    jugg = carta("Juggernaut")
    p.giocatore("A")[Zona.CAMPO].extend([jugg, cr("Orso", 2, 2)])
    muro = Carta("Muro", "Creature — Wall", "{1}", 0, 8, "Defender")
    p.giocatore("B")[Zona.CAMPO].append(muro)
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [])
    assert p.combattimento.attaccanti == [jugg.id]  # attacca comunque
    assert "muri" in combattimento.puo_bloccare_contro(p, "B", muro, jugg)


def test_ali_from_cairo(p):
    p.giocatore("A")[Zona.CAMPO].append(carta("Ali from Cairo"))
    p.giocatore("A").vita = 3
    azioni.danni_a_giocatore(p, cr("Fonte", 1, 1, "{R}"), "A", 10)
    assert p.giocatore("A").vita == 1 and not p.vincitore
    azioni.modifica_vita(p, "A", -5, "(perdita di vita, non danni)")
    azioni.azioni_di_stato(p)
    assert p.vincitore == "B"


def test_analisi_capisce_le_carte_del_torneo(conn):
    nomi = ["Moat", "The Abyss", "Hypnotic Specter", "Sengir Vampire", "Erhnam Djinn", "Mishra's Factory", "Kird Ape",
            "Sedge Troll", "Disrupting Scepter", "Su-Chi", "Triskelion", "Juggernaut", "Ali from Cairo"]
    a = mazzi.analizza(conn, {n: 1 for n in nomi}, {})
    assert [x for x in a["avvisi"] if any(n in x for n in nomi)] == []
