"""Import delle carte 93/94 dai bulk data di Scryfall (https://scryfall.com/docs/api/bulk-data).

Uso:  python -m app.cards.scryfall
Scarica 'default_cards' (pesante, ~centinaia di MB), tiene solo i set ammessi e salva nel DB locale.
"""
import json
import sys

import httpx

from app.cards import database
from app.cards.regole_swedish import carica_regole
from app.config import CARTELLA_BULK

HEADERS = {"User-Agent": "OldSchoolArena/0.1", "Accept": "application/json"}


def scarica_bulk() -> list[dict]:
    CARTELLA_BULK.mkdir(parents=True, exist_ok=True)
    destinazione = CARTELLA_BULK / "default_cards.json"
    if not destinazione.exists():
        indice = httpx.get("https://api.scryfall.com/bulk-data/default-cards", headers=HEADERS, timeout=30).json()
        with httpx.stream("GET", indice["download_uri"], headers=HEADERS, timeout=None) as r, open(destinazione, "wb") as f:
            for blocco in r.iter_bytes():
                f.write(blocco)
    return json.loads(destinazione.read_text(encoding="utf-8"))


def converti(carte_scryfall: list[dict], set_ammessi: set[str]) -> list[dict]:
    """Raggruppa le stampe per nome, tenendo solo i set ammessi. Il testo è quello Oracle attuale."""
    per_nome: dict[str, dict] = {}
    for c in carte_scryfall:
        if c.get("set") not in set_ammessi or "card_faces" in c:
            continue
        nome = c["name"]
        voce = per_nome.setdefault(nome, {
            "nome": nome,
            "tipo": c.get("type_line", ""),
            "costo": c.get("mana_cost", ""),
            "forza": _intero(c.get("power")),
            "costituzione": _intero(c.get("toughness")),
            "testo": c.get("oracle_text", ""),
            "set_codici": set(),
            "immagine_url": c.get("image_uris", {}).get("normal", ""),
        })
        voce["set_codici"].add(c["set"])
    for voce in per_nome.values():
        voce["set_codici"] = ",".join(sorted(voce["set_codici"]))
    return list(per_nome.values())


def _intero(valore: str | None) -> int | None:
    try:
        return int(valore) if valore is not None else None
    except ValueError:  # es. "*" per Tarmogoyf-like
        return None


def main() -> None:
    regole = carica_regole()
    righe = converti(scarica_bulk(), set(regole.set_ammessi))
    with database.connetti() as conn:
        n = database.salva(conn, righe)
    print(f"Importate {n} carte nei set {', '.join(regole.set_ammessi)}", file=sys.stderr)


if __name__ == "__main__":
    main()
