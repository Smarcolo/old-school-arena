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


def test_non_si_scopre_contro_wrath_e_lancia_prima_l_esca():
    from app.ai.avversaria import teme_contromagia, teme_spazzata
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO].extend([cr("Leone", 3, 1), cr("Cavaliere", 2, 2)])
    b[Zona.CAMPO][:] = [carta("Plains"), carta("Island"), carta("Island")]
    b[Zona.MANO][:] = [carta("Island"), carta("Island"), carta("Island")]
    assert teme_spazzata(p, "AI")  # 2 creature e 5 di forza contro un mazzo bianco con la mano piena
    b.vita = 5
    assert not teme_spazzata(p, "AI")  # sta per vincere: niente prudenza
    b[Zona.CIMITERO].append(carta("Counterspell"))
    assert teme_contromagia(p, "AI")  # {U}{U} stappati e Counterspell già visto
    for t in b[Zona.CAMPO]:
        t.tappata = True
    assert not teme_contromagia(p, "AI")


def test_strip_mine_sulla_propria_terra_poi_balance():
    """La giocata di Marco contro The Deck: Strip Mine sulla propria terra, poi Balance pagato con Mox e Sol Ring.
    L'avversario scende a zero terre e perde la mano; lei resta con il mana degli artefatti."""
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    mina, pianura = carta("Strip Mine"), carta("Plains")
    ai[Zona.CAMPO][:] = [mina, pianura, carta("Mox Pearl"), carta("Sol Ring")]
    ai[Zona.MANO][:] = [carta("Balance"), cr("Orso", 2, 2)]
    ai.terre_giocate_nel_turno = 1
    b[Zona.CAMPO][:] = [carta("Plains"), carta("Plains"), carta("Island"), carta("Island"), carta("Island"), carta("Plains")]
    b[Zona.MANO][:] = [carta("Island") for _ in range(6)]
    agisci(p, "AI")
    assert pianura in ai[Zona.CIMITERO] or (p.pila and p.pila[-1].bersagli == [f"carta:{pianura.id}"])
    for _ in range(40):  # si gioca finché Balance non è risolto
        if any(c.nome == "Balance" for c in ai[Zona.CIMITERO]):
            break
        if p.pila or p.giocatore_con_priorita.nome != "AI":
            azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
        else:
            agisci(p, "AI")
    assert any(c.nome == "Balance" for c in ai[Zona.CIMITERO])
    assert not any(c.is_terra for c in b[Zona.CAMPO])  # The Deck senza terre
    assert len(b[Zona.MANO]) <= 1


def test_niente_strip_sulla_propria_terra_senza_artefatti():
    from app.ai.politiche import strip_per_balance
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Strip Mine"), carta("Plains"), carta("Plains"), carta("Island")]
    ai[Zona.MANO][:] = [carta("Balance")]
    b[Zona.CAMPO][:] = [carta("Island") for _ in range(6)]
    b[Zona.MANO][:] = [carta("Island") for _ in range(6)]
    assert strip_per_balance(p, "AI") is None  # senza Mox né Sol Ring resterebbe a secco come lui


SCAVENGER = "{G}, {T}, Sacrifice Scavenger Folk: Destroy target artifact."


def test_scavenger_folk_blocca_poi_si_sacrifica_su_un_artefatto():
    """Come in torneo: Scavenger Folk blocca un 4/4 e prima dei danni si sacrifica per
    distruggere un artefatto. L'attaccante resta bloccato: niente danni al giocatore, e l'artefatto se ne va."""
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    folk = Carta("Scavenger Folk", "Creature — Human", "{G}", 1, 1, SCAVENGER)
    ai[Zona.CAMPO][:] = [folk, carta("Forest")]
    sol = carta("Sol Ring")
    bestia = cr("Bestia", 4, 4)
    b[Zona.CAMPO][:] = [bestia, sol]
    p.attivo = p.priorita = 1  # turno di B
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    combattimento.dichiara_attaccanti(p, "B", [bestia])
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    agisci(p, "AI")  # blocca con il Folk
    assert folk.id in p.combattimento.bloccanti()
    vita = ai.vita
    for _ in range(20):
        if p.fase != Fase.COMBATTIMENTO:
            break
        if p.giocatore_con_priorita.nome == "AI":
            agisci(p, "AI")
        else:
            azioni.passa_priorita(p, "B")
    assert sol in b[Zona.CIMITERO] and folk in ai[Zona.CIMITERO]
    assert ai.vita == vita  # la bestia è rimasta bloccata


