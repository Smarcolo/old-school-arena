import random
import sqlite3

from app.cards import database, mazzi, scryfall, tcdecks

FORMATO = """
<table class="tourney_list">
<tr><th>Tournament Name</th><th>Players</th><th>Date</th></tr>
<tr><td><a href="deck.php?id=43448">X-point Old School Online Monthly #62</a></td><td>24</td><td>10/10/2026</td></tr>
<tr><td><a href="https://www.tcdecks.net/deck.php?id=43400">Hurloon Battle</a></td><td>30</td><td>03/10/2026</td></tr>
<tr><td><a href="deck.php?id=43448">X-point Old School Online Monthly #62</a></td><td>24</td><td>10/10/2026</td></tr>
</table>"""

TORNEO = """
<table>
<tr><th>Position</th><th>Archetype</th><th>Player</th></tr>
<tr><td>2</td><td><a href="deck.php?id=43448&amp;iddeck=900002">Atog</a></td><td>Ivan V.</td></tr>
<tr><td>1</td><td><a href="deck.php?id=43448&amp;iddeck=900001">Disco Troll</a></td><td>Oleg E.</td></tr>
<tr><td>3</td><td><a href="deck.php?id=43448&iddeck=900003">Lion Dib</a></td><td>Grigoriy K.</td></tr>
</table>"""

# Due forme diverse di pagina del mazzo: righe di tabella e testo con <br>
MAZZO_TABELLA = """
<table><tr><th>Creatures (4)</th></tr>
<tr><td>4 <a href="#">Savannah Lions</a></td></tr>
<tr><th>Instants (8)</th></tr>
<tr><td>4 <a>Lightning Bolt</a></td></tr><tr><td>4 <a>Swords to Plowshares</a></td></tr>
<tr><th>Lands (20)</th></tr><tr><td>20 <a>Plateau</a></td></tr>
<tr><td>28 cards</td></tr>
<tr><th>Sideboard (3)</th></tr><tr><td>3 <a>Disenchant</a></td></tr></table>"""
MAZZO_BR = """<div class="deck">4 Savannah Lions<br>4 Lightning Bolt<br/>4 Swords to Plowshares<br>
20 Plateau<br>Sideboard<br>3 Disenchant<br></div>"""


def test_tornei_recenti():
    tornei = tcdecks.tornei_recenti(FORMATO)
    assert [(t.id, t.nome) for t in tornei] == [("43448", "X-point Old School Online Monthly #62"), ("43400", "Hurloon Battle")]


def test_mazzi_del_torneo_ordinati_per_posizione():
    voci = tcdecks.mazzi_del_torneo(TORNEO, "43448", quanti=2)
    assert [(v.iddeck, v.nome, v.posizione, v.giocatore) for v in voci] == [
        ("900001", "Disco Troll", 1, "Oleg E."), ("900002", "Atog", 2, "Ivan V.")]


def test_lista_dal_mazzo_in_due_formati():
    for pagina in (MAZZO_TABELLA, MAZZO_BR):
        mazzo, side = tcdecks.lista_dal_mazzo(pagina)
        assert mazzo == {"Savannah Lions": 4, "Lightning Bolt": 4, "Swords to Plowshares": 4, "Plateau": 20}
        assert side == {"Disenchant": 3}


class Pagina:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


def finto_get(pagine):
    def get(url, **kw):
        for chiave, testo in pagine.items():
            if url.endswith(chiave):
                return Pagina(testo)
        raise OSError(f"404 {url}")
    return get


def test_importa_e_scelta_automatica(conn):
    lista = MAZZO_BR.replace("20 Plateau", "48 Plateau")  # 60 carte
    get = finto_get({"format=Old+School": FORMATO, "deck.php?id=43448": TORNEO, "deck.php?id=43400": "<p>vuoto</p>",
                     "iddeck=900001": lista, "iddeck=900002": lista.replace("Savannah Lions", "Carta Ignota"),
                     "iddeck=900003": "<p>niente</p>"})
    res = tcdecks.importa(conn, tornei=2, get=get, pausa=0)
    assert len(res.salvati) == 2 and res.carte_sconosciute == {"Carta Ignota"}
    assert any("lista non letta" in e for e in res.errori)
    voci = mazzi.elenco(conn, "tcdecks")
    assert {v["info"]["posizione"] for v in voci} == {1, 2} and voci[0]["info"]["url"].startswith("https://www.tcdecks.net/")
    scelto = mazzi.scegli_mazzo_avversaria(conn, random.Random(1))
    assert scelto.startswith("TC 1° Disco Troll")  # l'altro ha una carta sconosciuta: non giocabile


def test_nessun_mazzo_tcdecks(conn):
    assert mazzi.scegli_mazzo_avversaria(conn, random.Random(1)) is None


def test_errore_di_rete(conn):
    res = tcdecks.importa(conn, get=finto_get({}), pausa=0)
    assert res.salvati == [] and "non raggiungibile" in res.errori[0]


