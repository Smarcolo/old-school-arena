from app.engine import azioni
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.zone import Zona
from app.regia import avanza, esegui_comando


def mountain():
    return Carta("Mountain", "Basic Land — Mountain")


def ogre():
    return Carta("Gray Ogre", "Creature — Ogre", "{2}{R}", 2, 2)


def partita_con_ai():
    p = nuova_partita({"Tu": [Carta("Forest", "Basic Land — Forest") for _ in range(30)],
                       "AI": [mountain() for _ in range(30)]}, seed=3)
    ai = p.giocatore("AI")
    ai[Zona.CAMPO].extend([mountain(), mountain()])
    ai[Zona.MANO].append(ogre())
    return p


def test_fine_turno_e_l_ai_lancia_una_creatura():
    p = partita_con_ai()
    esegui_comando(p, "Tu", "AI", "fine turno")
    # L'AI gioca una terra, lancia l'ogre e l'umano viene fermato per poter rispondere.
    assert p.giocatore_attivo.nome == "AI"
    assert [o.carta.nome for o in p.pila] == ["Gray Ogre"]
    assert p.giocatore_con_priorita.nome == "Tu"
    esegui_comando(p, "Tu", "AI", "passa")
    assert azioni.trova_in_zona(p, "AI", Zona.CAMPO, "gray ogre")
    # Il resto del turno AI scorre da solo fino alla fase principale dell'umano.
    assert p.giocatore_attivo.nome == "Tu" and p.fase == Fase.PRINCIPALE_1 and p.turno == 3


def test_passa_dalla_principale_1_si_ferma_alla_principale_2():
    p = partita_con_ai()
    esegui_comando(p, "Tu", "AI", "passa")
    assert p.fase == Fase.PRINCIPALE_2 and p.giocatore_attivo.nome == "Tu"


def test_avanza_non_tocca_l_umano_quando_deve_decidere():
    p = partita_con_ai()
    avanza(p, "Tu", "AI")
    assert p.turno == 1 and p.fase == Fase.PRINCIPALE_1


def test_fine_turno_con_una_propria_magia_in_pila_la_fa_risolvere():
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    tu[Zona.CAMPO].append(Carta("Forest", "Basic Land — Forest"))
    tu[Zona.MANO].append(Carta("Llanowar Elves", "Creature — Elf Druid", "{G}", 1, 1, "{T}: Add {G}."))
    esegui_comando(p, "Tu", "AI", "gioca llanowar elves")
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert azioni.trova_in_zona(p, "Tu", Zona.CAMPO, "llanowar elves")
    assert p.giocatore_attivo.nome == "AI"


def test_attacco_blocco_e_giant_growth_prima_dei_danni():
    """Il flusso che l'interfaccia spiega: principale 1 → «Vai al combattimento» → attacchi → l'AI blocca →
    ti fermi con Giant Growth giocabile → la lanci → «Vai ai danni»."""
    from app.api.main import vista
    p = partita_con_ai()
    p.scelte_manuali = {"Tu"}
    tu, ai = p.giocatore("Tu"), p.giocatore("AI")
    orso = Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2)
    orso.entrata_nel_turno = 0
    tu[Zona.CAMPO].extend([orso, Carta("Forest", "Basic Land — Forest")])
    muro = Carta("Gray Ogre", "Creature — Ogre", "{2}{R}", 2, 2)
    muro.entrata_nel_turno = 0
    ai[Zona.CAMPO].append(muro)
    ai[Zona.MANO].clear()
    tu[Zona.MANO][:] = [Carta("Giant Growth", "Instant", "{G}", None, None, "Target creature gets +3/+3 until end of turn.")]
    p.turno = 3
    esegui_comando(p, "Tu", "AI", "passa")
    assert vista(p)["richiesta"] == "attaccanti"
    esegui_comando(p, "Tu", "AI", "attacca con grizzly bears")
    v = vista(p)  # l'AI ha bloccato con l'ogre: l'umano si ferma prima dei danni
    assert v["combattimento"]["bloccanti_dichiarati"] and not v["combattimento"]["danni_inflitti"]
    assert v["priorita"] == "Tu" and v["giocatori"][0]["mano"][0]["giocabile"]
    esegui_comando(p, "Tu", "AI", "gioca giant growth su grizzly bears")
    esegui_comando(p, "Tu", "AI", "passa")  # si risolve
    esegui_comando(p, "Tu", "AI", "passa")  # danni
    assert orso in tu[Zona.CAMPO] and muro in ai[Zona.CIMITERO]


