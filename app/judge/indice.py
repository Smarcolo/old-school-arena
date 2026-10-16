"""Indice delle regole: ogni sezione '## ...' dei file .md in data/regole diventa un documento ricercabile (SQLite FTS5)."""
import re
import sqlite3
from pathlib import Path

from app.config import CARTELLA_REGOLE, DB_REGOLE


def _sezioni(testo: str, fonte: str) -> list[tuple[str, str, str]]:
    parti = re.split(r"^##\s+", testo, flags=re.MULTILINE)
    sezioni = []
    for parte in parti[1:]:
        titolo, _, corpo = parte.partition("\n")
        if corpo.strip():
            sezioni.append((fonte, titolo.strip(), corpo.strip()))
    return sezioni


def costruisci(cartella: Path = CARTELLA_REGOLE, db: Path | str = DB_REGOLE) -> sqlite3.Connection:
    conn = sqlite3.connect(db, check_same_thread=False)
    conn.execute("DROP TABLE IF EXISTS regole")
    conn.execute("CREATE VIRTUAL TABLE regole USING fts5(fonte, titolo, testo, tokenize='unicode61 remove_diacritics 2')")
    for file in sorted(Path(cartella).glob("*.md")):
        conn.executemany("INSERT INTO regole VALUES (?, ?, ?)", _sezioni(file.read_text(encoding="utf-8"), file.name))
    conn.commit()
    return conn


PAROLE_VUOTE = set("""
che chi cosa come quando dove perché perche quale quali quanto quanti quante una uno gli le lo la il del della dei
delle degli dal dalla dai dalle nel nella nei nelle sul sulla sui sulle con per tra fra non sono essere ha hanno
posso puoi può puo devo deve fare faccio fa mio mia miei mie tuo tua suo sua loro questo questa questi queste quello
quella anche ancora più piu poi già gia solo se sì via ogni mai sempre altro altra cosa succede funziona regola
the and for with what when does how can you your
""".split())


SINONIMI = {
    "volante": "volare", "volanti": "volare", "vola": "volare", "volatore": "volare", "volatori": "volare",
    "banda": "banding", "bande": "banding", "rigenerare": "rigenerazione", "rigenera": "rigenerazione",
    "proteggere": "protezione", "protetta": "protezione", "protetto": "protezione", "esilio": "rimosse",
    "librerie": "grimorio", "libreria": "grimorio", "mazzo": "mazzo", "malattia": "debolezza", "sickness": "debolezza",
    "ristretta": "ristrette", "bandita": "bandite", "aura": "aure", "incantare": "aure",
}


def _radice(parola: str) -> str:
    """Toglie le terminazioni italiane più comuni, così «creature» trova «creatura» (ricerca per prefisso)."""
    return parola[:-1] if len(parola) > 4 and parola[-1] in "aeiou" else parola


def cerca(conn: sqlite3.Connection, domanda: str, limite: int = 5) -> list[dict]:
    parole = [p for p in re.findall(r"\w{3,}", domanda.lower()) if p not in PAROLE_VUOTE]
    if not parole:
        return []
    query = " OR ".join(f'"{_radice(SINONIMI.get(p, p))}"*' for p in parole)
    righe = conn.execute(
        "SELECT fonte, titolo, snippet(regole, 2, '[', ']', ' … ', 30) FROM regole WHERE regole MATCH ? ORDER BY rank LIMIT ?",
        (query, limite),
    ).fetchall()
    return [{"fonte": f, "titolo": t, "estratto": s} for f, t, s in righe]
