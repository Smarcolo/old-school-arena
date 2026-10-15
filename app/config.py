import os
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
# I file generati (database, cache) vanno in data/; OSA_DATI permette di spostarli (lo usano i test).
DATI = Path(os.environ.get("OSA_DATI", RADICE / "data"))
DB_CARTE = DATI / "carte.sqlite"
DB_REGOLE = DATI / "regole.sqlite"
CARTELLA_REGOLE = RADICE / "data" / "regole"
CARTELLA_IMMAGINI = DATI / "immagini"
CARTELLA_BULK = DATI / "bulk"
