"""Guarda una partita del banco turno per turno: python strumenti/banco/guarda.py mazzoA mazzoB seme [giocatore]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, ".")
from app.ai import avversaria, previsione
from app.engine import mulligan
from app.engine.stato import Fase, nuova_partita
from app.engine.zone import Zona
from banco import MAZZI, carta
previsione.ABILITATA = False
a, b, seme = sys.argv[1], sys.argv[2], int(sys.argv[3])
chi = sys.argv[4] if len(sys.argv) > 4 else "A"
p = nuova_partita({"A": [carta(k) for k, q in MAZZI[a].items() for _ in range(q)],
                   "B": [carta(k) for k, q in MAZZI[b].items() for _ in range(q)]}, seed=seme, mulligan=True)
visti = set(); letti = 0
for _ in range(30000):
    if p.vincitore: break
    if p.fase == Fase.PRINCIPALE_1 and p.turno not in visti:
        visti.add(p.turno)
        for e in p.registro.eventi[letti:]:
            if e.tipo not in ("tappa", "mana", "fase", "pesca", "priorita"):
                print(f"     {e.descrizione}")
        letti = len(p.registro.eventi)
        for n in ("A", "B"):
            g = p.giocatore(n)
            print(f"T{p.turno} {n}{'*' if p.giocatore_attivo.nome == n else ' '} vita {g.vita:3d} mano {[c.nome for c in g[Zona.MANO]] if n == chi else len(g[Zona.MANO])} | campo {[c.nome + ('·' if c.tappata else '') for c in g[Zona.CAMPO]]}")
    if mulligan.in_corso(p):
        n = next(n for n, s in p.mulligan.items() if not s.finito); avversaria.decidi_mulligan(p, n)
    elif p.scelta: avversaria.decidi_scelta(p, p.scelta.giocatore)
    else: avversaria.agisci(p, p.giocatore_con_priorita.nome)
for e in p.registro.eventi[letti:]:
    if e.tipo not in ("tappa", "mana", "fase", "pesca", "priorita"):
        print(f"     {e.descrizione}")
print("vince", p.vincitore)
