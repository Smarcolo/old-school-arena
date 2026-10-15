from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "data"
DB_CARTE = DATI / "carte.sqlite"
DB_REGOLE = DATI / "regole.sqlite"
CARTELLA_REGOLE = DATI / "regole"
CARTELLA_IMMAGINI = DATI / "immagini"
CARTELLA_BULK = DATI / "bulk"
