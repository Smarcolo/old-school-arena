import pytest

from app.ai import politiche
from app.ai.avversaria import agisci
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine import azioni
from app.engine.abilita import analizza_abilita
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

DATI = {
    "Swords to Plowshares": ("Instant", "{W}"), "Terror": ("Instant", "{1}{B}"), "Counterspell": ("Instant", "{U}{U}"),
    "Ancestral Recall": ("Instant", "{U}"), "Disenchant": ("Instant", "{1}{W}"), "Mana Drain": ("Instant", "{U}{U}"),
    "Fireball": ("Sorcery", "{X}{R}"), "Psionic Blast": ("Instant", "{2}{U}"), "Time Walk": ("Sorcery", "{1}{U}"),
    "Timetwister": ("Sorcery", "{2}{U}"), "Wheel of Fortune": ("Sorcery", "{2}{R}"), "Braingeyser": ("Sorcery", "{X}{U}{U}"),
    "Mind Twist": ("Sorcery", "{X}{B}"), "Demonic Tutor": ("Sorcery", "{1}{B}"), "Regrowth": ("Sorcery", "{1}{G}"),
    "Wrath of God": ("Sorcery", "{2}{W}{W}"), "Balance": ("Sorcery", "{1}{W}"), "Dark Ritual": ("Instant", "{B}"),
    "Red Elemental Blast": ("Instant", "{R}"), "Shatter": ("Instant", "{1}{R}"), "Lightning Bolt": ("Instant", "{R}"),
    "Unsummon": ("Instant", "{U}"),
}
MULTI = "Land — Plains Island Swamp Mountain Forest"  # terra di prova che produce ogni colore


def magia(nome):
    tipo, costo = DATI[nome]
    return Carta(nome, tipo, costo)


def terra():
    return Carta("Terra", MULTI)


def cr(nome, f, c, costo="{G}", testo=""):
    return Carta(nome, "Creature — Test", costo, f, c, testo)


@pytest.fixture
def p():
    partita = nuova_partita({"A": [Carta("Forest", "Basic Land — Forest") for _ in range(30)],
                             "B": [Carta("Forest", "Basic Land — Forest") for _ in range(30)]}, seed=21)
    partita.turno = 3
    partita.giocatore("A")[Zona.CAMPO].extend(terra() for _ in range(8))
    partita.giocatore("B")[Zona.CAMPO].extend(terra() for _ in range(8))
    return partita


def in_mano(p, chi, nome):
    c = magia(nome)
    p.giocatore(chi)[Zona.MANO].append(c)
    return c


def risolvi(p):
    while p.pila:
        azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_swords_to_plowshares(p):
    orso = cr("Orso", 3, 3)
    p.giocatore("B")[Zona.CAMPO].append(orso)
    azioni.lancia(p, "A", in_mano(p, "A", "Swords to Plowshares"), [f"carta:{orso.id}"])
    risolvi(p)
    assert orso in p.giocatore("B")[Zona.RIMOSSE] and p.giocatore("B").vita == 23


def test_swords_non_si_rigenera(p):
    s = cr("Scheletro", 1, 1, "{B}", "{B}: Regenerate Scheletro.")
    s.scudi_rigenerazione = 1
    p.giocatore("B")[Zona.CAMPO].append(s)
    azioni.lancia(p, "A", in_mano(p, "A", "Swords to Plowshares"), [f"carta:{s.id}"])
    risolvi(p)
    assert s in p.giocatore("B")[Zona.RIMOSSE]


def test_terror(p):
    verde, nera, golem = cr("Verde", 2, 2), cr("Nera", 2, 2, "{B}"), Carta("Golem", "Artifact Creature — Golem", "{4}", 3, 3)
    verde.scudi_rigenerazione = 1
    p.giocatore("B")[Zona.CAMPO].extend([verde, nera, golem])
    t = in_mano(p, "A", "Terror")
    with pytest.raises(AzioneIllegale, match="non nera"):
        azioni.lancia(p, "A", t, [f"carta:{nera.id}"])
    with pytest.raises(AzioneIllegale, match="non nera"):
        azioni.lancia(p, "A", t, [f"carta:{golem.id}"])
    azioni.lancia(p, "A", t, [f"carta:{verde.id}"])
    risolvi(p)
    assert verde in p.giocatore("B")[Zona.CIMITERO]  # niente rigenerazione


