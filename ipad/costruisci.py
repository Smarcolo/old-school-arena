"""Prepara la versione per il browser (iPad senza PC) nella cartella sito/, da pubblicare su GitHub Pages.

    python -m ipad.costruisci [cartella]

- pagine di app/web con ipad/ponte.js inserito dopo comune.js (intercetta /api/... e le immagini);
- app.zip: il codice Python, le carte di prova e i testi del giudice;
- pyodide/: Python per il browser (Pyodide 0.25.1, dal pacchetto npm ufficiale) più il pacchetto sqlite3,
  controllato con l'impronta sha256 scritta in pyodide-lock.json. Scaricati una volta in ipad/.cache/.
"""
import hashlib
import io
import json
import re
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CACHE = RADICE / "ipad" / ".cache"
PYODIDE = "https://registry.npmjs.org/pyodide/-/pyodide-0.25.1.tgz"
# Il pacchetto npm «pyodide» non contiene i moduli opzionali: sqlite3 viene da pyodide-files (stessa build).
PYODIDE_FILES = "https://registry.npmjs.org/pyodide-files/-/pyodide-files-0.25.3.tgz"
FILE_PYODIDE = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
SQLITE = "sqlite3-1.0.0.zip"


def _scarica(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    file = CACHE / url.rsplit("/", 1)[-1]
    if not file.exists():
        print(f"scarico {url}")
        with urllib.request.urlopen(url, timeout=120) as r:
            file.write_bytes(r.read())
    return file.read_bytes()


def _estrai(tgz: bytes, nomi: list[str]) -> dict[str, bytes]:
    trovati = {}
    with tarfile.open(fileobj=io.BytesIO(tgz)) as t:
        for m in t.getmembers():
            nome = m.name.rsplit("/", 1)[-1]
            if nome in nomi and m.isfile():
                trovati[nome] = t.extractfile(m).read()
    if mancanti := set(nomi) - set(trovati):
        raise SystemExit(f"mancano nel pacchetto: {', '.join(sorted(mancanti))}")
    return trovati


def _pyodide(destinazione: Path) -> None:
    file = _estrai(_scarica(PYODIDE), FILE_PYODIDE)
    file |= _estrai(_scarica(PYODIDE_FILES), [SQLITE])
    atteso = json.loads(file["pyodide-lock.json"])["packages"]["sqlite3"]["sha256"]
    if hashlib.sha256(file[SQLITE]).hexdigest() != atteso:
        raise SystemExit("sqlite3 non corrisponde a pyodide-lock.json")
    destinazione.mkdir(parents=True)
    for nome, dati in file.items():
        (destinazione / nome).write_bytes(dati)


def _codice(file: Path) -> None:
    with zipfile.ZipFile(file, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted((RADICE / "app").rglob("*")):
            if p.is_file() and p.suffix in {".py", ".json"} and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(RADICE))
        for p in sorted((RADICE / "data" / "regole").glob("*.md")):
            z.write(p, p.relative_to(RADICE))


def _pagine(destinazione: Path) -> None:
    web = RADICE / "app" / "web"
    for p in web.iterdir():
        if p.suffix == ".html":
            html = p.read_text(encoding="utf-8")
            html = html.replace('<script src="comune.js"></script>',
                                '<script src="comune.js"></script>\n<script src="ponte.js"></script>')
            html = html.replace('<meta name="viewport"',
                                '<meta name="apple-mobile-web-app-capable" content="yes">\n'
                                '<link rel="manifest" href="manifest.json">\n<meta name="viewport"', 1)
            if "ponte.js" not in html:
                raise SystemExit(f"{p.name}: non trovo dove inserire ponte.js")
            (destinazione / p.name).write_text(html, encoding="utf-8")
        elif p.suffix in {".js", ".css"}:
            shutil.copy(p, destinazione / p.name)
    shutil.copy(RADICE / "ipad" / "ponte.js", destinazione / "ponte.js")
    (destinazione / "manifest.json").write_text(json.dumps(
        {"name": "Old School Arena", "short_name": "Old School", "start_url": "index.html",
         "display": "standalone", "background_color": "#1d1a16", "theme_color": "#1d1a16"}), encoding="utf-8")
    (destinazione / ".nojekyll").write_text("")  # GitHub Pages: servire i file così come sono


# Scritti nella cartella pubblicata da altri (il lavoro automatico su GitHub): si tengono tra una costruzione e l'altra
DA_TENERE = ["tornei_tcdecks.json"]


def costruisci(destinazione: Path) -> None:
    tenuti = {n: (destinazione / n).read_bytes() for n in DA_TENERE if (destinazione / n).exists()}
    if destinazione.exists():
        shutil.rmtree(destinazione)
    _pyodide(destinazione / "pyodide")
    _pagine(destinazione)
    _codice(destinazione / "app.zip")
    for nome, dati in tenuti.items():
        (destinazione / nome).write_bytes(dati)
    versione = re.search(r'VERSIONE = "([^"]+)"', (RADICE / "app" / "versione.py").read_text()).group(1)
    print(f"versione {versione} pronta in {destinazione}")


if __name__ == "__main__":
    costruisci(Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "sito")
