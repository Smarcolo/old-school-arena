"""Aggiornamento automatico all'avvio: confronta le versioni come numeri e non tocca mai dati e .bat."""
import io
import zipfile

from app import aggiorna


def test_le_versioni_si_confrontano_come_numeri():
    assert aggiorna.numeri("2026.11.24-10") > aggiorna.numeri("2026.11.24-9")
    assert aggiorna.numeri("2026.12.1-1") > aggiorna.numeri("2026.11.30-5")


def test_lo_zip_non_tocca_dati_venv_e_bat(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("old-school-arena-ramo/app/versione.py", 'VERSIONE = "2099.1.1-1"\n')
        z.writestr("old-school-arena-ramo/data/carte.sqlite", "da non toccare")
        z.writestr("old-school-arena-ramo/.venv/x", "da non toccare")
        z.writestr("old-school-arena-ramo/avvia.bat", "da non toccare")
        z.writestr("old-school-arena-ramo/docs/app.zip", "sito iPad")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "carte.sqlite").write_text("i miei mazzi")
    scritti = aggiorna.installa_zip(buffer.getvalue(), tmp_path)
    assert scritti == ["app/versione.py"]
    assert (tmp_path / "data" / "carte.sqlite").read_text() == "i miei mazzi"
    assert not (tmp_path / "avvia.bat").exists() and not (tmp_path / "docs").exists()


def test_senza_rete_non_si_ferma(monkeypatch):
    monkeypatch.delenv("OSA_NO_AGGIORNA", raising=False)
    def senza_rete(*a, **kw):
        raise OSError("niente rete")
    monkeypatch.setattr(aggiorna, "versione_in_rete", senza_rete)
    assert aggiorna.aggiorna() is False
