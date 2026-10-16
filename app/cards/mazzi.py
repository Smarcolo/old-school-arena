"""Mazzi salvati: formato testo, salvataggio in SQLite e analisi (regole Swedish + cosa il motore sa giocare)."""
import json
import re
import sqlite3
from collections import Counter

from app.cards import database
from app.cards.regole_swedish import TERRE_BASE, RegoleMazzo, carica_regole, valida_mazzo
from app.engine import carte_implementate  # noqa: F401  registra gli effetti
from app.engine import mana
from app.engine import inneschi, statici
from app.engine.abilita import riga_capita
from app.engine.effetti import EFFETTI
from app.engine.stato import Carta, parole_chiave_da_testo

MINIMO_PER_GIOCARE = 20  # sotto questo numero una partita di prova non ha senso
_RIGA = re.compile(r"^(?:(\d+)\s*x?\s+)?(.+?)\s*$", re.IGNORECASE)
_PROMEMORIA = re.compile(r"^\(.*\)$")


def analizza_testo(testo: str) -> tuple[dict[str, int], dict[str, int], list[str]]:
    """Legge righe come «4 Lightning Bolt», «4x Lightning Bolt» o «Lightning Bolt». Dopo una riga «Sideboard»
    (o con il prefisso «SB:») le carte vanno in sideboard. Ritorna (mazzo, sideboard, righe non capite)."""
    mazzo: Counter = Counter()
    sideboard: Counter = Counter()
    errori = []
    in_sideboard = False
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith(("#", "//")):
            continue
        if riga.lower().rstrip(":") in ("sideboard", "sb"):
            in_sideboard = True
            continue
        destinazione = sideboard if in_sideboard else mazzo
        if riga.lower().startswith("sb:"):
            destinazione, riga = sideboard, riga[3:].strip()
        m = _RIGA.match(riga)
        if not m or not m.group(2):
            errori.append(riga)
            continue
        destinazione[m.group(2)] += int(m.group(1) or 1)
    return dict(mazzo), dict(sideboard), errori


def formatta_testo(mazzo: dict[str, int], sideboard: dict[str, int]) -> str:
    righe = [f"{n} {nome}" for nome, n in mazzo.items()]
    if sideboard:
        righe += ["", "Sideboard"] + [f"{n} {nome}" for nome, n in sideboard.items()]
    return "\n".join(righe)


def normalizza(conn: sqlite3.Connection, lista: dict[str, int]) -> tuple[dict[str, int], list[str]]:
    """Corregge maiuscole e minuscole usando il database. Ritorna (lista, nomi sconosciuti)."""
    risultato: Counter = Counter()
    sconosciute = []
    for nome, n in lista.items():
        carta = database.cerca(conn, nome)
        if carta is None:
            sconosciute.append(nome)
            risultato[nome] += n
        else:
            risultato[carta.nome] += n
    return dict(risultato), sconosciute


def _limiti_motore(carta: Carta) -> str | None:
    """Cosa il motore non sa ancora fare con questa carta."""
    if carta.is_terra:
        if carta.nome not in TERRE_BASE and mana.mana_prodotto(carta) is None:
            return "terra non base: non produce mana nel motore"
        return None
    if not carta.is_permanente:
        return None if carta.nome in EFFETTI else "effetto non implementato: non si potrà lanciare"
    capite = parole_chiave_da_testo(carta.testo)
    for riga in carta.testo.splitlines():
        riga = riga.strip()
        if (not riga or _PROMEMORIA.match(riga) or mana.riga_di_mana(riga) or riga_capita(carta, riga)
                or inneschi.riga_capita(carta, riga) or statici.riga_capita(carta, riga)):
            continue
        if not {p.strip() for p in riga.lower().split(",")} <= capite:
            return "abilità non ancora attive nel motore"
    return None


def analizza(conn: sqlite3.Connection, mazzo: dict[str, int], sideboard: dict[str, int],
             regole: RegoleMazzo | None = None) -> dict:
    regole = regole or carica_regole()
    mazzo, sconosciute = normalizza(conn, mazzo)
    sideboard, sconosciute_sb = normalizza(conn, sideboard)
    problemi = [f"carta sconosciuta: {n}" for n in sconosciute + sconosciute_sb]
    problemi += valida_mazzo(mazzo, sideboard, regole)
    avvisi = []
    if not regole.bandite and not regole.ristrette:
        avvisi.append("Liste Swedish di carte bandite e ristrette non ancora compilate: il controllo è incompleto.")
    elif not regole.verificato:
        avvisi.append("Liste Swedish in bozza, non ancora verificate sul regolamento ufficiale.")
    curva: Counter = Counter()
    colori: Counter = Counter()
    prodotti: set[str] = set()
    for nome, n in mazzo.items():
        carta = database.cerca(conn, nome)
        if carta is None:
            continue
        if fonte := mana.mana_prodotto(carta):
            prodotti.update(fonte.colori)
        if motivo := _limiti_motore(carta):
            avvisi.append(f"{nome}: {motivo}")
        if not carta.is_terra:
            costo = mana.analizza_costo(carta.costo)
            curva[min(sum(costo.values()), 6)] += n
            for colore in mana.COLORI:
                if costo.get(colore):
                    colori[colore] += n
    for colore in sorted(set(colori) - prodotti, key=mana.COLORI.index):
        avvisi.append(f"Ci sono magie che chiedono {{{colore}}} ma nessuna carta del mazzo produce quel colore.")
    totale = sum(mazzo.values())
    return {
        "mazzo": mazzo, "sideboard": sideboard, "totale": totale, "totale_sideboard": sum(sideboard.values()),
        "problemi": problemi, "avvisi": avvisi, "legale": not problemi,
        "giocabile": not sconosciute and totale >= MINIMO_PER_GIOCARE,
        "curva": {str(k): curva[k] for k in range(7)}, "colori": dict(colori),
    }


def salva(conn: sqlite3.Connection, nome: str, mazzo: dict[str, int], sideboard: dict[str, int]) -> None:
    conn.execute(
        "INSERT INTO mazzi (nome, mazzo, sideboard) VALUES (?, ?, ?) ON CONFLICT(nome) DO UPDATE SET "
        "mazzo=excluded.mazzo, sideboard=excluded.sideboard, aggiornato=CURRENT_TIMESTAMP",
        (nome, json.dumps(mazzo, ensure_ascii=False), json.dumps(sideboard, ensure_ascii=False)),
    )
    conn.commit()


def leggi(conn: sqlite3.Connection, nome: str) -> tuple[dict[str, int], dict[str, int]] | None:
    r = conn.execute("SELECT mazzo, sideboard FROM mazzi WHERE nome = ?", (nome,)).fetchone()
    return (json.loads(r["mazzo"]), json.loads(r["sideboard"])) if r else None


def elenco(conn: sqlite3.Connection) -> list[dict]:
    righe = conn.execute("SELECT nome, mazzo, aggiornato FROM mazzi ORDER BY nome").fetchall()
    return [{"nome": r["nome"], "totale": sum(json.loads(r["mazzo"]).values()), "aggiornato": r["aggiornato"]} for r in righe]


def elimina(conn: sqlite3.Connection, nome: str) -> bool:
    cur = conn.execute("DELETE FROM mazzi WHERE nome = ?", (nome,))
    conn.commit()
    return cur.rowcount > 0


def salva_se_manca(conn: sqlite3.Connection, nome: str, mazzo: dict[str, int]) -> None:
    if leggi(conn, nome) is None:
        salva(conn, nome, mazzo, {})