def test_scavenger_folk_non_blocca_senza_artefatti():
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    folk = Carta("Scavenger Folk", "Creature — Human", "{G}", 1, 1, SCAVENGER)
    ai[Zona.CAMPO][:] = [folk, carta("Forest")]
    bestia = cr("Bestia", 4, 4)
    b[Zona.CAMPO][:] = [bestia]
    p.attivo = p.priorita = 1
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    combattimento.dichiara_attaccanti(p, "B", [bestia])
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    agisci(p, "AI")
    assert folk.id not in p.combattimento.bloccanti()


# --- Lezioni dai report dei tornei (blog Old School MTG) ------------------------------------------------

def test_i_danni_si_contano_per_mana_non_per_carte():
    """Mondiale 2022: due Bolt e una sola fonte rossa contro un avversario a 6 non fanno 6. Il Bolt va sulla
    minaccia, non in faccia."""
    from app.ai.avversaria import bersaglio_bolt
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Mountain")]
    ai[Zona.MANO][:] = [carta("Lightning Bolt"), carta("Lightning Bolt")]
    drago = cr("Drago", 3, 3, "Flying")
    b[Zona.CAMPO][:] = [drago]
    b.vita = 6
    assert bersaglio_bolt(p, "AI") == f"carta:{drago.id}"
    ai[Zona.CAMPO].append(carta("Mountain"))  # con due fonti rosse è letale
    assert bersaglio_bolt(p, "AI") == "giocatore:B"


def test_con_mirror_universe_pronto_niente_bolt_in_faccia_a_piccoli_passi():
    from app.ai.avversaria import bersaglio_bolt
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Mountain")]
    ai[Zona.MANO][:] = [carta("Lightning Bolt")]
    specchio = carta("Mirror Universe")
    b[Zona.CAMPO][:] = [specchio]
    b.vita = 8
    assert bersaglio_bolt(p, "AI") is None
    specchio.tappata = True
    assert bersaglio_bolt(p, "AI") == "giocatore:B"
    specchio.tappata = False
    b.vita = 3
    assert bersaglio_bolt(p, "AI") == "giocatore:B"  # letale: va bene anche col Mirror


def test_niente_bolt_sulle_creature_in_risposta_al_balance():
    from app.ai.avversaria import bersaglio_bolt
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Mountain"), cr("Orso", 2, 2), cr("Lupo", 2, 2)]
    ai[Zona.MANO][:] = [carta("Lightning Bolt")]
    elfo = cr("Elfo", 1, 1)
    b[Zona.CAMPO][:] = [carta("Plains"), carta("Plains"), elfo]
    b[Zona.MANO][:] = [carta("Balance")]
    p.attivo = p.priorita = 1
    azioni.lancia(p, "B", b[Zona.MANO][0])
    azioni.passa_priorita(p, "B")
    assert bersaglio_bolt(p, "AI") is None  # ucciderle farebbe sacrificare a lei una creatura in più


def test_con_earthquake_in_mano_tiene_le_creature_piccole():
    """n00bcon 13: «He started with Llanowar Elves and I didn't play my Lion, hoping to two-for-one him»."""
    p = p_base()
    ai = p.giocatore("AI")
    ai[Zona.CAMPO][:] = [carta("Mountain"), carta("Mountain")]
    leone = cr("Leone", 2, 1)
    ai[Zona.MANO][:] = [carta("Earthquake"), leone]
    ai.terre_giocate_nel_turno = 1
    agisci(p, "AI")
    assert leone in ai[Zona.MANO] and not p.pila


