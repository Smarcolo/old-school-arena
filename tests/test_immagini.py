from fastapi.testclient import TestClient

from app.api.main import app
from app.cards import immagini

client = TestClient(app)


class Risposta:
    def __init__(self, stato=200, tipo="image/jpeg", contenuto=b"\xff\xd8finta"):
        self.status_code, self.headers, self.content = stato, {"content-type": tipo}, contenuto


def test_scarica_e_mette_in_cache(conn, tmp_path):
    chiamate = []

    def finto(url, **kw):
        chiamate.append(url)
        return Risposta()

    file = immagini.ottieni(conn, "Lightning Bolt", finto, tmp_path)
    assert file.read_bytes().startswith(b"\xff\xd8") and file.name == "lightning-bolt.jpg"
    assert "frame%3A1993" in chiamate[0]  # prima cerca la cornice del 1993...
    assert "exact=Lightning%20Bolt" in chiamate[1]  # ...e qui non la trova (risposta finta), quindi la predefinita
    assert immagini.ottieni(conn, "Lightning Bolt", finto, tmp_path) == file
    assert len(chiamate) == 2  # la seconda volta dalla cache


def test_usa_l_url_del_database(conn, tmp_path):
    conn.execute("UPDATE carte SET immagine_url = 'https://esempio/bolt.jpg' WHERE nome = 'Lightning Bolt'")
    chiamate = []
    immagini.ottieni(conn, "Lightning Bolt", lambda url, **kw: chiamate.append(url) or Risposta(), tmp_path)
    assert chiamate == ["https://esempio/bolt.jpg"]


def test_senza_rete_ritorna_none_e_non_riprova(conn, tmp_path):
    chiamate = []

    def rotto(url, **kw):
        chiamate.append(url)
        raise OSError("niente rete")

    assert immagini.ottieni(conn, "Hill Giant", rotto, tmp_path) is None
    assert immagini.ottieni(conn, "Hill Giant", rotto, tmp_path) is None
    assert len(chiamate) == 2  # ricerca della cornice e immagine, una volta sola


def test_risposta_non_immagine(conn, tmp_path):
    assert immagini.ottieni(conn, "Gray Ogre", lambda url, **kw: Risposta(404, "application/json"), tmp_path) is None


def test_endpoint_serve_la_cache():
    file = immagini.percorso_cache("Grizzly Bears")
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(b"\xff\xd8orso")
    r = client.get("/api/immagini/Grizzly Bears")
    assert r.status_code == 200 and r.content == b"\xff\xd8orso"


def test_endpoint_404_se_non_disponibile():
    immagini._falliti.add("carta inesistente")
    assert client.get("/api/immagini/Carta inesistente").status_code == 404


def test_sceglie_la_stampa_con_i_bordi_neri(conn, tmp_path):
    class Ricerca(Risposta):
        def json(self):
            return {"data": [{"set": "2ed", "image_uris": {"normal": "https://img/unlimited.jpg"}},
                             {"set": "leb", "image_uris": {"normal": "https://img/beta.jpg"}},
                             {"set": "3ed", "image_uris": {"normal": "https://img/revised.jpg"}}]}
    chiamate = []

    def finto(url, **kw):
        chiamate.append(url)
        return Ricerca(tipo="application/json") if "search" in url else Risposta()

    assert immagini.ottieni(conn, "Grizzly Bears", finto, tmp_path) is not None
    assert chiamate[1] == "https://img/beta.jpg"


def test_import_tiene_la_stampa_preferita():
    from app.cards import scryfall
    stampe = [{"name": "Bolt", "set": s, "type_line": "Instant", "image_uris": {"normal": f"https://img/{s}.jpg"}}
              for s in ("2ed", "lea", "leb")]
    (voce,) = scryfall.converti(stampe, {"2ed", "lea", "leb"})
    assert voce["immagine_url"] == "https://img/leb.jpg" and "_ordine" not in voce
