"""Salvataggio di incontri e tornei in SQLite (data/salvataggi.sqlite), così sopravvivono al riavvio del server.
Ogni oggetto si salva intero con pickle: è un file locale scritto solo da questa app. Gli incontri di un torneo
si salvano dentro il torneo (non a parte), così dopo il caricamento torneo e tavolo condividono lo stesso oggetto.
Un salvataggio che non si riesce più a leggere (codice cambiato troppo) viene saltato, non blocca l'avvio."""
import logging
import pickle
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import DB_SALVATAGGI

SCHEMA = """
CREATE TABLE IF NOT EXISTS salvataggi (
    id TEXT PRIMARY KEY,
    tipo TEXT NOT NULL,             -- 'incontro' o 'torneo'
    descrizione TEXT NOT NULL DEFAULT '',
    aggiornato TEXT NOT NULL,
    dati BLOB NOT NULL
);
"""

log = logging.getLogger(__name__)


class Archivio:
    def __init__(self, percorso: Path | str = DB_SALVATAGGI) -> None:
        Path(percorso).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(percorso, check_same_thread=False)
        self.conn.executescript(SCHEMA)

    def salva(self, tipo: str, id_: str, oggetto, descrizione: str = "") -> None:
        dati = pickle.dumps(oggetto, protocol=pickle.HIGHEST_PROTOCOL)
        adesso = datetime.now().isoformat(timespec="seconds")
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO salvataggi (id, tipo, descrizione, aggiornato, dati) "
                              "VALUES (?, ?, ?, ?, ?)", (id_, tipo, descrizione, adesso, dati))

    def carica_tutti(self, tipo: str) -> dict:
        oggetti = {}
        for id_, dati in self.conn.execute("SELECT id, dati FROM salvataggi WHERE tipo = ?", (tipo,)):
            try:
                oggetti[id_] = pickle.loads(dati)
            except Exception as e:  # salvataggio di una versione vecchia dell'app
                log.warning("salvataggio %s illeggibile, lo salto: %s", id_, e)
        return oggetti

    def elenco(self) -> list[dict]:
        righe = self.conn.execute("SELECT id, tipo, descrizione, aggiornato FROM salvataggi ORDER BY aggiornato DESC")
        return [{"id": r[0], "tipo": r[1], "descrizione": r[2], "aggiornato": r[3]} for r in righe]

    def elimina(self, id_: str) -> bool:
        with self.conn:
            return self.conn.execute("DELETE FROM salvataggi WHERE id = ?", (id_,)).rowcount > 0
