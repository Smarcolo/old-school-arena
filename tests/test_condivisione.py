"""Mazzi del PC anche sull'iPad: invio su GitHub (finto) e import nella versione per il browser."""
import base64
import json

from app.cards import condivisione, mazzi


class Risposta:
    def __init__(self, codice, dati=None):
        self.status_code, self._dati = codice, dati or {}

    def json(self):
        return self._dati


class GitHubFinto:
    def __init__(self, codice_put=201):
        self.inviati, self.codice_put = [], codice_put

    def get(self, url, **kw):
        return Risposta(200, {"sha": "abc"})

    def put(self, url, json=None, **kw):
        self.inviati.append((url, json, kw["headers"]))
        return Risposta(self.codice_put)


def test_pubblica_i_mazzi_dell_utente(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(condivisione, "FILE_CHIAVE", tmp_path / "chiave.txt")
    github = GitHubFinto()
    assert not condivisione.pubblica(conn, attendi=True, client=github)  # senza chiave non manda niente
    (tmp_path / "chiave.txt").write_text("github_pat_prova\n")
    mazzi.salva(conn, "Mio blu", {"Island": 40}, {"Counterspell": 2})
    mazzi.salva(conn, "TC 1° Atog · Plague", {"Mountain": 60}, {}, origine="tcdecks")
    assert condivisione.pubblica(conn, attendi=True, client=github)
    url, corpo, intestazioni = github.inviati[0]
    assert url.endswith("/contents/docs/mazzi_pc.json") and corpo["sha"] == "abc"
    assert intestazioni["Authorization"] == "Bearer github_pat_prova"
    nomi = [m["nome"] for m in json.loads(base64.b64decode(corpo["content"]))["mazzi"]]
    assert "Mio blu" in nomi and not any(n.startswith("TC ") for n in nomi)  # quelli dei tornei l'iPad li ha già
    assert condivisione.stato["ultimo"] and not condivisione.stato["errore"]
    condivisione.pubblica(conn, attendi=True, client=GitHubFinto(401))
    assert "chiave" in condivisione.stato["errore"]


def test_l_ipad_importa_una_volta_sola(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(condivisione, "FILE_DAL_PC", tmp_path / "mazzi_pc.json")
    monkeypatch.setattr(condivisione, "FILE_IMPORTATO", tmp_path / "importati.txt")
    assert condivisione.importa_dal_pc(conn) == 0  # nessun file: niente
    dati = {"aggiornato": "2026-10-28T08:00:00+00:00", "mazzi": [
        {"nome": "Dal PC", "mazzo": {"Forest": 40}, "sideboard": {}, "origine": "", "info": {}}]}
    (tmp_path / "mazzi_pc.json").write_text(json.dumps(dati))
    assert condivisione.importa_dal_pc(conn) == 1
    assert mazzi.leggi(conn, "Dal PC") == ({"Forest": 40}, {})
    assert condivisione.importa_dal_pc(conn) == 0  # stesso file: già importato


def test_api_chiave(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.api.main import app
    monkeypatch.setattr(condivisione, "FILE_CHIAVE", tmp_path / "chiave.txt")
    client = TestClient(app)
    assert client.get("/api/condivisione").json()["chiave"] is False
    assert client.post("/api/condivisione", json={"testo": "password a caso"}).status_code == 400
    monkeypatch.setattr(condivisione, "_invia", lambda dati, token, client=None: condivisione.stato.update(errore=""))
    assert client.post("/api/condivisione", json={"testo": "github_pat_x"}).json()["chiave"] is True
