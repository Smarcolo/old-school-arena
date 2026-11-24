"""L'osservatore: fa giocare l'avversaria contro sé stessa e annota gli errori che si ripetono.
uso: python strumenti/banco/osserva.py N
- passa la fase principale 2 con carte lanciabili in mano (non istantanei, non contromagie)
- non attacca con creature pronte quando l'avversario non ha bloccanti (né Factory pronte)
- perde con in mano carte che avrebbe potuto lanciare
Stampa i conteggi per carta, per capire dove guardare."""
import random, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, ".")
from app.ai import avversaria, previsione
from app.engine import combattimento, mulligan
from app.engine.stato import Fase, nuova_partita
from app.engine.validazione import puo_lanciare
from app.engine.zone import Zona
from banco import MAZZI, carta

previsione.ABILITATA = False
passate, non_attacca, morto_con = Counter(), Counter(), Counter()
esempi = {}


def gioca(mazzi, seme):
    p = nuova_partita({"A": [carta(k) for k, q in MAZZI[mazzi[0]].items() for _ in range(q)],
                       "B": [carta(k) for k, q in MAZZI[mazzi[1]].items() for _ in range(q)]}, seed=seme, mulligan=True)
    mazzo_di = {"A": mazzi[0], "B": mazzi[1]}
    lanciabile_al_turno = {}
    for _ in range(30000):
        if p.vincitore:
            break
        if mulligan.in_corso(p):
            n = next(n for n, s in p.mulligan.items() if not s.finito); avversaria.decidi_mulligan(p, n); continue
        if p.scelta:
            avversaria.decidi_scelta(p, p.scelta.giocatore); continue
        n = p.giocatore_con_priorita.nome
        g = p.giocatore(n)
        if p.fase in (Fase.PRINCIPALE_1, Fase.PRINCIPALE_2) and p.giocatore_attivo.nome == n and not p.pila:
            for c in g[Zona.MANO]:  # quando si poteva lanciare (per «perde con in mano»)
                if not c.is_terra and puo_lanciare(p, n, c) is None:
                    lanciabile_al_turno[c.id] = p.turno
        prima = None
        if p.fase == Fase.PRINCIPALE_2 and p.giocatore_attivo.nome == n and not p.pila:
            prima = [c for c in g[Zona.MANO] if not c.is_terra and not c.is_istantaneo
                     and puo_lanciare(p, n, c) is None]
        if combattimento.deve_dichiarare_attaccanti(p, n):
            avv = p.avversario_di(n).nome
            pronti = combattimento.possibili_attaccanti(p, n)
            difesa = combattimento.possibili_bloccanti(p, avv) + avversaria.bloccanti_nascosti(p, avv)
            scelti = avversaria.scegli_attaccanti(p, n)
            if pronti and not difesa and len(scelti) < len(pronti):
                for c in pronti:
                    if c not in scelti:
                        non_attacca[(mazzo_di[n], c.nome)] += 1
        fase = p.fase
        avversaria.agisci(p, n)
        passa = p.fase == fase and not p.pila and p.giocatore_con_priorita.nome != n
        if prima and (p.fase != fase or passa):
            for c in prima:
                if c in g[Zona.MANO]:
                    passate[(mazzo_di[n], c.nome)] += 1
                    esempi.setdefault((mazzo_di[n], c.nome), (mazzi, seme, p.turno))
    if p.vincitore in ("A", "B"):
        perdente = "B" if p.vincitore == "A" else "A"
        for c in p.giocatore(perdente)[Zona.MANO]:
            if not c.is_terra and lanciabile_al_turno.get(c.id, -99) >= p.turno - 4:
                morto_con[(mazzo_di[perdente], c.nome)] += 1
                esempi.setdefault(("morto", mazzo_di[perdente], c.nome), (mazzi, seme, p.turno))


rng = random.Random(3)
N = int(sys.argv[1])
for _ in range(N):
    gioca((rng.choice(list(MAZZI)), rng.choice(list(MAZZI))), rng.randrange(10**6))
print(f"partite: {N}")
print("\nPASSA LA FASE PRINCIPALE 2 CON CARTE LANCIABILI (mazzo, carta: volte):")
for k, v in passate.most_common(15):
    print(f"  {k[0]:9s} {k[1]:24s} {v:5d}   es. mazzi {esempi[k][0]} seme {esempi[k][1]} turno {esempi[k][2]}")
print("\nNON ATTACCA CON CREATURE PRONTE CONTRO NESSUN BLOCCANTE:")
for k, v in non_attacca.most_common(10):
    print(f"  {k[0]:9s} {k[1]:24s} {v:5d}")
print("\nPERDE CON IN MANO CARTE LANCIABILI NEGLI ULTIMI 2 TURNI SUOI (mazzo, carta: partite):")
for k, v in morto_con.most_common(15):
    e = esempi[("morto",) + k]
    print(f"  {k[0]:9s} {k[1]:24s} {v:5d}   es. mazzi {e[0]} seme {e[1]}")
