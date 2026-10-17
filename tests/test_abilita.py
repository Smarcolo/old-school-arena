import pytest

from app.ai.avversaria import scegli_attaccanti, scegli_bloccanti
from app.engine import azioni, combattimento
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def cr(nome, f, c, testo=""):
    return Carta(nome, "Creature — Test", "{1}", f, c, testo)


def terra(tipo="Forest"):
    return Carta(tipo, f"Basic Land — {tipo}")


@pytest.fixture
def p():
    partita = nuova_partita({"A": [terra() for _ in range(20)], "B": [terra() for _ in range(20)]}, seed=6)
    partita.turno = 3
    return partita


def metti(p, chi, *carte):
    p.giocatore(chi)[Zona.CAMPO].extend(carte)
    return carte if len(carte) > 1 else carte[0]


def al_blocco(p, *attaccanti):
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.fase == Fase.COMBATTIMENTO
    combattimento.dichiara_attaccanti(p, "A", list(attaccanti))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")


def ai_danni(p):
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)
    azioni.passa_priorita(p, p.giocatore_con_priorita.nome)


def test_volare_si_blocca_solo_con_volare_o_raggiungere(p):
    roc = metti(p, "A", cr("Roc", 3, 3, "Flying"))
    orso, ragno = metti(p, "B", cr("Orso", 2, 2), cr("Ragno", 2, 4, "Reach"))
    al_blocco(p, roc)
    with pytest.raises(AzioneIllegale, match="vola"):
        combattimento.dichiara_bloccanti(p, "B", [(orso, roc)])
    combattimento.dichiara_bloccanti(p, "B", [(ragno, roc)])


def test_volatore_contro_chi_non_puo_bloccarlo_salta_i_blocchi(p):
    roc = metti(p, "A", cr("Roc", 3, 3, "Flying"))
    metti(p, "B", cr("Orso", 2, 2))
    al_blocco(p, roc)
    assert p.combattimento.bloccanti_dichiarati
    ai_danni(p)
    assert p.giocatore("B").vita == 17


def test_passaterre(p):
    driadi = metti(p, "A", cr("Driadi", 1, 1, "Forestwalk"))
    orso = metti(p, "B", cr("Orso", 2, 2))
    metti(p, "B", terra("Forest"))
    al_blocco(p, driadi)
    assert p.combattimento.bloccanti_dichiarati  # non bloccabile: salta da solo
    with pytest.raises(AzioneIllegale):
        combattimento.dichiara_bloccanti(p, "B", [(orso, driadi)])


def test_difensore_non_attacca(p):
    muro = metti(p, "A", cr("Muro", 0, 8, "Defender"))
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    with pytest.raises(AzioneIllegale, match="difensore"):
        combattimento.dichiara_attaccanti(p, "A", [muro])


def test_cautela_non_tappa(p):
    angelo = metti(p, "A", cr("Angelo", 4, 4, "Flying, vigilance"))
    al_blocco(p, angelo)
    assert not angelo.tappata


def test_rapidita_attacca_subito(p):
    fulmine = metti(p, "A", cr("Fulmine", 6, 1, "Trample, haste"))
    fulmine.entrata_nel_turno = p.turno
    al_blocco(p, fulmine)
    assert p.combattimento.attaccanti == [fulmine.id]


def test_travolgere(p):
    mammut = metti(p, "A", cr("Mammut", 3, 3, "Trample"))
    elfo = metti(p, "B", cr("Elfo", 1, 1))
    al_blocco(p, mammut)
    combattimento.dichiara_bloccanti(p, "B", [(elfo, mammut)])
    ai_danni(p)
    assert p.giocatore("B").vita == 18 and azioni.trova_in_zona(p, "B", Zona.CAMPO, "elfo") is None


def test_senza_travolgere_niente_danni_al_giocatore(p):
    gigante = metti(p, "A", cr("Gigante", 3, 3))
    elfo = metti(p, "B", cr("Elfo", 1, 1))
    al_blocco(p, gigante)
    combattimento.dichiara_bloccanti(p, "B", [(elfo, gigante)])
    ai_danni(p)
    assert p.giocatore("B").vita == 20


def test_attacca_per_primo_uccide_senza_subire(p):
    arcieri = metti(p, "A", cr("Arcieri", 2, 1, "First strike"))
    orso = metti(p, "B", cr("Orso", 2, 2))
    al_blocco(p, arcieri)
    combattimento.dichiara_bloccanti(p, "B", [(orso, arcieri)])
    ai_danni(p)
    assert azioni.trova_in_zona(p, "B", Zona.CAMPO, "orso") is None
    assert arcieri.danni == 0


def test_attacca_per_primo_in_difesa(p):
    orso = metti(p, "A", cr("Orso", 2, 2))
    arcieri = metti(p, "B", cr("Arcieri", 2, 1, "First strike"))
    al_blocco(p, orso)
    combattimento.dichiara_bloccanti(p, "B", [(arcieri, orso)])
    ai_danni(p)
    assert azioni.trova_in_zona(p, "A", Zona.CAMPO, "orso") is None
    assert azioni.trova_in_zona(p, "B", Zona.CAMPO, "arcieri")


def test_priorita_tra_i_due_passi_di_danno(p):
    """Dopo i danni di «attacca per primo» i giocatori hanno priorità: B finisce l'attaccante con un Bolt
    prima che colpisca nel passo normale."""
    arcieri = metti(p, "A", cr("Arcieri", 2, 1, "First strike"))
    orco = metti(p, "A", cr("Orco", 3, 3))
    muro = metti(p, "B", cr("Muro", 0, 4))
    metti(p, "B", terra("Mountain"))
    al_blocco(p, arcieri, orco)
    combattimento.dichiara_bloccanti(p, "B", [(muro, orco)])
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")
    assert p.giocatore("B").vita == 18 and not p.combattimento.danni_inflitti  # solo gli arcieri hanno colpito
    azioni.passa_priorita(p, "A")
    bolt = Carta("Lightning Bolt", "Instant", "{R}")
    p.giocatore("B")[Zona.MANO].append(bolt)
    azioni.lancia(p, "B", bolt, [f"carta:{orco.id}"])
    azioni.passa_priorita(p, "B")
    azioni.passa_priorita(p, "A")  # il Bolt si risolve: l'orco ha 3 danni e muore
    azioni.passa_priorita(p, "A")
    azioni.passa_priorita(p, "B")  # passo normale: l'orco non c'è più, gli arcieri non colpiscono due volte
    assert p.combattimento.danni_inflitti and p.giocatore("B").vita == 18 and muro.danni == 0


def test_ai_attacca_in_volo_sopra_i_bloccanti_di_terra(p):
    roc = metti(p, "A", cr("Roc", 3, 3, "Flying"))
    metti(p, "B", cr("Wurm", 6, 4))
    assert scegli_attaccanti(p, "A") == [roc]


def test_ai_non_blocca_un_volatore_con_creature_di_terra(p):
    roc = metti(p, "A", cr("Roc", 3, 3, "Flying"))
    orso = metti(p, "B", cr("Orso", 2, 2))
    combattimento.inizia(p)
    p.fase = Fase.COMBATTIMENTO
    p.combattimento.attaccanti = [roc.id]
    p.giocatore("B").vita = 1
    assert scegli_bloccanti(p, "B") == []
