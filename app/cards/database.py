"""Database locale delle carte (SQLite). Si popola con carte_base.json o con l'import da Scryfall."""
import json
import sqlite3
from pathlib import Path

from app.config import DB_CARTE
from app.engine.stato import Carta

SCHEMA = """
CREATE TABLE IF NOT EXISTS carte (
    nome TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,
    costo TEXT DEFAULT '',
    forza INTEGER,
    costituzione INTEGER,
    testo TEXT DEFAULT '',
    set_codici TEXT DEFAULT '',     -- set 93/94 in cui è stata stampata, separati da virgola
    immagine_url TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS mazzi (
    nome TEXT PRIMARY KEY,
    mazzo TEXT NOT NULL,            -- JSON {nome carta: copie}
    sideboard TEXT NOT NULL DEFAULT '{}',
    aggiornato TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

CARTE_BASE = Path(__file__).with_name("carte_base.json")


def connetti(percorso: Path | str = DB_CARTE) -> sqlite3.Connection:
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(percorso, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    colonne = {r[1] for r in conn.execute("PRAGMA table_info(mazzi)")}
    if "origine" not in colonne:  # database creati prima dei mazzi da TCDecks
        conn.execute("ALTER TABLE mazzi ADD COLUMN origine TEXT NOT NULL DEFAULT ''")
        conn.execute("ALTER TABLE mazzi ADD COLUMN info TEXT NOT NULL DEFAULT '{}'")
    return conn


def salva(conn: sqlite3.Connection, righe: list[dict]) -> int:
    conn.executemany(
        """INSERT INTO carte (nome, tipo, costo, forza, costituzione, testo, set_codici, immagine_url)
           VALUES (:nome, :tipo, :costo, :forza, :costituzione, :testo, :set_codici, :immagine_url)
           ON CONFLICT(nome) DO UPDATE SET tipo=excluded.tipo, costo=excluded.costo,
             forza=excluded.forza, costituzione=excluded.costituzione, testo=excluded.testo,
             set_codici=excluded.set_codici, immagine_url=excluded.immagine_url""",
        [
            {"costo": "", "forza": None, "costituzione": None, "testo": "", "set_codici": "", "immagine_url": "", **r}
            for r in righe
        ],
    )
    conn.commit()
    return len(righe)


def carica_carte_base(conn: sqlite3.Connection) -> int:
    return salva(conn, json.loads(CARTE_BASE.read_text(encoding="utf-8")))


def cerca(conn: sqlite3.Connection, nome: str) -> Carta | None:
    r = conn.execute("SELECT * FROM carte WHERE nome = ? COLLATE NOCASE", (nome.strip(),)).fetchone()
    if not r:
        return None
    return Carta(nome=r["nome"], tipo=r["tipo"], costo=r["costo"], forza=r["forza"],
                 costituzione=r["costituzione"], testo=r["testo"])


def mazzo_da_lista(conn: sqlite3.Connection, lista: dict[str, int]) -> list[Carta]:
    """Trasforma {nome: copie} in una lista di istanze Carta. Solleva KeyError per carte sconosciute."""
    mazzo = []
    for nome, copie in lista.items():
        if cerca(conn, nome) is None:
            raise KeyError(f"carta sconosciuta: {nome}")
        mazzo.extend(cerca(conn, nome) for _ in range(copie))
    return mazzo


class CostruttoreMazzi:
    """Da {nome: copie} a carte nuove, leggendo il database delle carte. A differenza di una lambda si può salvare
    con pickle insieme all'incontro (vedi app/salvataggio.py); la connessione si riapre al bisogno."""

    _connessioni: dict[str, sqlite3.Connection] = {}

    def __init__(self, percorso: Path | str | None = None) -> None:
        self.percorso = str(percorso) if percorso else None  # None = il database predefinito (DB_CARTE)

    def __call__(self, lista: dict[str, int]) -> list[Carta]:
        percorso = self.percorso or str(DB_CARTE)
        if percorso not in self._connessioni:
            self._connessioni[percorso] = connetti(percorso)
        return mazzo_da_lista(self._connessioni[percorso], lista)


def cerca_per_testo(conn: sqlite3.Connection, testo: str, limite: int = 30) -> list[dict]:
    righe = conn.execute(
        "SELECT nome, tipo, costo, forza, costituzione, testo FROM carte WHERE nome LIKE ? "
        "ORDER BY nome LIKE ? DESC, nome LIMIT ?",
        (f"%{testo.strip()}%", f"{testo.strip()}%", limite),
    ).fetchall()
    return [dict(r) for r in righe]