def test_counterspell(p):
    bolt = in_mano(p, "A", "Lightning Bolt")
    azioni.lancia(p, "A", bolt, ["giocatore:B"])
    azioni.passa_priorita(p, "A")
    cs = in_mano(p, "B", "Counterspell")
    azioni.lancia(p, "B", cs, [f"pila:{p.pila[-1].id}"])
    risolvi(p)
    assert p.giocatore("B").vita == 20 and bolt in p.giocatore("A")[Zona.CIMITERO]


def test_counterspell_solo_su_magie(p):
    cs = in_mano(p, "A", "Counterspell")
    with pytest.raises(AzioneIllegale, match="magia in pila"):
        azioni.lancia(p, "A", cs, ["giocatore:B"])


def test_mana_drain_da_mana_alla_prossima_principale(p):
    gigante = Carta("Gigante", "Creature — Giant", "{3}{R}", 3, 3)
    p.giocatore("A")[Zona.MANO].append(gigante)
    azioni.lancia(p, "A", gigante)
    azioni.passa_priorita(p, "A")
    azioni.lancia(p, "B", in_mano(p, "B", "Mana Drain"), [f"pila:{p.pila[-1].id}"])
    risolvi(p)
    assert gigante in p.giocatore("A")[Zona.CIMITERO] and p.mana_ritardato == [("B", 4)]
    while not (p.giocatore_attivo.nome == "B" and p.fase == Fase.PRINCIPALE_1):
        azioni.passa_fase(p)
    assert p.giocatore("B").riserva["C"] == 4


def test_ancestral_recall(p):
    prima = len(p.giocatore("A")[Zona.MANO])
    azioni.lancia(p, "A", in_mano(p, "A", "Ancestral Recall"), ["giocatore:A"])
    risolvi(p)
    assert len(p.giocatore("A")[Zona.MANO]) == prima + 3


def test_disenchant(p):
    vise = Carta("Black Vise", "Artifact", "{1}")
    crusade = Carta("Crusade", "Enchantment", "{W}{W}", testo="White creatures get +1/+1.")
    orso = cr("Orso", 2, 2)
    p.giocatore("B")[Zona.CAMPO].extend([vise, crusade, orso])
    d = in_mano(p, "A", "Disenchant")
    with pytest.raises(AzioneIllegale, match="artefatto o un incantesimo"):
        azioni.lancia(p, "A", d, [f"carta:{orso.id}"])
    azioni.lancia(p, "A", d, [f"carta:{vise.id}"])
    risolvi(p)
    assert vise in p.giocatore("B")[Zona.CIMITERO]


def test_fireball_con_x(p):
    azioni.lancia(p, "A", in_mano(p, "A", "Fireball"), ["giocatore:B"], x=6)
    assert sum(c.tappata for c in p.giocatore("A")[Zona.CAMPO]) == 7
    risolvi(p)
    assert p.giocatore("B").vita == 14


def test_fireball_x_troppo_alto(p):
    with pytest.raises(AzioneIllegale, match="X=9"):
        azioni.lancia(p, "A", in_mano(p, "A", "Fireball"), ["giocatore:B"], x=9)


def test_psionic_blast(p):
    azioni.lancia(p, "A", in_mano(p, "A", "Psionic Blast"), ["giocatore:B"])
    risolvi(p)
    assert p.giocatore("B").vita == 16 and p.giocatore("A").vita == 18


def test_time_walk(p):
    azioni.lancia(p, "A", in_mano(p, "A", "Time Walk"), [])
    risolvi(p)
    while p.turno == 3:
        azioni.passa_fase(p)
    assert p.turno == 4 and p.giocatore_attivo.nome == "A"
    while p.turno == 4:
        azioni.passa_fase(p)
    assert p.giocatore_attivo.nome == "B"


