"""Aggiornamento automatico all'avvio (avvia.bat): se su GitHub c'è una versione più nuova, la scarica e la mette
al posto del codice vecchio, poi il gioco parte con le modifiche. Così l'icona sul desktop del PC del negozio apre
sempre l'ultima versione, senza zip da estrarre a mano.

- Non tocca mai i dati: data/ (mazzi, salvataggi, carte, immagini), l'ambiente .venv, i file .bat in uso.
- Senza rete, o con qualsiasi errore, il gioco parte com'è.
- Per spegnerlo: variabile d'ambiente OSA_NO_AGGIORNA=1.
"""
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

RAMO = "claude/old-school-arena-setup-o0x9qi"
REPO = "smarcolo/old-school-arena"
URL_VERSIONE = f"https://raw.githubusercontent.com/{REPO}/{RAMO}/app/versione.py"
URL_ZIP = f"https://github.com/{REPO}/archive/refs/heads/{RAMO}.zip"
RADICE = Path(__file__).resolve().parent.parent
# cartelle e file che non si sovrascrivono: dati di Marco, ambiente Python, sito per l'iPad, strumenti di sviluppo,
# e i .bat (Windows legge il .bat mentre lo esegue: cambiarlo a metà lo rompe)
DA_SALTARE = ("data/", ".venv/", "docs/", "dojo/", "strumenti/", ".github/", "ipad/.cache/", "sito/")


def numeri(versione: str) -> tuple:
    """«2026.11.24-4» -> (2026, 11, 24, 4): si confrontano come numeri (così -10 viene dopo -9)."""
    return tuple(int(n) for n in re.findall(r"\d+", versione))


def versione_locale() -> str:
    testo = (RADICE / "app" / "versione.py").read_text(encoding="utf-8")
    return re.search(r'VERSIONE = "([^"]+)"', testo).group(1)


def versione_in_rete(timeout: float = 10) -> str | None:
    with urllib.request.urlopen(URL_VERSIONE, timeout=timeout) as r:
        trovata = re.search(r'VERSIONE = "([^"]+)"', r.read().decode("utf-8"))
    return trovata.group(1) if trovata else None


def da_saltare(percorso: str) -> bool:
    return percorso.startswith(DA_SALTARE) or percorso.endswith(".bat") or percorso.endswith("/")


def installa_zip(dati: bytes, destinazione: Path = RADICE) -> list[str]:
    """Copia i file dello zip di GitHub (cartella principale «old-school-arena-<ramo>/») sopra il progetto, saltando
    dati e .bat. Ritorna i percorsi scritti."""
    scritti = []
    with zipfile.ZipFile(io.BytesIO(dati)) as z:
        for voce in z.infolist():
            parti = voce.filename.split("/", 1)
            if len(parti) < 2 or not parti[1] or da_saltare(parti[1]):
                continue
            dove = destinazione / parti[1]
            dove.parent.mkdir(parents=True, exist_ok=True)
            with z.open(voce) as sorgente, open(dove, "wb") as file:
                shutil.copyfileobj(sorgente, file)
            scritti.append(parti[1])
    return scritti


def aggiorna() -> bool:
    """True se ha installato una versione nuova."""
    if os.environ.get("OSA_NO_AGGIORNA"):
        return False
    locale = versione_locale()
    try:
        nuova = versione_in_rete()
    except Exception:
        print("Aggiornamento: nessuna rete, parto con la versione", locale)
        return False
    if not nuova or numeri(nuova) <= numeri(locale):
        print("Versione", locale, "(aggiornata)")
        return False
    print(f"Aggiornamento: scarico la versione {nuova} (questa era la {locale})...")
    try:
        requisiti_prima = (RADICE / "requirements.txt").read_bytes() if (RADICE / "requirements.txt").exists() else b""
        with urllib.request.urlopen(URL_ZIP, timeout=120) as r:
            dati = r.read()
        installa_zip(dati)
        if (RADICE / "requirements.txt").read_bytes() != requisiti_prima:
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", str(RADICE / "requirements.txt")], check=False)
    except Exception as e:
        print("Aggiornamento non riuscito, parto con la versione", locale, f"({e})")
        return False
    print("Aggiornato alla versione", nuova)
    return True


if __name__ == "__main__":
    aggiorna()
