import pytest

from app.ai.avversaria import agisci
from app.api.main import vista
from app.cards import mazzi
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni, combattimento
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, nuova_partita
from app.engine.statici import analizza_statici
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

HOLY = ("Holy Strength", "Enchantment — Aura", "{W}", None, None, "Enchant creature\nEnchanted creature gets +1/+2.")
FLIGHT = ("Flight", "Enchantment — Aura", "{U}", None, None, "Enchant creature\nEnchanted creature has flying.")
FIRE = ("Firebreathing", "Enchantment — Aura", "{R}", None, None, "Enchant creature\n{R}: Enchanted creature gets +1/+0 until end of turn.")
CRUSADE = ("Crusade", "Enchantment", "{W}{W}", None, None, "White creatures get +1/+1.")


def terra(tipo="Plains"):
    return Carta(tipo, f"Basic Land — {tipo}")


def cr(nome, f, c, costo="{W}", testo=""):
    return Carta(nome, "Creature — Test", costo, f, c, testo)


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra("Mountain") for _ in range(20)]}, seed=15)
    partita.turno = 3
    return partita


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def incanta(p, chi, dati, creatura, terre=("Plains",)):
    aura = Carta(*dati)
    p.giocatore(chi)[Zona.CAMPO].extend(terra(t) for t in terre)
    p.giocatore(chi)[Zona.MANO].append(aura)
    azioni.lancia(p, chi, aura, [f"carta:{creatura.id}"])
    passano(p)
    return aura


def test_riconoscimento():
    assert [(e.tipo, e.forza, e.costituzione) for e in analizza_statici(Carta(*HOLY))] == [("aura", 1, 2)]
    assert analizza_statici(Carta(*FLIGHT))[0].parole == {"flying"}
    assert analizza_statici(Carta(*CRUSADE))[0].colore == "W"
    assert analizza_abilita(Carta(*FIRE))[0].su_incantata


def test_holy_strength(p):
    orso = cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].append(orso)
    aura = incanta(p, "A", HOLY, orso)
    assert aura.attaccata_a == orso.id and (orso.forza_attuale, orso.costituzione_attuale) == (3, 4)
    assert [c["incanta"] for c in vista(p)["giocatori"][0]["campo"] if c["nome"] == "Holy Strength"] == ["Orso"]


def test_aura_ha_bisogno_di_una_creatura(p):
    p.giocatore("A")[Zona.CAMPO].append(terra())
    p.giocatore("A")[Zona.MANO].append(Carta(*HOLY))
    with pytest.raises(AzioneIllegale, match="bersaglio"):
        azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "holy strength"), ["giocatore:A"])


def test_flight_da_volare(p):
    orso = cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].append(orso)
    incanta(p, "A", FLIGHT, orso, ("Island",))
    assert orso.ha("flying")
    muro = cr("Muro", 0, 5)
    p.giocatore("B")[Zona.CAMPO].append(muro)
    assert "vola" in combattimento.puo_bloccare_contro(p, "B", muro, orso)


def test_aura_va_al_cimitero_se_la_creatura_muore(p):
    orso = cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].append(orso)
    aura = incanta(p, "A", HOLY, orso)
    azioni.infliggi_danno(p, cr("Fonte", 1, 1, "{R}"), f"carta:{orso.id}", 4)
    azioni.azioni_di_stato(p)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "orso")
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "holy strength") and aura.attaccata_a is None


def test_bersaglio_sparito_aura_al_cimitero(p):
    orso = cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].extend([orso, terra()])
    p.giocatore("A")[Zona.MANO].append(Carta(*HOLY))
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "holy strength"), [f"carta:{orso.id}"])
    azioni.distruggi(p, orso)
    passano(p)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "holy strength")
    assert not any(c.nome == "Holy Strength" for c in p.giocatore("A")[Zona.CAMPO])


def test_aura_sull_avversario_e_protezione(p):
    k = cr("Cavaliere", 2, 2, "{B}{B}", "Protection from white")
    p.giocatore("B")[Zona.CAMPO].append(k)
    p.giocatore("A")[Zona.CAMPO].append(terra())
    p.giocatore("A")[Zona.MANO].append(Carta(*HOLY))
    with pytest.raises(AzioneIllegale, match="protezione"):
        azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "holy strength"), [f"carta:{k.id}"])


def test_firebreathing_pompa_la_creatura_incantata(p):
    orso = cr("Orso", 2, 2)
    p.giocatore("A")[Zona.CAMPO].append(orso)
    aura = incanta(p, "A", FIRE, orso, ("Mountain", "Mountain"))
    assert "in pila" in esegui(p, "A", analizza("attiva firebreathing"))
    passano(p)
    assert orso.forza_attuale == 3 and aura.forza is None


def test_crusade_pompa_solo_le_bianche_di_tutti(p):
    bianca, rossa = cr("Bianca", 1, 1, "{W}"), cr("Rossa", 1, 1, "{R}")
    nemica_bianca = cr("Nemica", 1, 1, "{1}{W}")
    p.giocatore("A")[Zona.CAMPO].extend([bianca, rossa, Carta(*CRUSADE)])
    p.giocatore("B")[Zona.CAMPO].append(nemica_bianca)
    azioni.azioni_di_stato(p)
    assert bianca.forza_attuale == 2 and rossa.forza_attuale == 1 and nemica_bianca.costituzione_attuale == 2


def test_crusade_che_se_ne_va_puo_uccidere(p):
    bianca = cr("Bianca", 1, 1, "{W}")
    crusade = Carta(*CRUSADE)
    p.giocatore("A")[Zona.CAMPO].extend([bianca, crusade])
    azioni.azioni_di_stato(p)
    bianca.danni = 1
    azioni.azioni_di_stato(p)
    assert bianca in p.giocatore("A")[Zona.CAMPO]
    azioni.distruggi(p, crusade)
    azioni.azioni_di_stato(p)
    assert azioni.trova_in_zona(p, "A", Zona.CIMITERO, "bianca")


def test_ai_incanta_la_sua_creatura_migliore(p):
    piccola, grande = cr("Piccola", 1, 1), cr("Grande", 3, 3)
    a = p.giocatore("A")
    a[Zona.CAMPO].extend([piccola, grande, terra()])
    a[Zona.MANO][:] = [Carta(*HOLY)]
    agisci(p, "A")
    assert p.pila[-1].carta.nome == "Holy Strength" and p.pila[-1].bersagli == [f"carta:{grande.id}"]


def test_analisi_mazzo_capisce_le_aure(conn):
    a = mazzi.analizza(conn, {"Holy Strength": 4, "Firebreathing": 2, "Crusade": 2, "Flight": 2, "Plains": 50}, {})
    assert not any(n in x for x in a["avvisi"] for n in ("Holy", "Firebreathing", "Crusade", "Flight"))