def test_timetwister_e_wheel(p):
    a, b = p.giocatore("A"), p.giocatore("B")
    a[Zona.CIMITERO].append(cr("Morto", 1, 1))
    azioni.lancia(p, "A", in_mano(p, "A", "Timetwister"), [])
    risolvi(p)
    assert len(a[Zona.MANO]) == 7 and len(b[Zona.MANO]) == 7
    assert a[Zona.CIMITERO][-1].nome == "Timetwister" and len(a[Zona.CIMITERO]) == 1
    b[Zona.MANO][:] = b[Zona.MANO][:2]
    azioni.lancia(p, "A", in_mano(p, "A", "Wheel of Fortune"), [])
    risolvi(p)
    assert len(b[Zona.MANO]) == 7 and len(a[Zona.MANO]) == 7


def test_braingeyser_e_mind_twist(p):
    azioni.lancia(p, "A", in_mano(p, "A", "Braingeyser"), ["giocatore:A"], x=2)
    risolvi(p)
    prima_b = len(p.giocatore("B")[Zona.MANO])
    azioni.lancia(p, "A", in_mano(p, "A", "Mind Twist"), ["giocatore:B"], x=3)
    risolvi(p)
    assert len(p.giocatore("B")[Zona.MANO]) == prima_b - 3


def test_demonic_tutor_automatico_e_manuale(p):
    a = p.giocatore("A")
    lotus = Carta("Black Lotus", "Artifact", "{0}")
    a[Zona.GRIMORIO].insert(0, lotus)
    azioni.lancia(p, "A", in_mano(p, "A", "Demonic Tutor"), [])
    risolvi(p)
    assert lotus in a[Zona.MANO]  # l'automatico prende la carta migliore
    p.scelte_manuali = {"A"}
    a[Zona.GRIMORIO].insert(0, Carta("Mox Jet", "Artifact", "{0}", testo="{T}: Add {B}."))
    azioni.lancia(p, "A", in_mano(p, "A", "Demonic Tutor"), [])
    risolvi(p)
    assert p.scelta and p.scelta.tipo == "cerca" and "Mox Jet" in p.scelta.dati["carte"].values()
    assert esegui(p, "A", analizza("scelgo mox jet")) == "Carta presa e grimorio rimescolato."
    assert any(c.nome == "Mox Jet" for c in a[Zona.MANO]) and p.scelta is None


def test_regrowth(p):
    a = p.giocatore("A")
    ancestral = magia("Ancestral Recall")
    a[Zona.CIMITERO].append(ancestral)
    in_mano(p, "A", "Regrowth")
    assert "in pila" in esegui(p, "A", analizza("gioca regrowth su ancestral recall"))
    risolvi(p)
    assert ancestral in a[Zona.MANO]


def test_wrath_of_god_e_balance(p):
    p.giocatore("A")[Zona.CAMPO].append(cr("Mia", 2, 2))
    p.giocatore("B")[Zona.CAMPO].extend([cr("Sua1", 2, 2), cr("Sua2", 3, 3)])
    azioni.lancia(p, "A", in_mano(p, "A", "Balance"), [])
    risolvi(p)
    assert [c.nome for c in p.giocatore("B")[Zona.CAMPO] if c.is_creatura] == ["Sua2"]  # tiene la migliore
    azioni.lancia(p, "A", in_mano(p, "A", "Wrath of God"), [])
    risolvi(p)
    assert not any(c.is_creatura for g in p.giocatori for c in g[Zona.CAMPO])


def test_dark_ritual_e_reb(p):
    azioni.lancia(p, "A", in_mano(p, "A", "Dark Ritual"), [])
    risolvi(p)
    assert p.giocatore("A").riserva["B"] == 3
    serendib = Carta("Serendib Efreet", "Creature — Efreet", "{2}{U}", 3, 4)
    p.giocatore("B")[Zona.CAMPO].append(serendib)
    azioni.lancia(p, "A", in_mano(p, "A", "Red Elemental Blast"), [f"carta:{serendib.id}"])
    risolvi(p)
    assert serendib in p.giocatore("B")[Zona.CIMITERO]


