from app.judge import indice
from app.judge.giudice import Giudice


def test_giudice_trova_regola(tmp_path):
    (tmp_path / "r.md").write_text("## Terre\nSi gioca una sola terra per turno.\n\n## Vita\nSi parte da 20.\n", encoding="utf-8")
    g = Giudice(indice.costruisci(tmp_path, tmp_path / "r.sqlite"))
    r = g.rispondi("quante terre posso giocare?")
    assert r["fonti"][0]["titolo"] == "Terre"


def test_giudice_senza_risultati(tmp_path):
    g = Giudice(indice.costruisci(tmp_path, tmp_path / "r.sqlite"))
    assert g.rispondi("ornitottero")["fonti"] == []


def test_giudice_con_i_testi_del_progetto():
    g = Giudice()
    assert g.rispondi("il banding funziona con travolgere?")["fonti"][0]["titolo"] == "Banding contro travolgere"
    assert "sacrificio" in g.rispondi("la rigenerazione salva dal sacrificio?")["risposta"]
    assert "Volare" in g.rispondi("posso bloccare un volante?")["fonti"][0]["titolo"]
    assert g.rispondi("che cosa")["fonti"] == []  # solo parole vuote
