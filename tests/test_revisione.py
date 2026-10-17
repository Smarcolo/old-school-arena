"""Casi trovati nella revisione del codice (ottobre 2026)."""
import pytest

from app.engine import azioni, mana
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, Scelta, nuova_partita
from app.engine.validazione import AzioneIllegale, fonti_di_mana
from app.engine.zone import Zona

MULTI = "Land — Plains Island Swamp Mountain Forest"
FACTORY = ("{T}: Add {C}.\n{1}: Mishra's Factory becomes a 2/2 Assembly-Worker artifact creature until end of turn. "
           "It's still a land.\n{T}: Target Assembly-Worker creature gets +1/+2 until end of turn.")


@pytest.fixture
def p():
    partita = nuova_partita({"A": [Carta("Forest", "Basic Land — Forest") for _ in range(30)],
                             "B": [Carta("Forest", "Basic Land — Forest") for _ in range(30)]}, seed=21)
    partita.turno = 3
    return partita


def campo(p, chi, *carte):
    for c in carte:
        c.proprietario, c.entrata_nel_turno = chi, 1
        p.giocatore(chi)[Zona.CAMPO].append(c)
    return carte[0] if len(carte) == 1 else carte


def risolvi(p):
    while p.pila and not p.scelta:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_due_terre_doppie_pagano_due_colori(p):
    campo(p, "A", Carta("Tundra", "Land — Plains Island"), Carta("Plateau", "Land — Mountain Plains"))
    piano = mana.piano_pagamento(p.giocatore("A").riserva, fonti_di_mana(p, "A"), mana.analizza_costo("{W}{U}"))
    assert sorted((f.carta.nome, c) for f, c in piano) == [("Plateau", "W"), ("Tundra", "U")]
    campo(p, "A", Carta("Scrubland", "Land — Plains Swamp"))
    assert mana.piano_pagamento({}, fonti_di_mana(p, "A"), mana.analizza_costo("{W}{U}{B}")) is not None


def test_paga_durante_una_scelta_di_altro_tipo(p):
    p.scelta = Scelta("A", testo="scegli", tipo="cerca")
    with pytest.raises(AzioneIllegale, match="niente da pagare"):
        azioni.rispondi_scelta(p, "A", True)


def test_aura_cade_quando_la_factory_torna_terra(p):
    p.fase = Fase.PRINCIPALE_1
    campo(p, "A", *[Carta("Terra", MULTI) for _ in range(4)])
    fac = campo(p, "A", Carta("Mishra's Factory", "Land", "", None, None, FACTORY))
    azioni.attiva(p, "A", fac, next(a for a in analizza_abilita(fac) if a.tipo == "anima"))
    risolvi(p)
    holy = Carta("Holy Strength", "Enchantment — Aura", "{W}", None, None, "Enchant creature\nEnchanted creature gets +1/+2.")
    p.giocatore("A")[Zona.MANO].append(holy)
    azioni.lancia(p, "A", holy, [f"carta:{fac.id}"])
    risolvi(p)
    while p.turno == 3:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    assert holy in p.giocatore("A")[Zona.CIMITERO] and fac.statico_costituzione == 0


def test_factory_animata_e_un_artefatto(p):
    p.fase = Fase.PRINCIPALE_1
    campo(p, "A", Carta("Terra", MULTI))
    fac = campo(p, "A", Carta("Mishra's Factory", "Land", "", None, None, FACTORY))
    azioni.attiva(p, "A", fac, next(a for a in analizza_abilita(fac) if a.tipo == "anima"))
    risolvi(p)
    pro = Carta("Cavaliere", "Creature — Knight", "{W}", 2, 2, "Protection from artifacts")
    assert pro.protetta_da(fac)


def test_juggernaut_attacca_anche_se_si_passa(p):
    jug = campo(p, "A", Carta("Juggernaut", "Artifact Creature — Juggernaut", "{4}", 5, 3,
                              "Juggernaut attacks each combat if able.\nJuggernaut can't be blocked by Walls."))
    p.fase = Fase.PRINCIPALE_1
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.fase == Fase.COMBATTIMENTO
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.combattimento.attaccanti == [jug.id]


def test_earthquake_rispetta_ali_from_cairo(p):
    campo(p, "B", Carta("Ali from Cairo", "Creature — Human", "{2}{R}{R}", 0, 1,
                        "Damage that would reduce your life total to less than 1 reduces it to 1 instead."))
    p.giocatore("B").vita = 3
    p.fase = Fase.PRINCIPALE_1
    campo(p, "A", *[Carta("Terra", MULTI) for _ in range(6)])
    eq = Carta("Earthquake", "Sorcery", "{X}{R}")
    p.giocatore("A")[Zona.MANO].append(eq)
    azioni.lancia(p, "A", eq, [], x=5)
    risolvi(p)
    assert p.giocatore("B").vita == 1  # Ali (0/1) muore, ma il danno è simultaneo: resta a 1


def test_niente_mana_durante_il_mulligan():
    p = nuova_partita({"A": [Carta("Forest", "Basic Land — Forest") for _ in range(30)],
                       "B": [Carta("Forest", "Basic Land — Forest") for _ in range(30)]}, seed=2, mulligan=True)
    lotus = campo(p, "A", Carta("Black Lotus", "Artifact", "{0}", None, None,
                                "{T}, Sacrifice Black Lotus: Add three mana of any one color."))
    with pytest.raises(AzioneIllegale):
        azioni.tappa(p, "A", lotus)


def test_mazzo_piccolissimo_non_rompe_la_partita():
    p = nuova_partita({"A": [Carta("Forest", "Basic Land — Forest") for _ in range(3)],
                       "B": [Carta("Forest", "Basic Land — Forest") for _ in range(30)]}, seed=2)
    assert len(p.giocatore("A")[Zona.MANO]) == 3


def test_passaforeste_non_resta_dopo_essere_tornata_in_mano(p):
    orso = campo(p, "B", Carta("Orso", "Creature — Bear", "{1}{G}", 2, 2))
    orso.passaforeste_fino_al_turno = 10
    azioni.torna_in_mano(p, orso)
    assert orso.passaforeste_fino_al_turno == 0
