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


def _terra(nome, tipo):
    return Carta(nome, tipo, "", None, None, "")


def test_spaccaterre_da_esperto():
    """Con creature in campo contro bianco-blu: via l'ultima isola o l'ultima pianura, e prima di tutto il Maze."""
    from app.ai.politiche import terra_da_distruggere
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    b[Zona.CAMPO][:] = [_terra("Plains", "Basic Land — Plains"), _terra("Plains", "Basic Land — Plains"),
                        _terra("Island", "Basic Land — Island"), _terra("Swamp", "Basic Land — Swamp")]
    b[Zona.CIMITERO][:] = [carta("Counterspell"), carta("Swords to Plowshares")]
    ai[Zona.CAMPO].append(cr("Orso", 2, 2))
    roccia = carta("Stone Rain") if "Stone Rain" in BASE else Carta("Stone Rain", "Sorcery", "{2}{R}")
    assert terra_da_distruggere(p, "AI", roccia).nome == "Island"  # l'unica fonte di blu: niente più Counterspell
    labirinto = _terra("Maze of Ith", "Land")
    b[Zona.CAMPO].append(labirinto)
    assert terra_da_distruggere(p, "AI", roccia) is labirinto  # con creature mie, il Maze prima di tutto
    ai[Zona.CAMPO].clear()
    assert terra_da_distruggere(p, "AI", roccia).nome == "Island"  # senza creature il Maze conta poco


def test_strip_mine_solo_su_un_bersaglio_che_vale():
    from app.ai.politiche import terra_da_distruggere
    p = p_base()
    b = p.giocatore("B")
    b[Zona.CAMPO][:] = [_terra("Forest", "Basic Land — Forest") for _ in range(4)]
    mina = carta("Strip Mine")
    assert terra_da_distruggere(p, "AI", mina, minimo=6) is None  # una foresta tra quattro non vale la Strip Mine
    b[Zona.CAMPO][:] = [_terra("Forest", "Basic Land — Forest"), carta("Library of Alexandria")]
    assert terra_da_distruggere(p, "AI", mina, minimo=6).nome == "Library of Alexandria"


FACTORY_VERA = ("{T}: Add {C}.\n{1}: Mishra's Factory becomes a 2/2 Assembly-Worker artifact creature until end of turn. "
                "It's still a land.\n{T}: Target Assembly-Worker creature gets +1/+1 until end of turn.")


def test_non_attacca_contro_una_factory_pronta_a_bloccare():
    """Un 2/2 contro una Factory stappata (2/2 che si pompa a 3/3): un giocatore esperto non attacca,
    a meno di avere Swords o Disenchant per toglierla di mezzo."""
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    orso = cr("Orso", 2, 2)
    orso.entrata_nel_turno = 1
    ai[Zona.CAMPO].append(orso)
    fabbrica = Carta("Mishra's Factory", "Land", "", None, None, FACTORY_VERA)
    b[Zona.CAMPO][:] = [fabbrica, carta("Forest")]
    assert orso not in scegli_attaccanti(p, "AI")
    fabbrica.tappata = True  # tappata: non può animarsi
    assert orso in scegli_attaccanti(p, "AI")
    fabbrica.tappata = False
    ai[Zona.CAMPO].append(carta("Plains"))
    ai[Zona.MANO][:] = [carta("Swords to Plowshares")]
    assert orso in scegli_attaccanti(p, "AI")  # se blocca, la Factory finisce rimossa dal gioco


def test_rompe_la_library_se_hai_la_mano_piena():
    from app.ai.politiche import terra_da_distruggere
    p = p_base()
    b = p.giocatore("B")
    libreria = carta("Library of Alexandria")
    b[Zona.CAMPO][:] = [_terra("Island", "Basic Land — Island"), libreria]
    b[Zona.CIMITERO][:] = [carta("Counterspell")]
    b[Zona.MANO][:] = [carta("Island") for _ in range(6)]
    assert terra_da_distruggere(p, "AI", carta("Strip Mine"), minimo=6) is libreria  # più dell'ultima isola
