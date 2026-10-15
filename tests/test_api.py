from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_partita_completa_via_api():
    p = client.post("/api/partite").json()
    assert isinstance(p["giocatori"][1]["mano"], int)  # mano avversaria nascosta
    r = client.post(f"/api/partite/{p['id']}/comando", json={"testo": "mano"}).json()
    assert r["messaggio"].startswith("Mano:")
    # Passa finché il turno non torna a te: nel frattempo l'AI gioca il suo turno.
    for _ in range(7):
        r = client.post(f"/api/partite/{p['id']}/comando", json={"testo": "passa"}).json()
    assert r["partita"]["attivo"] == "Tu" and r["partita"]["turno"] == 3


def test_giudice_api():
    assert "risposta" in client.get("/api/giudice", params={"q": "terra per turno"}).json()


def test_frontend():
    assert "Old School Arena" in client.get("/").text