def test_le_tue_magie_si_risolvono_da_sole():
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    tu[Zona.CAMPO].extend(Carta("Forest", "Basic Land — Forest") for _ in range(2))
    tu[Zona.MANO].append(Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2))
    esegui_comando(p, "Tu", "AI", "gioca grizzly bears")
    assert not p.pila and azioni.trova_in_zona(p, "Tu", Zona.CAMPO, "grizzly bears")


def test_ti_fermi_se_l_avversaria_risponde():
    p = partita_con_ai()
    tu, ai = p.giocatore("Tu"), p.giocatore("AI")
    tu[Zona.CAMPO].extend(Carta("Forest", "Basic Land — Forest") for _ in range(2))
    tu[Zona.MANO].append(Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2))
    ai[Zona.CAMPO].extend(Carta("Island", "Basic Land — Island") for _ in range(2))
    # due contromagie: con una sola l'AI la terrebbe per una carta più importante di un orso
    ai[Zona.MANO][:] = [Carta("Counterspell", "Instant", "{U}{U}"), Carta("Counterspell", "Instant", "{U}{U}")]
    esegui_comando(p, "Tu", "AI", "gioca grizzly bears")
    assert p.pila and p.pila[-1].carta.nome == "Counterspell" and p.giocatore_con_priorita.nome == "Tu"


FACTORY = ("{T}: Add {C}.\n{1}: Mishra's Factory becomes a 2/2 Assembly-Worker artifact creature until end of turn. "
           "It's still a land.\n{T}: Target Assembly-Worker creature gets +1/+2 until end of turn.")


def test_mishra_factory_anima_blocca_e_si_pompa():
    p = partita_con_ai()
    p.scelte_manuali = {"Tu"}
    tu, ai = p.giocatore("Tu"), p.giocatore("AI")
    fac = Carta("Mishra's Factory", "Land", "", None, None, FACTORY)
    fac.entrata_nel_turno = 0
    tu[Zona.CAMPO].extend([fac, Carta("Forest", "Basic Land — Forest")])
    # 3/4: la Factory pompata (3/4) non lo uccide, quindi l'AI attacca (contro un 3/3 non attaccherebbe)
    orco = Carta("Muro che cammina", "Creature — Giant", "{3}{R}", 3, 4)
    orco.entrata_nel_turno = 0
    ai[Zona.CAMPO].append(orco)
    ai[Zona.MANO].clear()
    esegui_comando(p, "Tu", "AI", "fine turno")
    # l'AI attacca: ti fermi prima dei blocchi perché puoi animare la Factory
    assert p.combattimento and p.combattimento.attaccanti == [orco.id] and not p.combattimento.attesa_bloccanti
    esegui_comando(p, "Tu", "AI", f"attiva {fac.id} 1")
    assert fac.is_creatura
    esegui_comando(p, "Tu", "AI", "passa")  # ai blocchi
    esegui_comando(p, "Tu", "AI", f"blocca {orco.id} con {fac.id}")
    esegui_comando(p, "Tu", "AI", f"attiva {fac.id} 2 su {fac.id}")  # si tappa e si dà +1/+2: blocca lo stesso
    # l'abilità si risolve da sola e si va ai danni: 3/4 contro 3/4, sopravvivono entrambi
    assert orco in ai[Zona.CAMPO] and fac in tu[Zona.CAMPO] and tu.vita == 20
    assert any("Mishra's Factory prende +1/+2" in e.descrizione for e in p.registro.eventi)


def test_ancestral_nella_fase_finale_avversaria():
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    tu[Zona.CAMPO].append(Carta("Island", "Basic Land — Island"))
    tu[Zona.MANO][:] = [Carta("Ancestral Recall", "Instant", "{U}", None, None, "Target player draws three cards.")]
    p.giocatore("AI")[Zona.MANO].clear()
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.giocatore_attivo.nome == "AI" and p.fase == Fase.FINALE and p.giocatore_con_priorita.nome == "Tu"
    esegui_comando(p, "Tu", "AI", "gioca ancestral recall su me")
    assert len(tu[Zona.MANO]) == 4 and p.giocatore_attivo.nome == "Tu"  # 3 di Ancestral + la pescata del tuo turno