def test_la_contromagia_si_tiene_per_le_carte_decisive():
    from app.ai.politiche import vale_una_contromagia
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.MANO][:] = [carta("Counterspell")]
    b[Zona.MANO][:] = [carta("Island") for _ in range(4)]
    assert not vale_una_contromagia(p, "AI", cr("Orso", 2, 2))
    assert vale_una_contromagia(p, "AI", carta("Serra Angel"))
    assert vale_una_contromagia(p, "AI", Carta("Underworld Dreams", "Enchantment", "{B}{B}{B}"))
    ai[Zona.MANO].append(carta("Counterspell"))  # con due contromagie si può essere meno avari
    assert vale_una_contromagia(p, "AI", Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2))


def test_disenchant_prima_sul_permanente_che_fa_vincere():
    from app.ai.politiche import distruggi_permanente
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Plains"), carta("Plains")]
    sogni = Carta("Underworld Dreams", "Enchantment", "{B}{B}{B}")
    b[Zona.CAMPO][:] = [Carta("Clay Statue", "Artifact Creature — Golem", "{4}", 3, 1), sogni]
    assert distruggi_permanente(p, "AI", carta("Disenchant")) == ([f"carta:{sogni.id}"], 0)


def test_swords_sulla_propria_creatura_contro_un_bolt_letale():
    """n00bfest 2023: a 3 vita contro un Bolt in pila, Swords sulla propria creatura fa guadagnare vita."""
    from app.ai.politiche import rimozione
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai.vita = 3
    ai[Zona.CAMPO][:] = [carta("Plains"), cr("Orso", 2, 2)]
    b[Zona.CAMPO][:] = [carta("Mountain"), cr("Drago", 4, 4)]
    b[Zona.MANO][:] = [carta("Lightning Bolt")]
    p.attivo = p.priorita = 1
    azioni.lancia(p, "B", b[Zona.MANO][0], ["giocatore:AI"])
    azioni.passa_priorita(p, "B")
    orso = ai[Zona.CAMPO][1]
    assert rimozione(p, "AI", carta("Swords to Plowshares")) == ([f"carta:{orso.id}"], 0)


def test_mind_twist_aspetta_che_l_avversario_si_tappi():
    from app.ai.politiche import mind_twist
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Swamp") for _ in range(4)]
    b[Zona.CAMPO][:] = [carta("Island"), carta("Island")]
    b[Zona.MANO][:] = [carta("Island") for _ in range(3)]
    twist = Carta("Mind Twist", "Sorcery", "{X}{B}")
    ai[Zona.MANO][:] = [twist]
    assert mind_twist(p, "AI", twist) is None  # tre carte e {U}{U} aperti: può rispondere
    for isola in b[Zona.CAMPO]:
        isola.tappata = True
    assert mind_twist(p, "AI", twist) == (["giocatore:B"], 3)


def test_mulligan_se_la_mano_non_ha_i_colori_delle_magie():
    from app.ai.avversaria import senza_colori
    mano = [carta("Island"), carta("Island"), carta("Sol Ring"), Carta("Mind Twist", "Sorcery", "{X}{B}"),
            carta("Lightning Bolt"), carta("Swords to Plowshares")]
    assert senza_colori(mano)
    mano.append(carta("Counterspell"))
    assert not senza_colori(mano)


def test_le_creature_nuove_si_giocano_dopo_il_combattimento():
    p = p_base()
    ai = p.giocatore("AI")
    pronto = cr("Pronto", 2, 2)
    pronto.entrata_nel_turno = 1
    nuovo = cr("Nuovo", 3, 3)
    ai[Zona.CAMPO][:] = [carta("Forest"), carta("Forest"), pronto]
    ai[Zona.MANO][:] = [nuovo]
    ai.terre_giocate_nel_turno = 1
    agisci(p, "AI")
    assert nuovo in ai[Zona.MANO]  # prima fase principale: prima si attacca
    p.fase, p.priorita = Fase.PRINCIPALE_2, 0  # dopo il combattimento
    agisci(p, "AI")
    assert p.pila and p.pila[-1].carta is nuovo


