"""Studio di un mazzo: lo fa giocare all'AI contro i mazzi del banco, con previsione spenta, e raccoglie cosa
succede. uso: python studio.py mazzo.txt N
Stampa: vittorie per avversario, turno medio di fine, come finiscono le partite (vita, grimorio), carte più
giocate nelle vittorie e nelle sconfitte, uso di Millstone (su chi), mulligan."""
import json, os, random, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, ".")
from app.ai import avversaria, previsione
from app.engine import mulligan
from app.engine.stato import Carta, nuova_partita
from app.engine.zone import Zona
from banco import MAZZI, carta, BASE

previsione.ABILITATA = False
# PARAM="nome=valore,nome=valore": parametri cambiati solo per chi gioca il mazzo studiato
import ast as _ast, os as _os
from app.ai import parametri as _par
_BASE = dict(_par.P)
_MIEI = dict(_BASE)
for _kv in filter(None, _os.environ.get("PARAM", "").split(",")):
    _k, _v = _kv.split("="); _MIEI[_k] = _ast.literal_eval(_v)
import os
if os.environ.get("VECCHIA"):
    import vecchia.avversaria as pilota
    import vecchia.previsione as vp; vp.ABILITATA = False
else:
    pilota = avversaria


def leggi(file):
    mazzo, side, sconosciute = {}, {}, []
    dove = mazzo
    for riga in Path(file).read_text().splitlines():
        riga = riga.strip()
        if not riga:
            continue
        if riga.lower().startswith("sideboard"):
            dove = side
            continue
        n, nome = riga.split(" ", 1)
        if nome not in BASE:
            sconosciute.append(nome)
            continue
        dove[nome] = dove.get(nome, 0) + int(n)
    return mazzo, side, sconosciute


def gioca(mio, contro, seme, io_primo):
    nomi = ("Studio", "Rivale") if io_primo else ("Rivale", "Studio")
    liste = {"Studio": mio, "Rivale": MAZZI[contro]}
    p = nuova_partita({n: [carta(k) for k, q in liste[n].items() for _ in range(q)] for n in nomi},
                      seed=seme, mulligan=True)
    mull = 0
    for _ in range(30000):
        if p.vincitore:
            break
        if mulligan.in_corso(p):
            n = next(n for n, s in p.mulligan.items() if not s.finito)
            prima = p.mulligan[n].fatti
            _par.P = _MIEI if n == "Studio" else _BASE
            (pilota if n == "Studio" else avversaria).decidi_mulligan(p, n)
            mull += n == "Studio" and p.mulligan.get(n) is not None and p.mulligan[n].fatti > prima
        elif p.scelta:
            n = p.scelta.giocatore; _par.P = _MIEI if n == "Studio" else _BASE
            (pilota if n == "Studio" else avversaria).decidi_scelta(p, n)
        else:
            n = p.giocatore_con_priorita.nome; _par.P = _MIEI if n == "Studio" else _BASE
            (pilota if n == "Studio" else avversaria).agisci(p, n)
    else:
        p.vincitore = max(p.giocatori, key=lambda g: g.vita).nome
    ev = p.registro.eventi
    giocate = Counter(e.descrizione.split(" lancia ")[1].split(" su ")[0].strip(" .")
                      for e in ev if e.giocatore == "Studio" and " lancia " in e.descrizione)
    mill = Counter()
    for e in ev:
        if e.tipo == "macina" or "macina" in e.descrizione.lower():
            if "Studio" in e.descrizione.split("macina")[0] or e.descrizione.startswith("Studio"):
                mill["su di sé" if e.descrizione.count("Studio") > 1 or "Studio macina" in e.descrizione else "?"] += 1
    perdente = next(g for g in p.giocatori if g.nome != p.vincitore) if p.vincitore in ("Studio", "Rivale") else None
    come = "pari" if perdente is None else ("grimorio" if perdente.pescato_da_vuoto else "vita" if perdente.vita <= 0 else "stallo")
    return p.vincitore == "Studio", p.turno, come, giocate, mull


def main():
    mio, side, sconosciute = leggi(sys.argv[1])
    n = int(sys.argv[2])
    print(f"carte nel mazzo: {sum(mio.values())}  (sconosciute al banco, tolte: {sconosciute})")
    rng = random.Random(int(os.environ.get("SEME", "7")))
    totale = Counter(); vittorie = Counter(); turni = []; come = Counter(); in_vittoria = Counter()
    in_sconfitta = Counter(); partite_v = partite_s = 0; mulligan_fatti = 0
    avversari = [m for m in MAZZI if not os.environ.get("CONTRO") or m in os.environ["CONTRO"].split(",")]
    for contro in avversari:
        for i in range(n):
            vinta, turno, fine, giocate, mull = gioca(mio, contro, rng.randrange(10**6), i % 2 == 0)
            totale[contro] += 1; vittorie[contro] += vinta; turni.append(turno); come[(vinta, fine)] += 1
            mulligan_fatti += mull
            if vinta:
                in_vittoria.update(set(giocate)); partite_v += 1
            else:
                in_sconfitta.update(set(giocate)); partite_s += 1
    print("vittorie:", {k: f"{vittorie[k]}/{totale[k]} ({100*vittorie[k]//totale[k]}%)" for k in avversari})
    print(f"turno medio di fine: {sum(turni)/len(turni):.1f}")
    print("come finisce:", {("vinta" if v else "persa") + " per " + f: q for (v, f), q in come.items()})
    print(f"mulligan: {mulligan_fatti} su {sum(totale.values())} partite")
    print("carte lanciate (quota di partite) vinte / perse:")
    for nome in sorted(set(in_vittoria) | set(in_sconfitta), key=lambda k: -(in_vittoria[k] + in_sconfitta[k])):
        v = in_vittoria[nome] / max(partite_v, 1); s = in_sconfitta[nome] / max(partite_s, 1)
        print(f"  {nome:28s} {100*v:4.0f}% / {100*s:4.0f}%   {'+' if v > s + 0.1 else '-' if s > v + 0.1 else ' '}")


if __name__ == "__main__":
    main()
