import json
from pathlib import Path

from app.ai.avversaria import agisci, factory_da_animare, lascia_contromagia, permanente_utile, scegli_attaccanti
from app.engine import azioni, combattimento
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.zone import Zona

BASE = {c["nome"]: c for c in json.loads(Path("app/cards/carte_base.json").read_text())}


def carta(nome):
    d = BASE[nome]
    return Carta(d["nome"], d["tipo"], d.get("costo", ""), d.get("forza"), d.get("costituzione"), d.get("testo", ""))


def cr(nome, f, c, testo=""):
    return Carta(nome, "Creature — Test", "{1}", f, c, testo)


def p_base():
    p = nuova_partita({"AI": [carta("Island") for _ in range(30)], "B": [carta("Forest") for _ in range(30)]}, seed=40)
    p.turno = 5
    return p


def test_gioca_subito_i_mox():
    p = p_base()
    ai = p.giocatore("AI")
    ai[Zona.MANO][:] = [carta("Serra Angel"), carta("Mox Pearl")]
    ai[Zona.CAMPO].extend(carta("Plains") for _ in range(5))
    ai.terre_giocate_nel_turno = 1
    agisci(p, "AI")
    assert p.pila[-1].carta.nome == "Mox Pearl"


def test_tiene_mana_per_la_contromagia():
    p = p_base()
    ai = p.giocatore("AI")
    ai[Zona.CAMPO].extend([carta("Island"), carta("Island"), carta("Plains")])
    ai[Zona.MANO][:] = [carta("Counterspell")]
    orso = cr("Orso", 2, 2)
    orso.costo = "{1}"
    assert lascia_contromagia(p, "AI", orso)  # con 3 terre: {1} + {U}{U} si può
    gigante = Carta("Gigante", "Creature — Giant", "{3}", 3, 3)
    assert not lascia_contromagia(p, "AI", gigante)  # {3} + {U}{U} = 5 > 3
    p.giocatore("B")[Zona.MANO][:] = []
    assert lascia_contromagia(p, "AI", gigante)  # l'avversario non ha carte: niente da neutralizzare


def test_moat_e_abyss_solo_se_convengono():
    p = p_base()
    p.giocatore("AI")[Zona.CAMPO].append(cr("Volante", 3, 3, "Flying"))
    p.giocatore("B")[Zona.CAMPO].append(cr("Terrestre", 4, 4))
    assert permanente_utile(p, "AI", carta("Moat"))
    p.giocatore("AI")[Zona.CAMPO].append(cr("Grosso", 6, 6))
    assert not permanente_utile(p, "AI", carta("Moat"))
    assert not permanente_utile(p, "AI", carta("The Abyss"))  # 2 sue creature contro 1


def test_attacco_finale_letale():
    p = p_base()
    p.giocatore("B").vita = 3
    attaccanti = [cr("A", 2, 2), cr("B", 2, 2), cr("C", 2, 2)]
    p.giocatore("AI")[Zona.CAMPO].extend(attaccanti)
    p.giocatore("B")[Zona.CAMPO].append(cr("Muro", 0, 10))
    azioni.passa_priorita(p, "AI")
    azioni.passa_priorita(p, "B")
    assert p.fase == Fase.COMBATTIMENTO
    assert len(scegli_attaccanti(p, "AI")) == 3  # bloccandone uno ne passano 4 danni: letale


def test_factory_animata_per_attaccare_e_per_bloccare():
    p = p_base()
    factory = carta("Mishra's Factory")
    p.giocatore("AI")[Zona.CAMPO].extend([factory, carta("Island")])
    assert factory_da_animare(p, "AI", per_attaccare=True)[0] is factory
    p.giocatore("B")[Zona.CAMPO].append(cr("Orso", 3, 3))
    assert factory_da_animare(p, "AI", per_attaccare=True) is None  # l'orso 3/3 la ucciderebbe
    # turno di B: attacca con un 1/1, la Factory si anima per bloccarlo
    p.attivo = p.priorita = 1
    elfo = cr("Elfo", 1, 1)
    p.giocatore("B")[Zona.CAMPO].append(elfo)
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    combattimento.dichiara_attaccanti(p, "B", [elfo])
    azioni.passa_priorita(p, "B")
    agisci(p, "AI")
    assert p.pila[-1].descrizione == "abilità di Mishra's Factory"
