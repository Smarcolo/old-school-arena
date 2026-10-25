import pytest

from app.ai.avversaria import agisci, scegli_attaccanti, scegli_bloccanti
from app.api.main import _abilita
from app.cards import mazzi
from app.engine import azioni, combattimento
from app.engine.stato import Carta, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def cavaliere_bianco():
    return Carta("White Knight", "Creature — Human Knight", "{W}{W}", 2, 2, "First strike, protection from black")


def pro_rosso():
    return Carta("Paladino", "Creature — Test", "{W}", 2, 2, "Protection from red")


def cr(nome, f, c, costo="{B}"):
    return Carta(nome, "Creature — Test", costo, f, c)


def terra(tipo="Mountain"):
    return Carta(tipo, f"Basic Land — {tipo}")


def bolt():
    return Carta("Lightning Bolt", "Instant", "{R}")


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra("Plains") for _ in range(20)]}, seed=13)
    partita.turno = 3
    return partita


def passano(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_colori_e_protezioni():
    k = cavaliere_bianco()
    assert k.colori == {"W"} and k.protezioni == {"B"} and k.ha("first strike")
    assert k.protetta_da(cr("Zombi", 2, 2, "{1}{B}")) and not k.protetta_da(cr("Orco", 2, 2, "{R}"))
    assert terra().colori == set()
    assert _abilita(k) == ["attacca per primo", "protezione dal nero"]


def test_non_si_puo_bersagliare(p):
    paladino = pro_rosso()
    p.giocatore("B")[Zona.CAMPO].append(paladino)
    p.giocatore("A")[Zona.CAMPO].append(terra())
    p.giocatore("A")[Zona.MANO].append(bolt())
    with pytest.raises(AzioneIllegale, match="protezione dal rosso"):
        azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [f"carta:{paladino.id}"])


def test_protezione_acquisita_dopo_il_lancio_neutralizza(p):
    orso = cr("Orso", 2, 2, "{W}")
    p.giocatore("B")[Zona.CAMPO].append(orso)
    p.giocatore("A")[Zona.CAMPO].append(terra())
    p.giocatore("A")[Zona.MANO].append(bolt())
    azioni.lancia(p, "A", azioni.trova_in_zona(p, "A", Zona.MANO, "lightning bolt"), [f"carta:{orso.id}"])
    orso.testo = "Protection from red"  # come se l'avesse ottenuta in risposta
    passano(p)
    assert orso in p.giocatore("B")[Zona.CAMPO]
    assert any(e.tipo == "neutralizzata" for e in p.registro.eventi)


def test_cavaliere_blocca_lo_zombi_e_non_subisce_danni(p):
    zombi = cr("Zombi", 3, 3, "{2}{B}")
    p.giocatore("A")[Zona.CAMPO].append(zombi)
    k = cavaliere_bianco()
    p.giocatore("B")[Zona.CAMPO].append(k)
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [zombi])
    passano(p)
    combattimento.dichiara_bloccanti(p, "B", [(k, zombi)])
    passano(p)
    assert k in p.giocatore("B")[Zona.CAMPO] and k.danni == 0
    assert zombi.danni == 2


def test_lo_zombi_non_puo_bloccare_il_cavaliere(p):
    k = cavaliere_bianco()
    p.giocatore("A")[Zona.CAMPO].append(k)
    zombi = cr("Zombi", 3, 3, "{2}{B}")
    p.giocatore("B")[Zona.CAMPO].append(zombi)
    passano(p)
    combattimento.dichiara_attaccanti(p, "A", [k])
    passano(p)
    assert p.combattimento.bloccanti_dichiarati  # nessun blocco legale: saltato
    assert "protezione" in combattimento.puo_bloccare_contro(p, "B", zombi, k)


def test_danno_da_abilita_prevenuto(p):
    paladino = pro_rosso()
    p.giocatore("B")[Zona.CAMPO].append(paladino)
    azioni.infliggi_danno(p, cr("Goblin", 1, 1, "{R}"), f"carta:{paladino.id}", 5)
    azioni.azioni_di_stato(p)
    assert paladino in p.giocatore("B")[Zona.CAMPO] and paladino.danni == 0


def test_ai_non_bolta_una_creatura_protetta(p):
    p.giocatore("B")[Zona.CAMPO].append(pro_rosso())
    p.giocatore("A")[Zona.CAMPO].append(terra())
    p.giocatore("A")[Zona.MANO].append(bolt())
    for c in list(p.giocatore("A")[Zona.MANO]):
        if c.is_terra:
            p.giocatore("A")[Zona.MANO].remove(c)
    p.giocatore("B").vita = 10  # in faccia solo verso la fine della partita
    agisci(p, "A")
    assert p.pila and p.pila[-1].bersagli == ["giocatore:B"]  # niente creature legali: va in faccia


def test_ai_attacca_con_il_cavaliere_contro_creature_nere(p):
    k = cavaliere_bianco()
    p.giocatore("A")[Zona.CAMPO].append(k)
    p.giocatore("B")[Zona.CAMPO].append(cr("Juzam", 5, 5, "{2}{B}{B}"))
    passano(p)
    assert scegli_attaccanti(p, "A") == [k]


def test_ai_blocca_con_il_cavaliere(p):
    p.attivo = p.priorita = 1
    p.turno = 4
    zombi = cr("Zombi", 5, 5, "{3}{B}{B}")
    p.giocatore("B")[Zona.CAMPO].append(zombi)
    k = cavaliere_bianco()
    p.giocatore("A")[Zona.CAMPO].append(k)
    passano(p)
    combattimento.dichiara_attaccanti(p, "B", [zombi])
    passano(p)
    assert [(b.nome, a.nome) for b, a in scegli_bloccanti(p, "A")] == [("White Knight", "Zombi")]


def test_analisi_mazzo_capisce_la_protezione(conn):
    a = mazzi.analizza(conn, {"White Knight": 4, "Black Knight": 4, "Plains": 26, "Swamp": 26}, {})
    assert not any("Knight" in x for x in a["avvisi"])


def test_protezione_dagli_artefatti(p):
    tetra = Carta("Guardiano", "Creature — Test", "{2}{G}", 2, 2, "Protection from artifacts")
    p.giocatore("B")[Zona.CAMPO].append(tetra)
    golem = Carta("Golem", "Artifact Creature — Golem", "{4}", 3, 3)
    assert tetra.protetta_da(golem) and not tetra.protetta_da(cr("Orco", 2, 2, "{R}"))
    azioni.infliggi_danno(p, golem, f"carta:{tetra.id}", 3)
    assert tetra.danni == 0
    assert _abilita(tetra) == ["protezione dagli artefatti"]
    p.giocatore("A")[Zona.CAMPO].append(golem)
    assert "protezione" in combattimento.puo_bloccare_contro(p, "A", golem, tetra)