def test_scarto_a_fine_turno():
    p = partita_con_ai()
    p.scelte_manuali = {"Tu"}
    tu = p.giocatore("Tu")
    tu[Zona.MANO][:] = [Carta(f"Carta{i}", "Instant", "{9}") for i in range(9)]
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.scelta and "scartane" in p.scelta.testo and p.giocatore_attivo.nome == "Tu"
    esegui_comando(p, "Tu", "AI", "scelgo carta0")
    assert p.scelta and "ancora 1" in p.scelta.testo
    esegui_comando(p, "Tu", "AI", "scelgo carta1")
    assert len(tu[Zona.MANO]) == 7 and p.giocatore_attivo.nome == "AI"
    assert [c.nome for c in tu[Zona.CIMITERO]] == ["Carta0", "Carta1"]


def test_tappi_city_of_brass_scegliendo_il_colore_e_poi_lanci():
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    city = Carta("City of Brass", "Land", "", None, None,
                 "Whenever City of Brass becomes tapped, it deals 1 damage to you.\n{T}: Add one mana of any color.")
    tu[Zona.CAMPO].extend([city, Carta("Island", "Basic Land — Island")])
    tu[Zona.MANO][:] = [Carta("Ancestral Recall", "Instant", "{U}", None, None, "Target player draws three cards.")]
    esegui_comando(p, "Tu", "AI", f"tappa {city.id} per u")
    assert tu.riserva["U"] == 1 and tu.vita == 19
    esegui_comando(p, "Tu", "AI", "gioca ancestral recall su me")
    isola = next(c for c in tu[Zona.CAMPO] if c.nome == "Island")
    assert not isola.tappata and len(tu[Zona.MANO]) == 3  # pagato col mana in riserva


def test_mishra_factory_non_si_paga_da_sola_per_animarsi():
    from app.engine.abilita import analizza_abilita
    from app.engine.validazione import puo_attivare
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    fac = Carta("Mishra's Factory", "Land", "", None, None, FACTORY)
    fac.entrata_nel_turno = 0
    tu[Zona.CAMPO].append(fac)  # nessun altro mana
    anima = analizza_abilita(fac)[0]
    assert "serve un altro mana" in puo_attivare(p, "Tu", fac, anima)
    tu[Zona.CAMPO].append(Carta("Forest", "Basic Land — Forest"))
    assert puo_attivare(p, "Tu", fac, anima) is None
    azioni.attiva(p, "Tu", fac, anima)
    assert not fac.tappata


MIRROR = ("{T}, Sacrifice Mirror Universe: Exchange life totals with target opponent. "
          "Activate only during your upkeep.")
MILLSTONE = "{2}, {T}: Target player mills two cards."


def test_ti_fermi_nel_mantenimento_per_mirror_universe():
    p = partita_con_ai()
    tu, ai = p.giocatore("Tu"), p.giocatore("AI")
    specchio = Carta("Mirror Universe", "Artifact", "{6}", None, None, MIRROR)
    specchio.entrata_nel_turno = 0
    tu[Zona.CAMPO].append(specchio)
    ai[Zona.MANO].clear()
    tu.vita = 5
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.giocatore_attivo.nome == "Tu" and p.fase == Fase.MANTENIMENTO  # fermo qui, non salta alla principale
    esegui_comando(p, "Tu", "AI", f"attiva {specchio.id} 1 su avversaria")
    assert tu.vita == 20 and ai.vita == 5


def test_millstone_anche_sul_proprio_grimorio():
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    macina = Carta("Millstone", "Artifact", "{2}", None, None, MILLSTONE)
    macina.entrata_nel_turno = 0
    tu[Zona.CAMPO].extend([macina, Carta("Forest", "Basic Land — Forest"), Carta("Forest", "Basic Land — Forest")])
    prima = len(tu[Zona.GRIMORIO])
    esegui_comando(p, "Tu", "AI", f"attiva {macina.id} 1 su me")
    assert len(tu[Zona.GRIMORIO]) == prima - 2 and len(tu[Zona.CIMITERO]) == 2


