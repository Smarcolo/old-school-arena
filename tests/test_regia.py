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
