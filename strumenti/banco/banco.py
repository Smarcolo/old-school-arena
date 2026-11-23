"""Banco: AI nuova (app.ai) contro AI vecchia (vecchia/), mazzi di carte_base, posti scambiati.
uso: python banco.py N"""
import json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, ".")
from app.ai import avversaria as nuova, previsione
import vecchia.avversaria as vecchia
import vecchia.previsione as vprev
from app.engine import mulligan
from app.engine.stato import Carta, nuova_partita

BASE = {c["nome"]: c for c in json.loads(Path("app/cards/carte_base.json").read_text())}
def carta(n):
    d = BASE[n]; return Carta(d["nome"], d["tipo"], d.get("costo", ""), d.get("forza"), d.get("costituzione"), d.get("testo", ""))
MAZZI = {
 "the_deck": {"Island": 7, "Plains": 5, "Tundra": 3, "Mishra's Factory": 2, "Strip Mine": 1, "Library of Alexandria": 1,
   "Mox Pearl": 1, "Mox Sapphire": 1, "Sol Ring": 1, "Black Lotus": 1, "Counterspell": 4, "Mana Drain": 2,
   "Swords to Plowshares": 4, "Disenchant": 3, "Balance": 1, "Wrath of God": 2, "Ancestral Recall": 1, "Time Walk": 1,
   "Jayemdae Tome": 2, "Serra Angel": 3, "Mahamoti Djinn": 1, "Ivory Tower": 1, "Icy Manipulator": 1, "Moat": 1},
 "zoo": {"Mountain": 5, "Forest": 4, "Taiga": 4, "Plateau": 2, "Savannah": 1, "Mishra's Factory": 2, "Strip Mine": 1,
   "Kird Ape": 4, "Savannah Lions": 4, "Erhnam Djinn": 3, "Serendib Efreet": 2, "Ball Lightning": 2, "Lightning Bolt": 4,
   "Swords to Plowshares": 4, "Disenchant": 2, "Giant Growth": 2, "Fireball": 1, "Chaos Orb": 1, "Mox Ruby": 1, "Sol Ring": 1},
 "nero": {"Swamp": 12, "Badlands": 2, "Mountain": 3, "Mishra's Factory": 2, "Strip Mine": 1, "Dark Ritual": 4,
   "Hypnotic Specter": 4, "Juzám Djinn": 4, "Sengir Vampire": 2, "Black Knight": 2, "Terror": 4, "Lightning Bolt": 4,
   "Sinkhole": 3, "Mind Twist": 1, "Demonic Tutor": 1, "Black Vise": 1, "Mox Jet": 1, "Sol Ring": 1, "Fireball": 1, "Disintegrate": 1},
 "robots": {"Mishra's Factory": 4, "Strip Mine": 1, "City of Brass": 2, "Plains": 6, "Island": 4, "Tundra": 2,
   "Su-Chi": 4, "Juggernaut": 4, "Triskelion": 2, "Serra Angel": 2, "Sol Ring": 1, "Mox Pearl": 1, "Mox Sapphire": 1,
   "Black Lotus": 1, "Swords to Plowshares": 4, "Disenchant": 2, "Counterspell": 3, "Balance": 1, "Armageddon": 2,
   "Ancestral Recall": 1, "Time Walk": 1, "Icy Manipulator": 1, "Chaos Orb": 1},
}
def mazzo(n): return [carta(k) for k, q in MAZZI[n].items() for _ in range(q)]

def gioca(nomi, mazzi, seme, chi_nuovo):
    p = nuova_partita({nomi[0]: mazzo(mazzi[0]), nomi[1]: mazzo(mazzi[1])}, seed=seme, mulligan=True)
    mod = {chi_nuovo: nuova, [n for n in nomi if n != chi_nuovo][0]: vecchia}
    for _ in range(30000):
        if p.vincitore: return p.vincitore
        if mulligan.in_corso(p):
            n = next(n for n, s in p.mulligan.items() if not s.finito); mod[n].decidi_mulligan(p, n)
        elif p.scelta: mod[p.scelta.giocatore].decidi_scelta(p, p.scelta.giocatore)
        else:
            n = p.giocatore_con_priorita.nome; mod[n].agisci(p, n)
    return max(p.giocatori, key=lambda g: g.vita).nome

if __name__ == '__main__':
    previsione.ABILITATA = False; vprev.ABILITATA = False
    import os
    from app.ai import politiche as npol
    for spegni in os.environ.get("SPEGNI","").split(","):
        if spegni == "dopo": nuova.dopo_il_combattimento = lambda p, n: False
        if spegni == "spazzata_mia": nuova.tiene_per_la_propria_spazzata = lambda p, n, c: False
        if spegni == "teme": nuova.teme_spazzata = lambda p, n: False
        if spegni == "contro": npol.vale_una_contromagia = lambda p, n, c: __import__("app.engine.mana",fromlist=["x"]).valore(c.costo) >= 2
        if spegni == "balance": nuova.risposta_a_balance = lambda p, n: False
        if spegni == "mirror": nuova.mirror_pronto = lambda p, n: False
        if spegni == "mulligan": nuova.senza_colori = lambda m: False
        if spegni == "bolt": nuova.bolt_pagabili = lambda p, n: sum(1 for c in p.giocatore(n)[__import__("app.engine.zone",fromlist=["Zona"]).Zona.MANO] if c.nome == "Lightning Bolt")
        if spegni == "drawgo": nuova.poche_creature = lambda p, c: False
        if spegni == "bersaglio": npol.valore_bersaglio = lambda p, c: (c.forza_attuale, c.costituzione_attuale)
        if spegni == "swords": npol.swords_per_salvarsi = lambda *a: None
        if spegni == "mindtwist":
            import vecchia.politiche as vpol; npol.POLITICHE["Mind Twist"] = vpol.mind_twist
        if spegni == "sogni": pass
    N = int(sys.argv[1]); vinte = tot = 0; per = {}
    nomi_m = list(MAZZI); rng = random.Random(1)
    for i in range(N):
        m = (rng.choice(nomi_m), rng.choice(nomi_m)); seme = rng.randrange(10**6)
        for scambio in (0, 1):  # stessi mazzi e seme, posti scambiati
            chi = "A" if scambio == 0 else "B"
            v = gioca(("A", "B"), m, seme, chi)
            vinte += v == chi; tot += 1
            k = m[0] if chi == "A" else m[1]; per.setdefault(k, [0, 0]); per[k][0] += v == chi; per[k][1] += 1
    print(f"nuova vince {vinte}/{tot} = {100*vinte/tot:.1f}%"); print({k: f"{a}/{b}" for k, (a, b) in per.items()})