def test_migrazione_database_vecchio(tmp_path):
    vecchio = sqlite3.connect(tmp_path / "v.sqlite")
    vecchio.execute("CREATE TABLE mazzi (nome TEXT PRIMARY KEY, mazzo TEXT NOT NULL, "
                    "sideboard TEXT NOT NULL DEFAULT '{}', aggiornato TEXT)")
    vecchio.execute("INSERT INTO mazzi VALUES ('Vecchio', ?, '{}', NULL)", ('{"Forest": 20}',))
    vecchio.commit()
    conn = database.connetti(tmp_path / "v.sqlite")
    assert mazzi.elenco(conn)[0]["origine"] == ""


class Json:
    def __init__(self, dati):
        self.dati = dati

    def json(self):
        return self.dati

    def raise_for_status(self):
        pass


def test_import_scryfall_a_pagine(conn):
    pagine = [
        {"data": [{"name": "Lightning Bolt", "set": "lea", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "x"}],
         "has_more": True, "next_page": "https://api.scryfall.com/cards/search?page=2"},
        {"data": [{"name": "Lightning Bolt", "set": "2ed", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "x"},
                  {"name": "Juzám Djinn", "set": "arn", "type_line": "Creature — Djinn", "mana_cost": "{2}{B}{B}",
                   "power": "5", "toughness": "5", "oracle_text": "y"}], "has_more": False}]
    chiamate = []

    def get(url, params=None, **kw):
        chiamate.append((url, params))
        return Json(pagine[len(chiamate) - 1])

    n = scryfall.importa(conn, get=get, pausa=0)
    assert n == 2 and "e:psum" in chiamate[0][1]["q"] and chiamate[1][1] is None
    assert database.cerca(conn, "Lightning Bolt") and conn.execute(
        "SELECT set_codici FROM carte WHERE nome='Lightning Bolt'").fetchone()[0] == "2ed,lea"


def test_importa_url(conn):
    lista = MAZZO_BR.replace("20 Plateau", "48 Plateau")
    get = finto_get({"iddeck=5": "<title>Lion Dib - TC Decks</title>" + lista})
    res = tcdecks.importa_url(conn, "https://www.tcdecks.net/deck.php?id=4&iddeck=5", get=get)
    assert res.salvati == ["TC Lion Dib - TC Decks"]
    assert "serve l'indirizzo" in tcdecks.importa_url(conn, "https://example.com", get=get).errori[0]


def test_nomi_con_accenti_arabi_e_pari_merito():
    mazzo, _ = tcdecks.lista_dal_mazzo("<div>4 Dandân</div><div>1 Ring of Ma'rûf</div><div>1 El-Hajjâj</div>")
    assert mazzo == {"Dandân": 4, "Ring of Ma'rûf": 1, "El-Hajjâj": 1}
    righe = "".join(f'<tr><td>5</td><td><a href="deck.php?id=9&iddeck={i}">M{i}</a></td></tr>' for i in range(4))
    assert [v.posizione for v in tcdecks.mazzi_del_torneo(righe, "9")] == [1, 2, 3, 4]


