from app.cards import database
from app.cards.regole_swedish import RegoleMazzo, valida_mazzo
from app.cards.scryfall import converti


def test_cerca_carta(conn):
    assert database.cerca(conn, "grizzly bears").forza == 2
    assert database.cerca(conn, "Carta Inesistente") is None


def test_mazzo_da_lista(conn):
    assert len(database.mazzo_da_lista(conn, {"Forest": 3, "Lightning Bolt": 1})) == 4


def test_validazione_mazzo():
    regole = RegoleMazzo(set_ammessi=["lea"], bandite=["Chaos Orb"], ristrette=["Black Lotus"])
    ok = {"Forest": 56, "Grizzly Bears": 4}
    assert valida_mazzo(ok, {}, regole) == []
    problemi = valida_mazzo({"Forest": 50, "Grizzly Bears": 5, "Black Lotus": 2, "Chaos Orb": 1}, {"Grizzly Bears": 1}, regole)
    assert any("minimo 60" in p for p in problemi)
    assert any("Grizzly Bears" in p for p in problemi)
    assert any("Black Lotus" in p and "ristretta" in p for p in problemi)
    assert any("Chaos Orb" in p and "bandita" in p for p in problemi)


def test_converti_scryfall_filtra_set():
    dati = [
        {"name": "Lightning Bolt", "set": "lea", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "x"},
        {"name": "Lightning Bolt", "set": "3ed", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "x"},
        {"name": "Lightning Bolt", "set": "m10", "type_line": "Instant", "mana_cost": "{R}", "oracle_text": "x"},
        {"name": "Tarmogoyf", "set": "fut", "type_line": "Creature", "power": "*", "toughness": "1+*"},
    ]
    righe = converti(dati, {"lea", "3ed"})
    assert len(righe) == 1 and righe[0]["set_codici"] == "3ed,lea"
