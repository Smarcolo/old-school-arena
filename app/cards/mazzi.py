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
# Righe di intestazione delle pagine TCDecks copiate a mano: «Instants [13]», «Land [19]», «Deck Name: ...»,
# «Mr. Pox playing Millstone Dreams  Position: 2». Le sezioni dicono quante carte ha il mazzo: quelle in più,
# in fondo e senza sezione, sono la sideboard (TCDecks la mostra in una colonna a parte).
_SEZIONE = re.compile(r"^([A-Za-z][A-Za-z ]*?)\s*\[(\d+)\]$")
_INTESTAZIONE_TCDECKS = re.compile(r"^(deck name:|.+\bplaying\b.+|.*\bposition:\s*\d+)", re.IGNORECASE)


def analizza_testo(testo: str) -> tuple[dict[str, int], dict[str, int], list[str]]:
    """Legge righe come «4 Lightning Bolt», «4x Lightning Bolt» o «Lightning Bolt». Dopo una riga «Sideboard»
    (o con il prefisso «SB:») le carte vanno in sideboard. Ritorna (mazzo, sideboard, righe non capite)."""
    mazzo: Counter = Counter()
    sideboard: Counter = Counter()
    errori = []
    in_sideboard = segnata = False
    blocchi: list[Counter] = [Counter()]  # gruppi separati da righe vuote (export MTGO: la sideboard è l'ultimo)
    da_sezioni = 0  # carte annunciate dalle intestazioni «Tipo [N]» (formato TCDecks)
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga:
            if blocchi[-1]:
                blocchi.append(Counter())
            continue
        if m := _SEZIONE.match(riga):
            da_sezioni += int(m.group(2))
            continue
        if _INTESTAZIONE_TCDECKS.match(riga):
            continue
        intestazione = re.sub(r"^(?://|#)\s*|\s*\(\d+\)$|:$", "", riga).strip().lower()
        if intestazione in ("sideboard", "sb"):  # «Sideboard», «Sideboard:», «// Sideboard», «Sideboard (15)»
            in_sideboard = segnata = True
            continue
        if riga.startswith(("#", "//")):
            continue
        destinazione = sideboard if in_sideboard else mazzo
        if da_sezioni and not in_sideboard and sum(mazzo.values()) >= da_sezioni:
            destinazione = sideboard  # le sezioni del mazzo sono complete: il resto è la sideboard
        if riga.lower().startswith("sb:"):
            destinazione, riga = sideboard, riga[3:].strip()
        m = _RIGA.match(riga)
        if not m or not m.group(2):
            errori.append(riga)
            continue
        destinazione[m.group(2)] += int(m.group(1) or 1)
        if destinazione is mazzo:
            blocchi[-1][m.group(2)] += int(m.group(1) or 1)
        else:
            segnata = True
    blocchi = [b for b in blocchi if b]
    if not segnata and len(blocchi) > 1 and sum(blocchi[-1].values()) <= 15 and sum(mazzo.values()) - sum(blocchi[-1].values()) >= 40:
        sideboard, mazzo = blocchi[-1], mazzo - blocchi[-1]
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
        if (not riga or _PROMEMORIA.match(riga) or mana.riga_di_mana(riga) or mana.riga_da_terre_avversarie(riga)
                or riga_capita(carta, riga)
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
        "carte": {n: {"tipo": c.tipo, "costo": c.costo, "forza": c.forza, "costituzione": c.costituzione, "testo": c.testo}
                  for n in list(mazzo) + list(sideboard) if (c := database.cerca(conn, n))},  # per il deck builder
    }


def salva(conn: sqlite3.Connection, nome: str, mazzo: dict[str, int], sideboard: dict[str, int],
          origine: str = "", info: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO mazzi (nome, mazzo, sideboard, origine, info) VALUES (?, ?, ?, ?, ?) ON CONFLICT(nome) DO UPDATE "
        "SET mazzo=excluded.mazzo, sideboard=excluded.sideboard, origine=excluded.origine, info=excluded.info, "
        "aggiornato=CURRENT_TIMESTAMP",
        (nome, json.dumps(mazzo, ensure_ascii=False), json.dumps(sideboard, ensure_ascii=False), origine,
         json.dumps(info or {}, ensure_ascii=False)),
    )
    conn.commit()


