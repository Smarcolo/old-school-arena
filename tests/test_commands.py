from app.commands.esegui import esegui
from app.commands.parser import analizza


def test_parser():
    assert analizza("Gioca la terra Forest").argomento == "forest"
    assert analizza("pesca 2").numero == 2
    assert analizza("avanti").azione == "passa"
    assert analizza("vita -3").numero == -3
    assert analizza("giudice: quante terre per turno?").azione == "giudice"
    assert analizza("balla la samba").azione == "sconosciuto"


def test_esegui_gioca_terra(partita):
    assert esegui(partita, "A", analizza("gioca forest")) == "Hai giocato Forest."
    assert "Mossa non valida" in esegui(partita, "A", analizza("gioca forest"))


def test_esegui_carta_assente(partita):
    assert "Non hai" in esegui(partita, "A", analizza("gioca black lotus"))


def test_metti_in_fondo():
    from app.commands.parser import analizza
    assert analizza("metti in fondo forest").azione == "infondo"
    assert analizza("metti forest").azione == "gioca"
