"""Mazzi dalla top 8 degli ultimi tornei Old School su TCDecks (https://www.tcdecks.net).

Pagine usate: l'elenco dei tornei del formato (format.php?format=Old+School), la pagina del torneo
(deck.php?id=<torneo>) e quella del singolo mazzo (deck.php?id=<torneo>&iddeck=<mazzo>).
Il parser non dipende dai dettagli dell'HTML: cerca i link e, nel testo della pagina del mazzo, le righe
«4 Nome carta», con il cambio a sideboard dopo la parola «Sideboard». Le richieste sono poche e distanziate.

Uso: python -m app.cards.tcdecks   (oppure il pulsante nell'editor dei mazzi)
"""
import html as html_lib
import re
import sys
import time
from dataclasses import dataclass, field

import httpx

from app.cards import mazzi

BASE = "https://www.tcdecks.net/"
FORMATO = BASE + "format.php?format=Old+School"
HEADERS = {"User-Agent": "OldSchoolArena/0.1 (uso personale)"}
ORIGINE = "tcdecks"


@dataclass
class Torneo:
    id: str
    nome: str


@dataclass
class VoceMazzo:
    iddeck: str
    nome: str
    posizione: int
    giocatore: str = ""


@dataclass
class Resoconto:
    salvati: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)
    carte_sconosciute: set[str] = field(default_factory=set)