def test_prima_le_creature_che_rubano_carte_e_quelle_con_l_aura():
    from app.ai.politiche import rimozione
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Plains")]
    gigante = carta("Hill Giant")
    spettro = carta("Hypnotic Specter")
    b[Zona.CAMPO][:] = [gigante, spettro]
    assert rimozione(p, "AI", carta("Swords to Plowshares")) == ([f"carta:{spettro.id}"], 0)
    orso = carta("Grizzly Bears")
    forza = carta("Holy Strength")
    forza.attaccata_a = orso.id
    b[Zona.CAMPO][:] = [gigante, orso, forza]
    assert rimozione(p, "AI", carta("Swords to Plowshares")) == ([f"carta:{orso.id}"], 0)  # due carte in una


def test_draw_go_bolt_in_faccia_a_fine_turno_contro_chi_non_ha_creature():
    from app.ai.avversaria import bersaglio_bolt
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Mountain")]
    ai[Zona.MANO][:] = [carta("Lightning Bolt")]
    b[Zona.CAMPO][:] = [carta("Island")]
    b[Zona.CIMITERO][:] = [carta("Counterspell"), carta("Ancestral Recall"), carta("Disenchant"),
                           carta("Swords to Plowshares"), carta("Balance"), carta("Time Walk")]  # The Deck
    p.attivo = p.priorita = 1
    assert bersaglio_bolt(p, "AI") is None  # nel suo turno, a metà: si tiene
    p.fase = Fase.FINALE
    assert bersaglio_bolt(p, "AI") == "giocatore:B"
    b[Zona.CAMPO].append(cr("Orso", 2, 4))
    assert bersaglio_bolt(p, "AI") is None  # ha una creatura: il Bolt resta per le creature


def test_mulligan_conta_mox_e_sol_ring_come_fonti():
    """Una terra, Mox e Sol Ring: è una mano da tenere (mtg.wiki, Mulligan). Senza terre no."""
    from app.engine import mulligan as mull
    p = nuova_partita({"AI": [carta("Island") for _ in range(30)], "B": [carta("Forest") for _ in range(30)]},
                      seed=40, mulligan=True)
    from app.ai.avversaria import decidi_mulligan
    ai = p.giocatore("AI")
    ai[Zona.MANO][:] = [carta("Island"), carta("Mox Sapphire"), carta("Sol Ring"), carta("Counterspell"),
                        carta("Ancestral Recall"), carta("Serra Angel"), carta("Swords to Plowshares")]
    decidi_mulligan(p, "AI")
    assert p.mulligan["AI"].tenuta and p.mulligan["AI"].fatti == 0


def test_fellwar_stone_subito_come_i_mox():
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Island"), carta("Island")]
    fellwar = carta("Fellwar Stone")
    ai[Zona.MANO][:] = [fellwar, carta("Counterspell")]
    ai.terre_giocate_nel_turno = 1
    b[Zona.CAMPO][:] = [carta("Swamp")]
    b[Zona.MANO][:] = [carta("Swamp") for _ in range(5)]
    agisci(p, "AI")
    assert p.pila and p.pila[-1].carta is fellwar  # più mana domani batte il Counterspell tenuto oggi


def test_moat_conta_le_mishra_s_factory_avversarie():
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    b[Zona.CAMPO][:] = [Carta("Mishra's Factory", "Land", "", None, None, FACTORY_VERA) for _ in range(2)]
    assert permanente_utile(p, "AI", carta("Moat"))


def test_niente_contromagia_su_un_bolt_in_faccia_a_vita_piena():
    from app.ai.politiche import contromagia
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO][:] = [carta("Island"), carta("Island")]
    contro = carta("Counterspell")
    ai[Zona.MANO][:] = [contro]
    b[Zona.CAMPO][:] = [carta("Mountain")]
    b[Zona.MANO][:] = [carta("Lightning Bolt"), carta("Mountain"), carta("Mountain")]
    p.attivo = p.priorita = 1
    azioni.lancia(p, "B", b[Zona.MANO][0], ["giocatore:AI"])
    azioni.passa_priorita(p, "B")
    assert contromagia(p, "AI", contro) is None  # 3 danni a 20 vita: si tiene per Ball Lightning
    ai.vita = 5
    assert contromagia(p, "AI", contro) is not None
