import pytest
from fastapi.testclient import TestClient

from app.api import main
from app.cards import database, mazzi, tcdecks
from app.engine import azioni
from app.incontro import Lista
from app.simulazione import gioca_da_sola
from app.torneo import Partecipante, Torneo

ROSSO = {"Mountain": 18, "Gray Ogre": 10, "Lightning Bolt": 12}
VERDE = {"Forest": 18, "Grizzly Bears": 12, "War Mammoth": 10}


def costruttore(conn):
    return lambda lista: database.mazzo_da_lista(conn, lista)


def partecipanti(posto_umano=8):
    ps = [Partecipante(i, f"Mazzo {i}", f"G{i}", Lista(ROSSO if i % 2 else VERDE)) for i in range(1, 9) if i != posto_umano]
    ps.append(Partecipante(posto_umano, "Mio", "", Lista(VERDE), umano=True))
    return ps


def perdi(inc):
    while not inc.vincitore:
        azioni.concedi(inc.partita, "Tu")
        inc.registra_esito()
        if not inc.vincitore:
            inc.prossima()


def vinci(inc):
    while not inc.vincitore:
        azioni.concedi(inc.partita, "Avversaria")
        inc.registra_esito()
        if not inc.vincitore:
            inc.prossima()


def test_tabellone_e_quarti_simulati(conn):
    t = Torneo("Prova", partecipanti(), costruttore(conn), seed=1)
    quarti = t.turni[0]
    assert [(s.a.posto, s.b.posto) for s in quarti] == [(1, 8), (4, 5), (2, 7), (3, 6)]
    assert quarti[0].con_umano and quarti[0].vincitore is None
    assert all(s.vincitore and s.punteggio in ("2-0", "2-1") for s in quarti[1:])
    assert t.fase == "Quarti di finale" and t.sfida_umano() is quarti[0]


def test_eliminato_si_simula_il_resto(conn):
    t = Torneo("Prova", partecipanti(), costruttore(conn), seed=2)
    perdi(t.crea_incontro_umano({"Tu"}))
    t.registra_incontro(t.incontri[t.turni[0][0].id_incontro])
    assert t.fase == "Finito" and t.campione and not t.campione.umano and len(t.turni) == 3


def test_vincere_il_torneo(conn):
    t = Torneo("Prova", partecipanti(posto_umano=3), costruttore(conn), seed=3)
    for fase in ("Quarti di finale", "Semifinali", "Finale"):
        assert t.fase == fase
        inc = t.crea_incontro_umano({"Tu"})
        assert t.crea_incontro_umano({"Tu"}) is inc  # stessa sfida, stesso incontro
        vinci(inc)
        t.registra_incontro(inc)
    assert t.campione.umano and t.stato()["campione"] == "Tu (Mio)"
    with pytest.raises(ValueError):
        t.crea_incontro_umano({"Tu"})


def test_partita_ai_contro_ai_finisce(conn):
    from app.engine.stato import nuova_partita
    p = nuova_partita({"A": database.mazzo_da_lista(conn, ROSSO), "B": database.mazzo_da_lista(conn, VERDE)}, seed=4, mulligan=True)
    assert gioca_da_sola(p) in ("A", "B")


def test_top_otto_dai_mazzi_salvati(conn):
    for i in range(1, 9):
        mazzi.salva(conn, f"TC {i}° Mazzo{i} · The Plague 5 (Swe)", ROSSO, {}, origine="tcdecks",
                    info={"torneo": "The Plague 5 (Swe)", "posizione": i, "giocatore": f"G{i}", "url": ""})
    def rotto(url, **kw):
        raise OSError("niente rete")
    top = tcdecks.carica_torneo(conn, "plague 5", get=rotto, pausa=0)
    assert top.torneo == "The Plague 5 (Swe)" and [v.posizione for v, _, _ in top.mazzi] == list(range(1, 9))
    assert "uso i mazzi già salvati" in top.errori[0]


def test_api_torneo_completo(monkeypatch):
    voci = [(tcdecks.VoceMazzo(str(i), f"Archetipo {i}", i, f"G{i}"), ROSSO if i % 2 else VERDE, {}) for i in range(1, 9)]
    voci[2] = (voci[2][0], {**ROSSO, "Carta Mai Vista": 2}, {})
    monkeypatch.setattr(tcdecks, "carica_torneo", lambda conn, nome: tcdecks.TopOtto("The Plague 5 (Swe)", voci))
    client = TestClient(main.app)
    r = client.post("/api/tornei", json={"torneo": "Plague 5", "posto": 8}).json()
    assert r["nome"] == "The Plague 5 (Swe)" and r["da_giocare"]
    assert any("Archetipo 3: 2 carte sconosciute" in a for a in r["avvisi"])
    assert r["turni"][0]["sfide"][0]["b"].startswith("Tu (")
    inc = client.post(f"/api/tornei/{r['id']}/gioca").json()
    assert inc["incontro"]["torneo"] == r["id"] and inc["incontro"]["mazzo_avversaria"].startswith("#1 Archetipo 1")
    for _ in range(2):
        if inc["richiesta"] == "mulligan":
            inc = client.post(f"/api/partite/{inc['id']}/comando", json={"testo": "tengo"}).json()["partita"]
        inc = client.post(f"/api/partite/{inc['id']}/comando", json={"testo": "concedo"}).json()["partita"]
        if inc["incontro"]["prossima_possibile"]:
            inc = client.post(f"/api/partite/{inc['id']}/prossima").json()
    stato = client.get(f"/api/tornei/{r['id']}").json()
    assert stato["fase"] == "Finito" and stato["campione"] and not stato["da_giocare"]


def test_api_posto_non_valido():
    client = TestClient(main.app)
    assert client.post("/api/tornei", json={"posto": 9}).status_code == 400
