"""Il Maestro consiglia all'umano la mossa dell'avversaria esperta, senza cambiare la partita."""
import pickle

from app.ai import maestro
from app.engine.stato import Carta, nuova_partita
from app.engine.zone import Zona


def terra(nome, colore):
    return Carta(nome, f"Basic Land — {nome}", "", None, None, f"({{T}}: Add {{{colore}}}.)")


def test_il_maestro_consiglia_il_bolt_letale_e_non_tocca_la_partita():
    p = nuova_partita({"Tu": [terra("Mountain", "R") for _ in range(30)],
                       "AI": [terra("Island", "U") for _ in range(30)]}, seed=5)
    p.turno = 5
    tu = p.giocatore("Tu")
    tu[Zona.CAMPO][:] = [terra("Mountain", "R")]
    tu[Zona.MANO][:] = [Carta("Lightning Bolt", "Instant", "{R}", None, None, "Lightning Bolt deals 3 damage to any target.")]
    tu.terre_giocate_nel_turno = 1
    p.giocatore("AI").vita = 3
    prima = pickle.dumps(p)
    r = maestro.consiglio(p, "Tu")
    assert "Lightning Bolt" in r["mossa"] and r["perche"]
    assert pickle.dumps(p) == prima  # la partita vera non cambia


def test_il_maestro_nel_turno_avversario():
    p = nuova_partita({"Tu": [terra("Mountain", "R") for _ in range(30)],
                       "AI": [terra("Island", "U") for _ in range(30)]}, seed=5)
    p.attivo = p.priorita = 1
    assert maestro.consiglio(p, "Tu")["mossa"] == "Adesso tocca all'avversaria."