def leggi(conn: sqlite3.Connection, nome: str) -> tuple[dict[str, int], dict[str, int]] | None:
    r = conn.execute("SELECT mazzo, sideboard FROM mazzi WHERE nome = ?", (nome,)).fetchone()
    return (json.loads(r["mazzo"]), json.loads(r["sideboard"])) if r else None


def elenco(conn: sqlite3.Connection, origine: str | None = None) -> list[dict]:
    righe = conn.execute("SELECT nome, mazzo, aggiornato, origine, info FROM mazzi ORDER BY origine, nome").fetchall()
    return [{"nome": r["nome"], "totale": sum(json.loads(r["mazzo"]).values()), "aggiornato": r["aggiornato"],
             "origine": r["origine"], "info": json.loads(r["info"])}
            for r in righe if origine is None or r["origine"] == origine]


def supporto(analisi: dict) -> float:
    """Quota delle carte (non terre) che il motore sa giocare per intero: 1.0 = tutte."""
    non_capite = sum(1 for a in analisi["avvisi"] if ":" in a and not a.startswith(("Liste", "Ci sono")))
    distinte = max(1, len(analisi["mazzo"]))
    return 1 - non_capite / distinte


def scegli_mazzo_avversaria(conn: sqlite3.Connection, rng, minimo: float = 0.8) -> str | None:
    """Un mazzo a caso tra quelli da TCDecks giocabili, preferendo quelli che il motore gioca meglio."""
    candidati = []
    for voce in elenco(conn, "tcdecks"):
        analisi = analizza(conn, *leggi(conn, voce["nome"]))
        if analisi["giocabile"]:
            candidati.append((supporto(analisi), voce["nome"]))
    if not candidati:
        return None
    buoni = [n for s, n in candidati if s >= minimo]
    return rng.choice(buoni) if buoni else max(candidati)[1]


def elimina(conn: sqlite3.Connection, nome: str) -> bool:
    cur = conn.execute("DELETE FROM mazzi WHERE nome = ?", (nome,))
    conn.commit()
    return cur.rowcount > 0


def salva_se_manca(conn: sqlite3.Connection, nome: str, mazzo: dict[str, int],
                   sideboard: dict[str, int] | None = None) -> None:
    if leggi(conn, nome) is None:
        salva(conn, nome, mazzo, sideboard or {})


INTESTAZIONE_TRASFERIMENTO = "OLD-SCHOOL-ARENA-MAZZI"


def esporta_tutti(conn: sqlite3.Connection) -> str:
    """Tutti i mazzi in un testo da copiare (PC → iPad e viceversa): intestazione e JSON compatto."""
    righe = conn.execute("SELECT nome, mazzo, sideboard, origine, info FROM mazzi ORDER BY origine, nome").fetchall()
    dati = [{"nome": r["nome"], "mazzo": json.loads(r["mazzo"]), "sideboard": json.loads(r["sideboard"]),
             "origine": r["origine"], "info": json.loads(r["info"])} for r in righe]
    return INTESTAZIONE_TRASFERIMENTO + "\n" + json.dumps(dati, ensure_ascii=False, separators=(",", ":"))


def importa_tutti(conn: sqlite3.Connection, testo: str) -> list[str]:
    """Salva i mazzi di un testo fatto da `esporta_tutti` (quelli con lo stesso nome si sovrascrivono)."""
    inizio = testo.find("[")
    if INTESTAZIONE_TRASFERIMENTO not in testo or inizio < 0:
        raise ValueError("non è un testo copiato con «Copia tutti i mazzi»")
    try:
        dati = json.loads(testo[inizio:testo.rfind("]") + 1])
    except json.JSONDecodeError:
        raise ValueError("il testo è incompleto o rovinato: copialo di nuovo tutto")
    for m in dati:
        salva(conn, m["nome"], m["mazzo"], m.get("sideboard", {}), m.get("origine", ""), m.get("info"))
    return [m["nome"] for m in dati]
