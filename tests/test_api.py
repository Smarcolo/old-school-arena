from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def comando(id_partita, testo):
    return client.post(f"/api/partite/{id_partita}/comando", json={"testo": testo}).json()


def test_partita_completa_via_api():
    p = client.post("/api/partite").json()
    assert isinstance(p["giocatori"][1]["mano"], int)  # mano avversaria nascosta
    assert p["priorita"] == "Tu" and p["pila"] == []
    assert p["richiesta"] == "mulligan"
    assert "mulligan" in comando(p["id"], "fine turno")["messaggio"]
    p = comando(p["id"], "tengo")["partita"]
    assert p["richiesta"] is None
    assert comando(p["id"], "mano")["messaggio"].startswith("Mano:")
    # Avanti finché non torna il tuo turno: l'AI gioca il suo, rispondendo «passa» quando lancia qualcosa.
    r = {"partita": p}
    for _ in range(20):
        r = comando(p["id"], "passa" if r["partita"]["pila"] else "fine turno")
        if r["partita"]["turno"] >= 3:
            break
    assert r["partita"]["attivo"] == "Tu" and r["partita"]["turno"] == 3


def test_giudice_api():
    assert "risposta" in client.get("/api/giudice", params={"q": "terra per turno"}).json()


def test_frontend():
    assert "Old School Arena" in client.get("/").text