def test_strip_mine_library_icy_atog(p):
    a, b = p.giocatore("A"), p.giocatore("B")
    strip = Carta("Strip Mine", "Land", testo="{T}: Add {C}.\n{T}, Sacrifice Strip Mine: Destroy target land.")
    duale = Carta("Volcanic Island", "Land — Island Mountain")
    a[Zona.CAMPO].append(strip)
    b[Zona.CAMPO].append(duale)
    ab = analizza_abilita(strip)
    assert [x.tipo for x in ab] == ["distruggi"]
    azioni.attiva(p, "A", strip, ab[0], [f"carta:{duale.id}"])
    risolvi(p)
    assert strip in a[Zona.CIMITERO] and duale in b[Zona.CIMITERO]

    library = Carta("Library of Alexandria", "Land", testo="{T}: Add {C}.\n{T}: Draw a card. Activate only if you have exactly seven cards in your hand.")
    a[Zona.CAMPO].append(library)
    a[Zona.MANO][:] = a[Zona.MANO][:6]
    with pytest.raises(AzioneIllegale, match="sette carte"):
        azioni.attiva(p, "A", library, analizza_abilita(library)[0])
    a[Zona.MANO].append(cr("X", 1, 1))
    azioni.attiva(p, "A", library, analizza_abilita(library)[0])
    risolvi(p)
    assert len(a[Zona.MANO]) == 8

    icy = Carta("Icy Manipulator", "Artifact", "{4}", testo="{1}, {T}: Tap target artifact, creature, or land.")
    orso = cr("Orso", 2, 2)
    a[Zona.CAMPO].append(icy)
    b[Zona.CAMPO].append(orso)
    azioni.attiva(p, "A", icy, analizza_abilita(icy)[0], [f"carta:{orso.id}"])
    risolvi(p)
    assert orso.tappata

    atog = Carta("Atog", "Creature — Atog", "{1}{R}", 1, 2, "Sacrifice an artifact: Atog gets +2/+2 until end of turn.")
    mox = Carta("Mox Ruby", "Artifact", "{0}", testo="{T}: Add {R}.")
    a[Zona.CAMPO].extend([atog, mox])
    assert "in pila" in esegui(p, "A", analizza("attiva atog su mox ruby"))
    risolvi(p)
    assert atog.forza_attuale == 3 and mox in a[Zona.CIMITERO] and icy in a[Zona.CAMPO]


def test_ai_contromagia_e_rimozione(p):
    gigante = Carta("Gigante", "Creature — Giant", "{3}{R}", 3, 3)
    p.giocatore("A")[Zona.MANO].append(gigante)
    azioni.lancia(p, "A", gigante)
    azioni.passa_priorita(p, "A")
    p.giocatore("B")[Zona.MANO].append(magia("Counterspell"))
    agisci(p, "B")
    assert p.pila[-1].carta.nome == "Counterspell"
    risolvi(p)
    # turno di B: rimozione sulla creatura migliore di A
    p.attivo = p.priorita = 1
    orso = cr("Orso", 3, 3)
    p.giocatore("A")[Zona.CAMPO].append(orso)
    p.giocatore("B")[Zona.MANO].append(magia("Swords to Plowshares"))
    assert politiche.scegli_magia(p, "B")[1] == [f"carta:{orso.id}"]


def test_ai_fireball_letale(p):
    p.giocatore("A").vita = 5
    p.attivo = p.priorita = 1
    p.giocatore("B")[Zona.MANO][:] = [magia("Fireball")]
    carta, bersagli, x = politiche.scegli_magia(p, "B")
    assert bersagli == ["giocatore:A"] and x >= 5


def test_ai_ancestral_a_fine_turno_avversario(p):
    p.fase = Fase.FINALE
    p.giocatore("B")[Zona.MANO][:] = [magia("Ancestral Recall")]
    p.priorita = 1
    assert politiche.scegli_magia(p, "B")[1] == ["giocatore:B"]
