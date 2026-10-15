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


def cerca(conn: sqlite3.Connection, domanda: str, limite: int = 5) -> list[dict]:
    parole = re.findall(r"\w{3,}", domanda.lower())
    if not parole:
        return []
    query = " OR ".join(f'"{p}"' for p in parole)
    righe = conn.execute(
        "SELECT fonte, titolo, snippet(regole, 2, '[', ']', ' … ', 30) FROM regole WHERE regole MATCH ? ORDER BY rank LIMIT ?",
        (query, limite),
    ).fetchall()
    return [{"fonte": f, "titolo": t, "estratto": s} for f, t, s in righe]
