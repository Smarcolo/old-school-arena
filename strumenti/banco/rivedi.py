"""Rivede una partita dello studio: python rivedi.py mazzo.txt avversario seme"""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0]); sys.path.insert(0, ".")
import studio
from app.ai import avversaria
from app.engine import mulligan
from app.engine.stato import nuova_partita
from banco import MAZZI, carta
mio, _, _ = studio.leggi(sys.argv[1])
p = nuova_partita({"Studio": [carta(k) for k, q in mio.items() for _ in range(q)],
                   "Rivale": [carta(k) for k, q in MAZZI[sys.argv[2]].items() for _ in range(q)]}, seed=int(sys.argv[3]), mulligan=True)
for _ in range(30000):
    if p.vincitore: break
    if mulligan.in_corso(p):
        n = next(n for n, s in p.mulligan.items() if not s.finito); avversaria.decidi_mulligan(p, n)
    elif p.scelta: avversaria.decidi_scelta(p, p.scelta.giocatore)
    else: avversaria.agisci(p, p.giocatore_con_priorita.nome)
print("vince", p.vincitore, "turno", p.turno)
for e in p.registro.eventi:
    if e.tipo in ("tappa", "mana", "fase", "passa", "pesca") and "grimorio" not in e.descrizione: continue
    print(f"T{e.turno:2d} {e.fase[:6]:6s} {e.descrizione}")
