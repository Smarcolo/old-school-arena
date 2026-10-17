import importlib

from fastapi.testclient import TestClient

from app.api import main
from app.cards import database
from app.engine import azioni
from app.incontro import Incontro, Lista
from app.salvataggio import Archivio
from app.simulazione import gioca_da_sola
from app.engine.zone import Zona

ROSSO = {"Mountain": 18, "Gray Ogre": 10, "Lightning Bolt": 12}
VERDE = {"Forest": 18, "Grizzly Bears": 12, "War Mammoth": 10}


def test_incontro_salvato_e_ripreso(conn, tmp_path):
    archivio = Archivio(tmp_path / "s.sqlite")
    inc = Incontro(["A", "B"], {"A": Lista(ROSSO), "B": Lista(VERDE)},
                   database.CostruttoreMazzi(tmp_path / "carte.sqlite"), seed=3, avversaria="Verde")
    gioca_da_sola(inc.partita)
    inc.registra_esito()
    archivio.salva("incontro", inc.id, inc, "prova")

    ripreso = Archivio(tmp_path / "s.sqlite").carica_tutti("incontro")[inc.id]
    assert ripreso.vittorie == inc.vittorie and ripreso.avversaria == "Verde"
    assert ripreso.partita.registro.eventi == inc.partita.registro.eventi
    ripreso.prossima()  # il costruttore dei mazzi funziona anche dopo il caricamento
    assert ripreso.numero == 2 and len(ripreso.partita.giocatori[0][Zona.MANO]) == 7
    assert [v["id"] for v in archivio.elenco()] == [inc.id]
    assert archivio.elimina(inc.id) and archivio.elenco() == []


def test_salvataggio_illeggibile_saltato(tmp_path):
    archivio = Archivio(tmp_path / "s.sqlite")
    with archivio.conn:
        archivio.conn.execute("INSERT INTO salvataggi VALUES ('x', 'incontro', '', '2026', ?)", (b"rotto",))
    assert archivio.carica_tutti("incontro") == {}


def test_partita_sopravvive_al_riavvio_del_server():
    client = TestClient(main.app)
    p = client.post("/api/partite").json()
    client.post(f"/api/partite/{p['id']}/comando", json={"testo": "tengo"})
    assert any(v["id"] == p["id"] for v in client.get("/api/salvataggi").json())
    prima = client.get(f"/api/partite/{p['id']}").json()

    riavviato = importlib.reload(main)  # come un nuovo avvio: rilegge i salvataggi dal disco
    client = TestClient(riavviato.app)
    dopo = client.get(f"/api/partite/{p['id']}").json()
    assert dopo == prima
    assert client.delete(f"/api/salvataggi/{p['id']}").json()["ok"]
    assert client.get(f"/api/partite/{p['id']}").status_code == 404


def test_torneo_salvato_con_il_tuo_incontro(conn, tmp_path):
    from app.torneo import Partecipante, Torneo
    ps = [Partecipante(i, f"Mazzo {i}", f"G{i}", Lista(ROSSO if i % 2 else VERDE)) for i in range(1, 8)]
    ps.append(Partecipante(8, "Mio", "", Lista(VERDE), umano=True))
    t = Torneo("Prova", ps, database.CostruttoreMazzi(tmp_path / "carte.sqlite"), seed=1)
    inc = t.crea_incontro_umano({"Tu"})
    archivio = Archivio(tmp_path / "s.sqlite")
    archivio.salva("torneo", t.id, t)

    ripreso = archivio.carica_tutti("torneo")[t.id]
    inc2 = ripreso.incontri[inc.id]
    assert ripreso.sfida_umano().id_incontro == inc2.id
    while not inc2.vincitore:
        azioni.concedi(inc2.partita, "Avversaria")
        inc2.registra_esito()
        if not inc2.vincitore:
            inc2.prossima()
    ripreso.registra_incontro(inc2)
    assert ripreso.fase == "Semifinali"
