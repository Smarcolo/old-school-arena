"""Immagini delle carte: scaricate da Scryfall alla prima richiesta e tenute in cache in data/immagini/93/.

Sempre con la cornice originale del 1993: la stampa salvata dall'import (solo set 93/94) o, per le carte non
importate, la prima stampa con `frame:1993` trovata su Scryfall, preferendo i bordi neri (Beta, Alpha, Arabian
Nights...). Solo se anche questa ricerca fallisce si usa l'immagine predefinita di Scryfall (cornice moderna).
Senza rete l'app funziona lo stesso: le carte restano testuali. I nomi che non si riescono a scaricare
vengono ricordati fino al riavvio, per non riprovare a ogni passaggio del mouse.
"""
import re
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import CARTELLA_IMMAGINI

HEADERS = {"User-Agent": "OldSchoolArena/0.1", "Accept": "image/*"}
URL_SCRYFALL = "https://api.scryfall.com/cards/named?format=image&version=normal&exact={nome}"
URL_RICERCA = "https://api.scryfall.com/cards/search?unique=prints&order=released&dir=asc&q={q}"
# Stampe preferite per l'immagine: prima i bordi neri, poi Unlimited e Summer Magic
STAMPE_PREFERITE = ["leb", "lea", "arn", "atq", "leg", "drk", "2ed", "psum"]
_falliti: dict[str, float] = {}  # nome -> fino a quando non riprovare (inf = la carta non esiste su Scryfall)
RIPROVA_DOPO = 60  # secondi, per i fallimenti di rete o i limiti di Scryfall
PAUSA = 0.12  # Scryfall chiede al massimo ~10 richieste al secondo
_un_download_alla_volta = threading.Lock()
_ultima_richiesta = 0.0


def _educato(scarica):
    """Le richieste a Scryfall una alla volta, distanziate, e ripetute se rispondono 429 (troppe richieste):
    il tavolo chiede tutte le immagini insieme e senza questo metà finivano senza figura."""
    def richiesta(url, **kw):
        global _ultima_richiesta
        for tentativo in range(4):
            attesa = _ultima_richiesta + PAUSA - time.monotonic()
            if attesa > 0:
                time.sleep(attesa)
            _ultima_richiesta = time.monotonic()
            risposta = scarica(url, **kw)
            if risposta.status_code != 429:
                return risposta
            time.sleep(1 + tentativo)
        return risposta
    return richiesta


def percorso_cache(nome: str, cartella: Path | None = None) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return (cartella or CARTELLA_IMMAGINI / "93") / f"{slug}.jpg"


def ordine_stampa(codice_set: str) -> int:
    return STAMPE_PREFERITE.index(codice_set) if codice_set in STAMPE_PREFERITE else len(STAMPE_PREFERITE)


def _url_cornice_1993(nome: str, scarica) -> str | None:
    q = quote(f'!"{nome}" frame:1993')
    try:
        risposta = scarica(URL_RICERCA.format(q=q), headers={**HEADERS, "Accept": "application/json"},
                           follow_redirects=True, timeout=8)
        if risposta.status_code != 200:
            return None
        stampe = [c for c in risposta.json().get("data", []) if c.get("image_uris", {}).get("normal")]
    except Exception:
        return None
    if not stampe:
        return None
    return min(stampe, key=lambda c: ordine_stampa(c.get("set", "")))["image_uris"]["normal"]


def _url(conn: sqlite3.Connection, nome: str, scarica=httpx.get) -> str:
    riga = conn.execute("SELECT immagine_url FROM carte WHERE nome = ? COLLATE NOCASE", (nome,)).fetchone()
    if riga and riga["immagine_url"]:
        return riga["immagine_url"]
    return _url_cornice_1993(nome, scarica) or URL_SCRYFALL.format(nome=quote(nome))


def ottieni(conn: sqlite3.Connection, nome: str, scarica=httpx.get, cartella: Path | None = None) -> Path | None:
    """Percorso dell'immagine in cache, scaricandola se serve. None se non disponibile."""
    file = percorso_cache(nome, cartella)
    if file.exists():
        return file
    if _falliti.get(nome.lower(), 0) > time.monotonic():
        return None
    with _un_download_alla_volta:
        if file.exists():  # scaricata nel frattempo da un'altra richiesta
            return file
        educato = _educato(scarica)
        try:
            risposta = educato(_url(conn, nome, educato), headers=HEADERS, follow_redirects=True, timeout=8)
        except Exception:
            _falliti[nome.lower()] = time.monotonic() + RIPROVA_DOPO
            return None
        if risposta.status_code != 200 or not risposta.headers.get("content-type", "").startswith("image/"):
            _falliti[nome.lower()] = float("inf") if risposta.status_code == 404 else time.monotonic() + RIPROVA_DOPO
            return None
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(risposta.content)
        return file
