import pytest

from app.engine import azioni
from app.engine.stato import Carta, Fase, nuova_partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona


def terra_in_mano(p, nome):
    return next(c for c in p.giocatore(nome)[Zona.MANO] if c.is_terra)


def test_mano_iniziale(partita):
    for g in partita.giocatori:
        assert len(g[Zona.MANO]) == 7
        assert len(g[Zona.GRIMORIO]) == 33
    assert partita.fase == Fase.PRINCIPALE_1  # il primo giocatore salta la pescata


def test_una_terra_per_turno(partita):
    azioni.gioca_terra(partita, "A", terra_in_mano(partita, "A"))
    with pytest.raises(AzioneIllegale, match="già giocato"):
        azioni.gioca_terra(partita, "A", terra_in_mano(partita, "A"))


def test_niente_terre_nel_turno_avversario(partita):
    with pytest.raises(AzioneIllegale, match="tuo turno"):
        azioni.gioca_terra(partita, "B", terra_in_mano(partita, "B"))


def test_cambio_turno_stappa_e_pesca(partita):
    while partita.giocatore_attivo.nome == "A":
        azioni.passa_fase(partita)
    while partita.fase != Fase.PRINCIPALE_1:
        azioni.passa_fase(partita)
    assert partita.turno == 2
    assert len(partita.giocatore("B")[Zona.MANO]) == 8


def test_grimorio_vuoto_fa_perdere():
    # A ha solo la mano iniziale: salta la pescata al turno 1, ma al turno 3 deve pescare e perde.
    p = nuova_partita({"A": [Carta("Forest", "Basic Land") for _ in range(7)],
                       "B": [Carta("Forest", "Basic Land") for _ in range(8)]})
    while not p.vincitore:
        azioni.passa_fase(p)
    assert p.vincitore == "B" and p.turno == 3


def test_vita_a_zero(partita):
    azioni.modifica_vita(partita, "B", -20)
    assert partita.vincitore == "A"


def test_registro_eventi(partita):
    azioni.gioca_terra(partita, "A", terra_in_mano(partita, "A"))
    assert partita.registro.eventi[-1].tipo == "terra"