def test_carica_torneo_dall_indirizzo_e_diagnosi(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(tcdecks, "DIAGNOSI", tmp_path / "diagnosi")
    lista = MAZZO_BR.replace("20 Plateau", "48 Plateau")
    get = finto_get({"deck.php?id=43448": TORNEO, "iddeck=900001": lista, "iddeck=900002": lista, "iddeck=900003": lista})
    top = tcdecks.carica_torneo(conn, "https://www.tcdecks.net/deck.php?id=43448", get=get, pausa=0)
    assert len(top.mazzi) == 3  # senza passare dall'elenco dei tornei
    salvate = sorted(f.name for f in (tmp_path / "diagnosi").iterdir())
    assert salvate[0] == "01-torneo.html" and len(salvate) == 4


def test_carica_torneo_spiega_cosa_non_va(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(tcdecks, "DIAGNOSI", tmp_path / "diagnosi")
    top = tcdecks.carica_torneo(conn, "plague", get=finto_get({"format=Old+School": FORMATO}), pausa=0)
    assert any("non trovato" in e and "ci sono:" in e for e in top.errori)

    class Bloccato:
        status_code, text = 403, "Just a moment..."
    top = tcdecks.carica_torneo(conn, "", get=lambda url, **kw: Bloccato(), pausa=0)
    assert any("codice 403" in e for e in top.errori)


TORNEO_OTTO = "<title>X-point Old School Online Monthly #62 - TCDecks</title><table>" + "".join(
    f'<tr><td>{i}</td><td><a href="deck.php?id=43448&amp;iddeck=9000{i}">Mazzo {i}</a></td><td>Giocatore {i}</td></tr>'
    for i in range(1, 9)) + "</table>"


def test_raccogli_tornei_per_il_file_su_github(tmp_path, monkeypatch):
    monkeypatch.setattr(tcdecks, "DIAGNOSI", tmp_path / "diagnosi")
    lista = MAZZO_BR.replace("20 Plateau", "48 Plateau")
    pagine = {"format=Old+School": FORMATO, "deck.php?id=43448": TORNEO_OTTO, "deck.php?id=43400": "<p>vuoto</p>"}
    pagine |= {f"iddeck=9000{i}": lista for i in range(1, 9)}
    dati = tcdecks.raccogli_tornei(5, get=finto_get(pagine), pausa=0)
    (torneo,) = dati["tornei"]
    assert torneo["nome"] == "X-point Old School Online Monthly #62"
    assert torneo["data"] == "10/10/2026" and torneo["giocatori"] == 24
    assert [m["posizione"] for m in torneo["mazzi"]] == list(range(1, 9))
    assert torneo["mazzi"][0]["sideboard"] == {"Disenchant": 3}
    assert any("Hurloon Battle" in e for e in dati["errori"])  # senza mazzi: saltato e spiegato


def test_top_otto_dall_elenco_e_copia_locale(conn, tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(tcdecks, "FILE_TORNEI", tmp_path / "tornei.json")
    lista = {"Plateau": 48, "Savannah Lions": 12}
    dati = {"tornei": [{"id": "43448", "nome": "Monthly #62", "url": "u", "mazzi": [
        {"posizione": i, "nome": f"Mazzo {i}", "giocatore": "G", "mazzo": lista, "sideboard": {}} for i in range(1, 9)]}]}

    class Risposta:
        status_code = 200
        def json(self):
            return dati
    assert tcdecks.elenco_tornei(get=lambda url, **kw: Risposta())["tornei"][0]["nome"] == "Monthly #62"
    senza_rete = finto_get({})
    assert json.loads((tmp_path / "tornei.json").read_text())["tornei"]  # copia locale per quando manca la rete
    top = tcdecks.top_otto_dall_elenco(conn, "43448", get=senza_rete)
    assert top.torneo == "Monthly #62" and len(top.mazzi) == 8
    assert len(mazzi.elenco(conn, tcdecks.ORIGINE)) == 8  # salvati: l'avversaria li può usare
    assert tcdecks.top_otto_dall_elenco(conn, "1", get=senza_rete).errori


def test_dettagli_nel_formato_vero_di_tcdecks():
    riga = ('<tr><td title="Paper"></td><td data-label="Tournament Name"><a href="deck.php?id=44640">The Plague 5 (Swe)</a></td>'
            '<td data-label="Players"><a href="deck.php?id=44640"> 65 Players </a></td>'
            '<td data-label="Date"><a href="deck.php?id=44640">03/10/2026</a></td></tr>')
    assert tcdecks.tornei_recenti(riga)[0].nome == "The Plague 5 (Swe)"
    assert tcdecks._dettagli_tornei(riga) == {"44640": {"data": "03/10/2026", "giocatori": 65}}


def test_verifica_anti_bot_riconosciuta(conn, tmp_path, monkeypatch):
    monkeypatch.setattr(tcdecks, "DIAGNOSI", tmp_path / "diagnosi")
    verifica = "<title>Verificación en curso...</title><p>Verificando que no eres un bot...</p>"
    top = tcdecks.carica_torneo(conn, "", get=finto_get({"format=Old+School": FORMATO, "deck.php?id=43448": verifica}), pausa=0)
    assert any("anti-bot" in e for e in top.errori)


def test_lista_nella_tabella_vera_di_tcdecks():
    """Intestazione «Sideboard» sopra le colonne; mazzo diviso in sezioni, sideboard senza (e ripetuta, annidata)."""
    carta = lambda n, nome: f'{n} <a class="screenshot" href="x" name="{nome}">{nome}</a><br />'
    pagina = ('<table class="table_deck"><tr><th colspan="2"> Mario playing Mardu </th><th>Position: 1 </th></tr>'
              '<tr><th colspan="2"> Deck Name: Kiwisdu </th><th scope="hide"> Sideboard </th></tr><tr align="left">'
              f'<td><h6>Creatures [4]</h6>{carta(4, "Hypnotic Specter")}<h6>Instants [4]</h6>{carta(4, "Lightning Bolt")}</td>'
              f'<td><h6>Land [52]</h6>{carta(52, "Swamp")}</td>'
              f'<td><table><tr><td>{carta(3, "Disenchant")}{carta(2, "Terror")}</td></tr><tr><td>5 Cards</td></tr></table></td>'
              '</tr></table>')
    mazzo, side = tcdecks.lista_dal_mazzo(pagina)
    assert mazzo == {"Hypnotic Specter": 4, "Lightning Bolt": 4, "Swamp": 52}
    assert side == {"Disenchant": 3, "Terror": 2}
