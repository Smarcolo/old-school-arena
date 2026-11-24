"""Underworld Dreams, Shatterstorm, Twiddle (lezioni dei report dei tornei) e come le usa l'avversaria."""
from app.engine import azioni
from app.engine.stato import Carta, nuova_partita
from app.engine.zone import Zona

SOGNI = Carta("Underworld Dreams", "Enchantment", "{B}{B}{B}", None, None,
              "Whenever an opponent draws a card, Underworld Dreams deals 1 damage to that player.")


def terra(nome, colore):
    return Carta(nome, f"Basic Land — {nome}", "", None, None, f"({{T}}: Add {{{colore}}}.)")


def p_base():
    p = nuova_partita({"AI": [terra("Swamp", "B") for _ in range(30)], "B": [terra("Forest", "G") for _ in range(30)]},
                      seed=7)
    p.turno = 5
    return p


def metti(p, chi, c):
    c.entrata_nel_turno = 1
    p.giocatore(chi)[Zona.CAMPO].append(c)
    return c


def test_underworld_dreams_fa_un_danno_per_carta_pescata_dall_avversario():
    p = p_base()
    metti(p, "AI", Carta(**{k: getattr(SOGNI, k) for k in ("nome", "tipo", "costo", "forza", "costituzione", "testo")}))
    azioni.pesca(p, "B", 3)
    assert p.giocatore("B").vita == 17
    azioni.pesca(p, "AI", 2)
    assert p.giocatore("AI").vita == 20  # le proprie pescate non fanno danni


def test_shatterstorm_distrugge_tutti_gli_artefatti_senza_rigenerazione():
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    mox = metti(p, "B", Carta("Mox Emerald", "Artifact", "{0}", None, None, "{T}: Add {G}."))
    sol = metti(p, "AI", Carta("Sol Ring", "Artifact", "{1}", None, None, "{T}: Add {C}{C}."))
    ai[Zona.CAMPO].extend(terra("Mountain", "R") for _ in range(4))
    tempesta = Carta("Shatterstorm", "Sorcery", "{2}{R}{R}")
    ai[Zona.MANO][:] = [tempesta]
    azioni.lancia(p, "AI", tempesta)
    azioni.passa_priorita(p, "AI")
    azioni.passa_priorita(p, "B")
    assert mox in b[Zona.CIMITERO] and sol in ai[Zona.CIMITERO]


def test_twiddle_tappa_o_stappa():
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    ai[Zona.CAMPO].append(terra("Island", "U"))
    orso = metti(p, "B", Carta("Grizzly Bears", "Creature — Bear", "{1}{G}", 2, 2))
    tw = Carta("Twiddle", "Instant", "{U}")
    ai[Zona.MANO][:] = [tw]
    azioni.lancia(p, "AI", tw, [f"carta:{orso.id}"])
    azioni.passa_priorita(p, "AI")
    azioni.passa_priorita(p, "B")
    assert orso.tappata


def test_ai_ancestral_sull_avversario_con_i_sogni():
    from app.ai.politiche import pescate
    p = p_base()
    metti(p, "AI", Carta("Underworld Dreams", "Enchantment", "{B}{B}{B}", None, None, SOGNI.testo))
    b = p.giocatore("B")
    b.vita = 3
    assert pescate(p, "AI", Carta("Ancestral Recall", "Instant", "{U}")) == (["giocatore:B"], 0)


def test_ai_shatterstorm_solo_quando_prende_piu_artefatti_a_lui():
    from app.ai.politiche import shatterstorm
    p = p_base()
    tempesta = Carta("Shatterstorm", "Sorcery", "{2}{R}{R}")
    metti(p, "B", Carta("Mox Emerald", "Artifact", "{0}", None, None, "{T}: Add {G}."))
    assert shatterstorm(p, "AI", tempesta) is None  # un Mox solo: si aspetta
    metti(p, "B", Carta("Jayemdae Tome", "Artifact", "{4}", None, None, "{4}, {T}: Draw a card."))
    metti(p, "B", Carta("Su-Chi", "Artifact Creature — Construct", "{4}", 4, 4))
    assert shatterstorm(p, "AI", tempesta) == ([], 0)


