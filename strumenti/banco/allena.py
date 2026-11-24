"""Allenamento dall'esperienza: l'avversaria gioca contro sé stessa con un parametro cambiato (app/ai/parametri.py).
Stessi mazzi e stesso seme a posti scambiati: vince solo chi gioca meglio. Previsione spenta (troppo lenta).
uso: python strumenti/banco/allena.py N nome=valore [nome=valore ...]   (N coppie di partite)
Stampa la percentuale di vittorie della variante contro i parametri attuali."""
import ast, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, ".")
from app.ai import avversaria, parametri, previsione
from app.engine import mulligan
from app.engine.stato import nuova_partita
from banco import MAZZI, carta

previsione.ABILITATA = False
BASE = dict(parametri.P)


def gioca(mazzi, seme, chi_variante, variante):
    p = nuova_partita({"A": [carta(k) for k, q in MAZZI[mazzi[0]].items() for _ in range(q)],
                       "B": [carta(k) for k, q in MAZZI[mazzi[1]].items() for _ in range(q)]}, seed=seme, mulligan=True)
    per = {chi_variante: variante, ("B" if chi_variante == "A" else "A"): BASE}
    for _ in range(30000):
        if p.vincitore:
            return p.vincitore
        if mulligan.in_corso(p):
            n = next(n for n, s in p.mulligan.items() if not s.finito)
            parametri.P = per[n]; avversaria.decidi_mulligan(p, n)
        elif p.scelta:
            n = p.scelta.giocatore; parametri.P = per[n]; avversaria.decidi_scelta(p, n)
        else:
            n = p.giocatore_con_priorita.nome; parametri.P = per[n]; avversaria.agisci(p, n)
    return max(p.giocatori, key=lambda g: g.vita).nome


def main():
    n = int(sys.argv[1])
    variante = dict(BASE)
    for arg in sys.argv[2:]:
        k, v = arg.split("=", 1)
        assert k in BASE, f"parametro sconosciuto: {k}"
        try:
            variante[k] = ast.literal_eval(v)
        except (ValueError, SyntaxError):
            variante[k] = v
    seme_base = int(__import__("os").environ.get("SEME", "1"))
    rng = random.Random(seme_base)
    vinte = tot = 0
    nomi = list(MAZZI)
    for _ in range(n):
        m = (rng.choice(nomi), rng.choice(nomi)); seme = rng.randrange(10**6)
        for chi in ("A", "B"):
            vinte += gioca(m, seme, chi, variante) == chi; tot += 1
    print(json.dumps({"variante": sys.argv[2:], "vinte": vinte, "partite": tot, "percentuale": round(100 * vinte / tot, 1)}))


if __name__ == "__main__":
    main()
