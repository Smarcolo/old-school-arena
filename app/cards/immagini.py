"""Immagini delle carte: scaricate da Scryfall alla prima richiesta e tenute in cache in data/immagini/93/.

Sempre con la cornice originale del 1993: la stampa salvata dall'import (solo set 93/94) o, per le carte non
importate, la prima stampa con `frame:1993` trovata su Scryfall, preferendo i bordi neri (Beta, Alpha, Arabian
Nights...). Solo se anche questa ricerca fallisce si usa l'immagine predefinita di Scryfall (cornice moderna).
Senza rete l'app funziona lo stesso: le carte restano testuali. I nomi che non si riescono a scaricare
vengono ricordati fino al riavvio, per non riprovare a ogni passaggio del mouse.
"""
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

import httpx

from app.config import CARTELLA_IMMAGINI

HEADERS = {"User-Agent": "OldSchoolArena/0.1", "Accept": "image/*"}
URL_SCRYFALL = "https://api.scryfall.com/cards/named?format=image&version=normal&exact={nome}"
URL_RICERCA = "https://api.scryfall.com/cards/search?unique=prints&order=released&dir=asc&q={q}"
# Stampe preferite per l'immagine: prima i bordi neri, poi Unlimited e Summer Magic
STAMPE_PREFERITE = ["leb", "lea", "arn", "atq", "leg", "drk", "2ed", "psum"]
_falliti: set[str] = set()


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
    if nome.lower() in _falliti:
        return None
    try:
        risposta = scarica(_url(conn, nome, scarica), headers=HEADERS, follow_redirects=True, timeout=8)
        if risposta.status_code != 200 or not risposta.headers.get("content-type", "").startswith("image/"):
            raise ValueError(f"risposta {risposta.status_code}")
    except Exception:
        _falliti.add(nome.lower())
        return None
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(risposta.content)
    return file
