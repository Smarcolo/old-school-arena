import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0]); sys.path.insert(0, ".")
import studio
from app.ai import avversaria, politiche
from app.engine import mulligan
from app.engine.validazione import fonti_di_mana, puo_lanciare
from app.engine.stato import nuova_partita
from app.engine.zone import Zona
from banco import MAZZI, carta
mio, _, _ = studio.leggi(sys.argv[1])
p = nuova_partita({"Studio": [carta(k) for k, q in mio.items() for _ in range(q)],
                   "Rivale": [carta(k) for k, q in MAZZI[sys.argv[2]].items() for _ in range(q)]}, seed=int(sys.argv[3]), mulligan=True)
for _ in range(30000):
    if p.vincitore: break
    if p.pila and p.pila[-1].carta.nome == sys.argv[4] and p.giocatore_con_priorita.nome == "Studio":
        g = p.giocatore("Studio")
        print("mano", [c.nome for c in g[Zona.MANO]]); print("campo", [(c.nome, c.tappata) for c in g[Zona.CAMPO]])
        for c in g[Zona.MANO]:
            if c.nome in ("Counterspell", "Mana Drain"):
                print(c.nome, puo_lanciare(p, "Studio", c), politiche.contromagia(p, "Studio", c))
        break
    if mulligan.in_corso(p):
        n = next(n for n, s in p.mulligan.items() if not s.finito); avversaria.decidi_mulligan(p, n)
    elif p.scelta: avversaria.decidi_scelta(p, p.scelta.giocatore)
    else: avversaria.agisci(p, p.giocatore_con_priorita.nome)