def _testo(frammento: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", frammento)).split())


def tornei_recenti(pagina: str) -> list[Torneo]:
    """Link ai tornei nell'ordine della pagina (TCDecks li elenca dal più recente)."""
    visti, tornei = set(), []
    for m in re.finditer(r'href="(?:https?://www\.tcdecks\.net/)?deck\.php\?id=(\d+)"[^>]*>(.*?)</a>', pagina, re.S | re.I):
        if m.group(1) not in visti and (nome := _testo(m.group(2))):
            visti.add(m.group(1))
            tornei.append(Torneo(m.group(1), nome))
    return tornei


def mazzi_del_torneo(pagina: str, id_torneo: str, quanti: int = 8) -> list[VoceMazzo]:
    """I primi `quanti` mazzi in classifica. Se la riga ha un numero di posizione lo usa, altrimenti l'ordine."""
    voci = []
    righe = re.findall(r"<tr[^>]*>(.*?)</tr>", pagina, re.S | re.I) or [pagina]
    for riga in righe:
        for m in re.finditer(rf'href="[^"]*deck\.php\?id={id_torneo}&(?:amp;)?iddeck=(\d+)"[^>]*>(.*?)</a>', riga, re.S | re.I):
            if any(v.iddeck == m.group(1) for v in voci):
                continue
            celle = [_testo(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", riga, re.S | re.I)]
            numeri = [int(n.group(1)) for c in celle if (n := re.match(r"^(\d{1,3})(?:st|nd|rd|th|°|º)?$", c))]
            altre = [c for c in celle if c and c != _testo(m.group(2)) and not re.match(r"^\d", c)]
            voci.append(VoceMazzo(m.group(1), _testo(m.group(2)) or f"Mazzo {m.group(1)}",
                                  numeri[0] if numeri else len(voci) + 1, altre[0] if altre else ""))
    voci.sort(key=lambda v: v.posizione)
    if len({v.posizione for v in voci}) != len(voci):  # pari merito (5-8, 5-8...): posti in ordine di tabella
        for i, v in enumerate(voci, 1):
            v.posizione = i
    return voci[:quanti]


def lista_dal_mazzo(pagina: str) -> tuple[dict[str, int], dict[str, int]]:
    """Righe «4 Nome carta» del testo della pagina; dopo «Sideboard» vanno in sideboard."""
    testo = re.sub(r"<(?:br|/tr|/td|/th|/div|/li|/p|/h\d)[^>]*>", "\n", pagina, flags=re.I)
    testo = html_lib.unescape(re.sub(r"<[^>]+>", " ", testo))
    mazzo: dict[str, int] = {}
    sideboard: dict[str, int] = {}
    destinazione = mazzo
    for riga in testo.splitlines():
        riga = " ".join(riga.split())
        if not riga:
            continue
        if re.match(r"^side ?board\b", riga, re.I):
            destinazione = sideboard
            continue
        m = re.match(r"^(\d{1,2})\s*x?\s+([A-ZÀ-Þ][\w ',.\-:!/]+?)$", riga)  # \w: anche Dandân, Ma'rûf
        if m and not re.search(r"\b(cards?|total|creatures?|spells?|lands?|artifacts?|sorcer(?:y|ies)|instants?|enchantments?)\b$",
                               m.group(2), re.I):
            nome = m.group(2).strip()
            destinazione[nome] = destinazione.get(nome, 0) + int(m.group(1))
    return mazzo, sideboard


def importa(conn, tornei: int = 3, per_torneo: int = 8, get=httpx.get, pausa: float = 1.0) -> Resoconto:
    """Scarica la top 8 degli ultimi `tornei` tornei e salva i mazzi (origine "tcdecks")."""
    res = Resoconto()

    def scarica(url: str) -> str:
        risposta = get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        risposta.raise_for_status()
        time.sleep(pausa)
        return risposta.text

    try:
        elenco = tornei_recenti(scarica(FORMATO))[:tornei]
    except Exception as e:
        res.errori.append(f"elenco dei tornei non raggiungibile: {e}")
        return res
    if not elenco:
        res.errori.append("nessun torneo trovato nella pagina del formato (la pagina potrebbe essere cambiata)")
    for torneo in elenco:
        try:
            voci = mazzi_del_torneo(scarica(f"{BASE}deck.php?id={torneo.id}"), torneo.id, per_torneo)
        except Exception as e:
            res.errori.append(f"{torneo.nome}: {e}")
            continue
        for voce in voci:
            try:
                mazzo, side = lista_dal_mazzo(scarica(f"{BASE}deck.php?id={torneo.id}&iddeck={voce.iddeck}"))
            except Exception as e:
                res.errori.append(f"{torneo.nome}, {voce.nome}: {e}")
                continue
            if not 40 <= sum(mazzo.values()) <= 100:
                res.errori.append(f"{torneo.nome}, {voce.nome}: lista non letta ({sum(mazzo.values())} carte)")
                continue
            analisi = mazzi.analizza(conn, mazzo, side)
            res.carte_sconosciute |= {p.removeprefix("carta sconosciuta: ") for p in analisi["problemi"]
                                      if p.startswith("carta sconosciuta")}
            nome = f"TC {voce.posizione}° {voce.nome} · {torneo.nome}"[:120]
            mazzi.salva(conn, nome, analisi["mazzo"], analisi["sideboard"], origine=ORIGINE,
                        info={"torneo": torneo.nome, "posizione": voce.posizione, "giocatore": voce.giocatore,
                              "url": f"{BASE}deck.php?id={torneo.id}&iddeck={voce.iddeck}"})
            res.salvati.append(nome)
    return res


@dataclass
class TopOtto:
    torneo: str
    mazzi: list[tuple[VoceMazzo, dict[str, int], dict[str, int]]] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)
    carte_sconosciute: set[str] = field(default_factory=set)


def carica_torneo(conn, nome: str = "", get=httpx.get, pausa: float = 1.0) -> TopOtto:
    """La top 8 di un torneo cercato per nome tra quelli della pagina del formato (vuoto = il più recente).
    I mazzi vengono anche salvati (origine "tcdecks"). Senza rete usa quelli già salvati di quel torneo."""
    def scarica(url: str) -> str:
        risposta = get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        risposta.raise_for_status()
        time.sleep(pausa)
        return risposta.text

    try:
        tornei = tornei_recenti(scarica(FORMATO))
    except Exception as e:
        return _top_otto_salvata(conn, nome, f"TCDecks non raggiungibile ({e})")
    cercato = nome.strip().lower()
    torneo = next((t for t in tornei if cercato in t.nome.lower()), None) if cercato else (tornei[0] if tornei else None)
    if torneo is None:
        return _top_otto_salvata(conn, nome, f"torneo «{nome}» non trovato tra gli ultimi su TCDecks")
    risultato = TopOtto(torneo.nome)
    try:
        voci = mazzi_del_torneo(scarica(f"{BASE}deck.php?id={torneo.id}"), torneo.id, 8)
    except Exception as e:
        risultato.errori.append(f"pagina del torneo non leggibile: {e}")
        return risultato
    for voce in voci:
        try:
            mazzo, side = lista_dal_mazzo(scarica(f"{BASE}deck.php?id={torneo.id}&iddeck={voce.iddeck}"))
        except Exception as e:
            risultato.errori.append(f"{voce.nome}: {e}")
            continue
        if not 40 <= sum(mazzo.values()) <= 100:
            risultato.errori.append(f"{voce.nome}: lista non letta ({sum(mazzo.values())} carte)")
            continue
        analisi = mazzi.analizza(conn, mazzo, side)
        risultato.carte_sconosciute |= {p.removeprefix("carta sconosciuta: ") for p in analisi["problemi"]
                                        if p.startswith("carta sconosciuta")}
        mazzi.salva(conn, f"TC {voce.posizione}° {voce.nome} · {torneo.nome}"[:120], mazzo, side, origine=ORIGINE,
                    info={"torneo": torneo.nome, "posizione": voce.posizione, "giocatore": voce.giocatore,
                          "url": f"{BASE}deck.php?id={torneo.id}&iddeck={voce.iddeck}"})
        risultato.mazzi.append((voce, mazzo, side))
    return risultato


def _top_otto_salvata(conn, nome: str, motivo: str) -> TopOtto:
    cercato = nome.strip().lower()
    salvati = [v for v in mazzi.elenco(conn, ORIGINE) if v["info"].get("posizione")
               and (not cercato or cercato in v["info"].get("torneo", "").lower())]
    if not salvati:
        return TopOtto(nome, errori=[motivo + "; e non ci sono mazzi salvati di quel torneo"])
    # il torneo con più posti salvati (meglio se completo), poi il più recente
    per_torneo: dict[str, list[dict]] = {}
    for v in salvati:
        per_torneo.setdefault(v["info"].get("torneo", ""), []).append(v)
    torneo = max(per_torneo, key=lambda t: (min(len({v["info"]["posizione"] for v in per_torneo[t]}), 7),
                                             max(v["aggiornato"] or "" for v in per_torneo[t])))
    risultato = TopOtto(torneo, errori=[motivo + f"; uso i mazzi già salvati di «{torneo}»"])
    for v in sorted((v for v in salvati if v["info"]["torneo"] == torneo), key=lambda v: v["info"]["posizione"])[:8]:
        mazzo, side = mazzi.leggi(conn, v["nome"])
        nome_mazzo = v["nome"].split(" · ")[0].split("° ", 1)[-1]
        risultato.mazzi.append((VoceMazzo("", nome_mazzo, v["info"]["posizione"], v["info"].get("giocatore", "")), mazzo, side))
    return risultato


def importa_url(conn, url: str, get=httpx.get) -> Resoconto:
    """Un solo mazzo, dall'indirizzo della sua pagina su TCDecks (deck.php?id=...&iddeck=...)."""
    res = Resoconto()
    m = re.search(r"deck\.php\?id=(\d+)&(?:amp;)?iddeck=(\d+)", url)
    if not m:
        res.errori.append("serve l'indirizzo di un mazzo: https://www.tcdecks.net/deck.php?id=...&iddeck=...")
        return res
    try:
        risposta = get(f"{BASE}deck.php?id={m.group(1)}&iddeck={m.group(2)}", headers=HEADERS, timeout=30,
                       follow_redirects=True)
        risposta.raise_for_status()
        pagina = risposta.text
    except Exception as e:
        res.errori.append(f"pagina non raggiungibile: {e}")
        return res
    mazzo, side = lista_dal_mazzo(pagina)
    if not 40 <= sum(mazzo.values()) <= 100:
        res.errori.append(f"lista non letta ({sum(mazzo.values())} carte)")
        return res
    titolo = re.search(r"<title>(.*?)</title>", pagina, re.S | re.I)
    nome = f"TC {(_testo(titolo.group(1)) if titolo else 'mazzo ' + m.group(2))}"[:120]
    analisi = mazzi.analizza(conn, mazzo, side)
    res.carte_sconosciute |= {p.removeprefix("carta sconosciuta: ") for p in analisi["problemi"]
                              if p.startswith("carta sconosciuta")}
    mazzi.salva(conn, nome, analisi["mazzo"], analisi["sideboard"], origine=ORIGINE,
                info={"torneo": "importato a mano", "posizione": 0, "giocatore": "", "url": url})
    res.salvati.append(nome)
    return res


def main() -> None:
    from app.cards import database
    with database.connetti() as conn:
        res = importa(conn)
    print(f"Salvati {len(res.salvati)} mazzi.", file=sys.stderr)
    for e in res.errori:
        print("Errore:", e, file=sys.stderr)
    if res.carte_sconosciute:
        print(f"{len(res.carte_sconosciute)} carte non sono nel database: lancia python -m app.cards.scryfall", file=sys.stderr)


if __name__ == "__main__":
    main()
