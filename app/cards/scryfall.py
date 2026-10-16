"""Import delle carte dei set ammessi dalla ricerca di Scryfall (https://scryfall.com/docs/api/cards/search).

Uso:  python -m app.cards.scryfall      (oppure il pulsante nell'editor dei mazzi)
Una ricerca per i soli set ammessi, con tutte le stampe: una ventina di pagine, con una pausa tra le richieste
come chiede Scryfall. Le carte importate sostituiscono quelle di prova con lo stesso nome.
"""
import sys
import time

import httpx

from app.cards import database
from app.cards.regole_swedish import carica_regole

HEADERS = {"User-Agent": "OldSchoolArena/0.1", "Accept": "application/json"}
URL = "https://api.scryfall.com/cards/search"


def scarica(set_ammessi: list[str], get=httpx.get, pausa: float = 0.1) -> list[dict]:
    query = " or ".join(f"e:{s}" for s in set_ammessi)
    params = {"q": f"({query})", "unique": "prints", "order": "name"}
    url, carte = URL, []
    while url:
        risposta = get(url, params=params, headers=HEADERS, timeout=30)
        risposta.raise_for_status()
        dati = risposta.json()
        carte.extend(dati.get("data", []))
        url, params = (dati.get("next_page"), None) if dati.get("has_more") else (None, None)
        time.sleep(pausa)
    return carte


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
    except ValueError:  # es. "*"
        return None


def importa(conn, get=httpx.get, pausa: float = 0.1) -> int:
    regole = carica_regole()
    righe = converti(scarica(regole.set_ammessi, get, pausa), set(regole.set_ammessi))
    return database.salva(conn, righe)


def main() -> None:
    with database.connetti() as conn:
        n = importa(conn)
    print(f"Importate {n} carte nei set {', '.join(carica_regole().set_ammessi)}", file=sys.stderr)


if __name__ == "__main__":
    main()
