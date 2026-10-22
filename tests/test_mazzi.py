from fastapi.testclient import TestClient

from app.api.main import app
from app.cards import mazzi
from app.cards.regole_swedish import RegoleMazzo

client = TestClient(app)


def test_analizza_testo():
    mazzo, sb, errori = mazzi.analizza_testo("4 Lightning Bolt\n2x hill giant\nSerra Angel\n# commento\n\nSideboard\n3 Giant Growth\n")
    assert mazzo == {"Lightning Bolt": 4, "hill giant": 2, "Serra Angel": 1}
    assert sb == {"Giant Growth": 3} and errori == []


def test_analisi_normalizza_e_segnala(conn):
    a = mazzi.analizza(conn, {"lightning bolt": 4, "Carta Inesistente": 1, "Mountain": 20}, {})
    assert a["mazzo"]["Lightning Bolt"] == 4
    assert "carta sconosciuta: Carta Inesistente" in a["problemi"]
    assert not a["giocabile"] and not a["legale"]
    assert not any("bozza" in x for x in a["avvisi"])  # liste verificate da Marco


def test_analisi_limiti_del_motore(conn):
    conn.execute("INSERT INTO carte (nome, tipo, costo, testo) VALUES ('Healing Salve', 'Instant', '{W}', 'Choose one...')")
    conn.execute("INSERT INTO carte (nome, tipo, costo, forza, costituzione, testo) VALUES "
                 "('Dragon Whelp', 'Creature — Dragon', '{2}{R}{R}', 2, 3, 'Flying\n{R}: Dragon Whelp gets +1/+0 until end of turn. "
                 "If this ability has been activated four or more times this turn, sacrifice Dragon Whelp at the beginning of the next end step.')")
    a = mazzi.analizza(conn, {"Healing Salve": 1, "Dragon Whelp": 1, "Serra Angel": 1, "Llanowar Elves": 1, "Forest": 56}, {})
    avvisi = " ".join(a["avvisi"])
    assert "Healing Salve: effetto non implementato" in avvisi
    assert "Dragon Whelp: abilità non ancora attive" in avvisi
    assert "Serra Angel" not in avvisi and "Llanowar" not in avvisi
    assert a["legale"] and a["curva"]["5"] == 1


def test_analisi_con_ristrette(conn):
    regole = RegoleMazzo(set_ammessi=[], ristrette=["Lightning Bolt"])
    a = mazzi.analizza(conn, {"Lightning Bolt": 2, "Mountain": 58}, {}, regole)
    assert any("ristretta" in p for p in a["problemi"])
    assert not any("non ancora compilate" in x for x in a["avvisi"])


def test_api_salva_apri_gioca_elimina():
    testo = "20 Forest\n10 Grizzly Bears\n10 War Mammoth\nSideboard\n2 Giant Growth"
    r = client.put("/api/mazzi/Mio verde", json={"testo": testo}).json()
    assert r["totale"] == 40 and r["giocabile"]
    assert any(m["nome"] == "Mio verde" for m in client.get("/api/mazzi").json())
    assert "10 War Mammoth" in client.get("/api/mazzi/Mio verde").json()["testo"]
    p = client.post("/api/partite", json={"mazzo": "Mio verde"}).json()
    assert p["giocatori"][0]["grimorio"] == 33
    assert client.delete("/api/mazzi/Mio verde").status_code == 200
    assert client.get("/api/mazzi/Mio verde").status_code == 404


def test_api_rifiuta_mazzo_non_giocabile():
    client.put("/api/mazzi/Corto", json={"testo": "5 Forest"})
    r = client.post("/api/partite", json={"mazzo": "Corto"})
    assert r.status_code == 400 and "almeno 20" in r.json()["detail"]


def test_api_righe_non_capite_e_ricerca():
    risultati = client.get("/api/carte", params={"q": "giant"}).json()
    assert {"Giant Growth", "Giant Spider", "Hill Giant"} <= {c["nome"] for c in risultati}
    assert risultati[0]["nome"].lower().startswith("giant")


def test_mazzi_predefiniti():
    nomi = {m["nome"] for m in client.get("/api/mazzi").json()}
    assert {"Verde (prova)", "Rosso (prova)"} <= nomi


def test_pagina_mazzi():
    assert "Aggiungi carte" in client.get("/mazzi.html").text


def test_avviso_colore_mancante(conn):
    a = mazzi.analizza(conn, {"Serra Angel": 4, "Lightning Bolt": 4, "Mountain": 52}, {})
    assert any("{W}" in x for x in a["avvisi"]) and not any("{R}" in x for x in a["avvisi"])


def test_lista_swedish_in_bozza(conn):
    conn.execute("INSERT INTO carte (nome, tipo, costo) VALUES ('Darkpact', 'Sorcery', '{B}{B}{B}')")
    a = mazzi.analizza(conn, {"Black Lotus": 2, "Darkpact": 1, "Swamp": 57}, {})
    assert any("Black Lotus è ristretta" in p for p in a["problemi"])
    assert any("Darkpact è bandita" in p for p in a["problemi"])
