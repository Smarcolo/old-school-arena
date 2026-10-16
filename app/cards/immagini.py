"""Immagini delle carte: scaricate da Scryfall alla prima richiesta e tenute in cache in data/immagini/.

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
_falliti: set[str] = set()


def percorso_cache(nome: str, cartella: Path | None = None) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    return (cartella or CARTELLA_IMMAGINI) / f"{slug}.jpg"


def _url(conn: sqlite3.Connection, nome: str) -> str:
    riga = conn.execute("SELECT immagine_url FROM carte WHERE nome = ? COLLATE NOCASE", (nome,)).fetchone()
    if riga and riga["immagine_url"]:
        return riga["immagine_url"]
    return URL_SCRYFALL.format(nome=quote(nome))


def ottieni(conn: sqlite3.Connection, nome: str, scarica=httpx.get, cartella: Path | None = None) -> Path | None:
    """Percorso dell'immagine in cache, scaricandola se serve. None se non disponibile."""
    file = percorso_cache(nome, cartella)
    if file.exists():
        return file
    if nome.lower() in _falliti:
        return None
    try:
        risposta = scarica(_url(conn, nome), headers=HEADERS, follow_redirects=True, timeout=8)
        if risposta.status_code != 200 or not risposta.headers.get("content-type", "").startswith("image/"):
            raise ValueError(f"risposta {risposta.status_code}")
    except Exception:
        _falliti.add(nome.lower())
        return None
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(risposta.content)
    return file
