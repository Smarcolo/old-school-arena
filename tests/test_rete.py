import base64

from fastapi.testclient import TestClient

from app import avvio
from app.api.main import app

client = TestClient(app)  # il client di prova non arriva da 127.0.0.1: per il server è un altro dispositivo


def basic(password):
    return {"Authorization": "Basic " + base64.b64encode(f"marco:{password}".encode()).decode()}


def test_senza_rete_niente_password(monkeypatch):
    monkeypatch.delenv("OSA_PASSWORD", raising=False)
    assert client.get("/api/salute").status_code == 200


def test_dalla_rete_serve_la_password(monkeypatch):
    monkeypatch.setenv("OSA_PASSWORD", "segreta1")
    r = client.get("/api/salute")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]
    assert client.get("/api/salute", headers=basic("sbagliata")).status_code == 401
    assert client.get("/api/salute", headers=basic("segreta1")).status_code == 200
    assert client.get("/index.html", headers=basic("segreta1")).status_code == 200


def test_password_creata_una_volta_e_modificabile(tmp_path, monkeypatch):
    monkeypatch.setattr(avvio, "FILE_PASSWORD", tmp_path / "password.txt")
    prima = avvio.password()
    assert len(prima) == 8 and avvio.password() == prima
    (tmp_path / "password.txt").write_text("lamiapassword\n", encoding="utf-8")
    assert avvio.password() == "lamiapassword"
