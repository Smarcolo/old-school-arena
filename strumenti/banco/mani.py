import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0]); sys.path.insert(0, ".")
import studio
from app.ai import avversaria
from app.engine import mulligan
from app.engine.stato import nuova_partita, Fase
from app.engine.zone import Zona
from banco import MAZZI, carta
mio, _, _ = studio.leggi(sys.argv[1])
p = nuova_partita({"Studio": [carta(k) for k, q in mio.items() for _ in range(q)],
                   "Rivale": [carta(k) for k, q in MAZZI[sys.argv[2]].items() for _ in range(q)]}, seed=int(sys.argv[3]), mulligan=True)
visto = set()
for _ in range(30000):
    if p.vincitore: break
    if p.fase == Fase.PRINCIPALE_1 and p.giocatore_attivo.nome == "Studio" and p.turno not in visto:
        visto.add(p.turno); g = p.giocatore("Studio")
        print(f"T{p.turno} vita {g.vita} mano: {[c.nome for c in g[Zona.MANO]]} | campo: {[c.nome + ('*' if c.tappata else '') for c in g[Zona.CAMPO]]}")
    if mulligan.in_corso(p):
        n = next(n for n, s in p.mulligan.items() if not s.finito); avversaria.decidi_mulligan(p, n)
    elif p.scelta: avversaria.decidi_scelta(p, p.scelta.giocatore)
    else: avversaria.agisci(p, p.giocatore_con_priorita.nome)