def test_ai_twiddle_sull_unico_bloccante_per_chiudere():
    from app.ai.politiche import twiddle
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    metti(p, "AI", Carta("Orso", "Creature — Bear", "{1}{G}", 3, 3))
    muro = metti(p, "B", Carta("Muro", "Creature — Wall", "{1}", 0, 5))
    b.vita = 3
    assert twiddle(p, "AI", Carta("Twiddle", "Instant", "{U}")) == ([f"carta:{muro.id}"], 0)
    b.vita = 10
    assert twiddle(p, "AI", Carta("Twiddle", "Instant", "{U}")) is None


MAZE = Carta("Maze of Ith", "Land", "", None, None,
             "{T}: Untap target attacking creature. Prevent all combat damage that would be dealt to and dealt by it this turn.")


def test_maze_of_ith_ferma_l_attaccante_e_l_ai_lo_usa():
    from app.ai.avversaria import agisci
    from app.engine import combattimento
    p = p_base()
    ai, b = p.giocatore("AI"), p.giocatore("B")
    maze = metti(p, "AI", Carta(**{k: getattr(MAZE, k) for k in ("nome", "tipo", "costo", "forza", "costituzione", "testo")}))
    djinn = metti(p, "B", Carta("Juzam Djinn", "Creature — Djinn", "{2}{B}{B}", 5, 5))
    p.attivo = p.priorita = 1  # turno di B
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "AI")
    combattimento.dichiara_attaccanti(p, "B", [djinn])
    for _ in range(12):
        if p.fase.value != "combattimento":
            break
        if combattimento.deve_dichiarare_bloccanti(p, "AI") or p.giocatore_con_priorita.nome == "AI":
            agisci(p, "AI")
        else:
            azioni.passa_priorita(p, "B")
    assert maze.tappata and not djinn.tappata
    assert ai.vita == 20  # danni prevenuti


SINDBAD = "{T}: Draw a card and reveal it. If it isn't a land card, discard it."


def test_sindbad_tiene_le_terre_e_scarta_il_resto():
    from app.engine.abilita import analizza_abilita
    p = p_base()
    ai = p.giocatore("AI")
    sindbad = metti(p, "AI", Carta("Sindbad", "Creature — Human", "{1}{U}", 1, 1, SINDBAD))
    ab = analizza_abilita(sindbad)[0]
    assert ab.tipo == "sindbad"
    ai[Zona.GRIMORIO].append(Carta("Serra Angel", "Creature — Angel", "{3}{W}{W}", 4, 4))
    azioni.attiva(p, "AI", sindbad, ab)
    azioni.passa_priorita(p, "AI")
    azioni.passa_priorita(p, "B")
    assert any(c.nome == "Serra Angel" for c in ai[Zona.CIMITERO])  # non è una terra: scartata
    sindbad.tappata = False
    ai[Zona.GRIMORIO].append(terra("Island", "U"))
    mano = len(ai[Zona.MANO])
    azioni.attiva(p, "AI", sindbad, ab)
    azioni.passa_priorita(p, "AI")
    azioni.passa_priorita(p, "B")
    assert len(ai[Zona.MANO]) == mano + 1  # una terra: resta in mano


def test_ai_sindbad_con_field_of_dreams_solo_su_una_terra():
    from app.ai.politiche import sindbad_conviene
    p = p_base()
    ai = p.giocatore("AI")
    metti(p, "AI", Carta("Field of Dreams", "World Enchantment", "{W}{U}", None, None,
                         "Players play with the top card of their libraries revealed."))
    ai[Zona.CAMPO].extend([terra("Island", "U"), terra("Island", "U")])
    ai[Zona.GRIMORIO].append(Carta("Ancestral Recall", "Instant", "{U}"))
    assert not sindbad_conviene(p, "AI")  # non si butta via l'Ancestral
    ai[Zona.GRIMORIO].append(terra("Island", "U"))
    assert sindbad_conviene(p, "AI")