def test_con_field_of_dreams_ti_fermi_nel_mantenimento_per_millstone():
    """Field of Dreams scopre la prima carta dei grimori: nel mantenimento, prima della pescata, puoi macinare con
    Millstone la tua carta inutile o quella buona dell'avversaria. Il gioco si ferma lì (anche nel suo turno)."""
    p = partita_con_ai()
    tu, ai = p.giocatore("Tu"), p.giocatore("AI")
    macina = Carta("Millstone", "Artifact", "{2}", None, None, MILLSTONE)
    sogni = Carta("Field of Dreams", "World Enchantment", "{W}{U}", None, None,
                  "Players play with the top card of their libraries revealed.")
    for c in (macina, sogni):
        c.entrata_nel_turno = 0
    tu[Zona.CAMPO].extend([macina, sogni, Carta("Forest", "Basic Land — Forest"), Carta("Forest", "Basic Land — Forest")])
    ai[Zona.MANO].clear()
    esegui_comando(p, "Tu", "AI", "fine turno")
    assert p.giocatore_attivo.nome == "AI" and p.fase == Fase.MANTENIMENTO  # fermo nel suo mantenimento
    cima = ai[Zona.GRIMORIO][-1]
    esegui_comando(p, "Tu", "AI", f"attiva {macina.id} 1 su avversaria")
    assert cima in ai[Zona.CIMITERO] and len(ai[Zona.CIMITERO]) == 2  # macinata prima che la pescasse


def test_black_lotus_due_mana_per_una_magia_e_uno_per_un_altra():
    """Il Lotus dà 3 mana: con Millstone ({2}) il mana che avanza è del colore che serve alla carta in mano
    (il Bolt), resta nella riserva e il gioco lo ricorda."""
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    lotus = Carta("Black Lotus", "Artifact", "{0}", None, None, "{T}, Sacrifice Black Lotus: Add three mana of any one color.")
    lotus.entrata_nel_turno = 0
    tu[Zona.CAMPO].append(lotus)
    tu[Zona.MANO][:] = [Carta("Millstone", "Artifact", "{2}", None, None, MILLSTONE),
                        Carta("Lightning Bolt", "Instant", "{R}", None, None, "Lightning Bolt deals 3 damage to any target.")]
    messaggio = esegui_comando(p, "Tu", "AI", "gioca millstone")
    assert tu.riserva["R"] == 1 and "in riserva" in messaggio
    esegui_comando(p, "Tu", "AI", "gioca lightning bolt su avversaria")
    assert p.giocatore("AI").vita == 17


def test_black_lotus_due_bianchi_per_serra_e_il_terzo_resta_per_wrath():
    """Il caso di Marco: Lotus tappato per il bianco, Serra Angel prende 2 dei 3 bianchi e il generico da Mishra's
    Factory, Strip Mine e una Tropical Island; il terzo bianco e il Mox Pearl restano per Wrath of God."""
    p = partita_con_ai()
    tu = p.giocatore("Tu")
    def c(nome, tipo, testo):
        x = Carta(nome, tipo, "", None, None, testo)
        x.entrata_nel_turno = 0
        return x
    lotus = c("Black Lotus", "Artifact", "{T}, Sacrifice Black Lotus: Add three mana of any one color.")
    pearl = c("Mox Pearl", "Artifact", "{T}: Add {W}.")
    fabbrica = c("Mishra's Factory", "Land", "{T}: Add {C}.")
    strip = c("Strip Mine", "Land", "{T}: Add {C}.\n{T}, Sacrifice Strip Mine: Destroy target land.")
    trop1 = c("Tropical Island", "Land — Forest Island", "")
    trop2 = c("Tropical Island", "Land — Forest Island", "")
    tu[Zona.CAMPO][:] = [lotus, pearl, fabbrica, strip, trop1, trop2]
    tu[Zona.MANO][:] = [Carta("Serra Angel", "Creature — Angel", "{3}{W}{W}", 4, 4, "Flying, vigilance"),
                        Carta("Wrath of God", "Sorcery", "{2}{W}{W}", None, None, "Destroy all creatures. They can't be regenerated.")]
    esegui_comando(p, "Tu", "AI", f"tappa {lotus.id} per w")
    esegui_comando(p, "Tu", "AI", "gioca serra angel")
    assert any(x.nome == "Serra Angel" for x in tu[Zona.CAMPO])
    assert tu.riserva["W"] == 1 and not pearl.tappata  # il terzo bianco e il Mox Pearl sono ancora lì
    assert fabbrica.tappata and strip.tappata and [trop1.tappata, trop2.tappata].count(True) == 1
