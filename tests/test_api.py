from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def comando(id_partita, testo):
    return client.post(f"/api/partite/{id_partita}/comando", json={"testo": testo}).json()


def gioca_fino_al_tuo_prossimo_turno(p):
    """Passa e risponde finché non è di nuovo il tuo turno, in una fase principale, dopo almeno un turno dell'AI."""
    turno_iniziale = p["turno"]
    r = {"partita": p}
    for _ in range(40):
        q = r["partita"]
        if q["vincitore"]:
            return q
        if q["attivo"] == "Tu" and q["turno"] > turno_iniziale and q["richiesta"] is None and not q["pila"]:
            return q
        if q["richiesta"] == "bloccanti":
            testo = "nessun blocco"
        elif q["richiesta"] == "attaccanti":
            testo = "non attacco"
        elif q["richiesta"] == "scelta":
            testo = "non pago" if q["scelta"]["tipo"] == "paga" else f"danni su {q['scelta']['candidate'][0]['id']}"
        elif q["pila"] or q["attivo"] != "Tu":
            testo = "passa"
        else:
            testo = "fine turno"
        r = comando(q["id"], testo)
    raise AssertionError("la partita non avanza")


def test_partita_completa_via_api():
    p = client.post("/api/partite").json()
    assert isinstance(p["giocatori"][1]["mano"], int)  # mano avversaria nascosta
    assert p["incontro"]["numero"] == 1 and p["incontro"]["lancio_moneta"] in ("Tu", "Avversaria")
    assert p["richiesta"] == "mulligan"
    assert "mulligan" in comando(p["id"], "fine turno")["messaggio"]
    p = comando(p["id"], "tengo")["partita"]
    assert p["richiesta"] != "mulligan"
    assert comando(p["id"], "mano")["messaggio"].startswith("Mano:")
    p = gioca_fino_al_tuo_prossimo_turno(p)
    assert p["attivo"] == "Tu" and p["turno"] >= 2


def test_incontro_al_meglio_di_tre():
    p = client.post("/api/partite").json()
    id_ = p["id"]
    assert client.post(f"/api/partite/{id_}/prossima").status_code == 400  # la prima non è finita
    comando(id_, "tengo")
    r = comando(id_, "concedo")
    assert r["partita"]["vincitore"] == "Avversaria" and r["partita"]["incontro"]["vittorie"]["Avversaria"] == 1
    assert comando(id_, "passa")["partita"]["incontro"]["vittorie"]["Avversaria"] == 1  # contata una volta sola
    p2 = client.post(f"/api/partite/{id_}/prossima").json()
    assert p2["incontro"]["numero"] == 2 and p2["vincitore"] is None
    assert p2["attivo"] == "Tu" and p2["turno"] == 1  # inizia chi ha perso: tu (e si parte dal mulligan)
    assert any("ha perso la partita precedente" in e for e in p2["eventi"])
    comando(id_, "tengo")
    r = comando(id_, "concedo")
    inc = r["partita"]["incontro"]
    assert inc["vincitore"] == "Avversaria" and not inc["prossima_possibile"]
    assert client.post(f"/api/partite/{id_}/prossima").status_code == 400


def test_giudice_api():
    assert "risposta" in client.get("/api/giudice", params={"q": "terra per turno"}).json()


def test_frontend():
    assert "Old School Arena" in client.get("/").text


def test_sideboard_via_api():
    client.put("/api/mazzi/Con sideboard", json={"testo": "20 Forest\n20 Grizzly Bears\nSideboard\n2 Giant Growth"})
    p = client.post("/api/partite", json={"mazzo": "Con sideboard"}).json()
    id_ = p["id"]
    comando(id_, "tengo")
    r = comando(id_, "concedo")["partita"]
    assert r["incontro"]["liste"]["sideboard"] == {"Giant Growth": 2}
    assert client.post(f"/api/partite/{id_}/sideboard", json={"entra": {"Giant Growth": 2}, "esce": {"Forest": 1}}).status_code == 400
    r = client.post(f"/api/partite/{id_}/sideboard", json={"entra": {"Giant Growth": 2}, "esce": {"Grizzly Bears": 2}}).json()
    assert r["incontro"]["liste"]["mazzo"]["Giant Growth"] == 2
    p2 = client.post(f"/api/partite/{id_}/prossima").json()
    assert p2["incontro"]["numero"] == 2 and p2["incontro"]["liste"] is None
