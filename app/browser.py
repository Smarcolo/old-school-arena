"""Versione per il browser (iPad, Pyodide): lo stesso programma senza server.

Nel browser non ci sono FastAPI, pydantic né la rete per httpx. Qui ci sono dei sostituti minimi, registrati in
`sys.modules` prima di importare `app.api.main`: così main.py resta identico e le sue funzioni (gli «endpoint»)
si chiamano direttamente. La pagina (web/ponte.js) intercetta le richieste a /api/... e le passa a `chiama`.

- FastAPI finta: i decoratori @app.get/post/put/delete registrano solo la funzione e il percorso; middleware,
  dipendenze e file statici non servono.
- BaseModel finta: campi dalle annotazioni, con i valori predefiniti.
- httpx finto: ogni richiesta fallisce come «rete non disponibile», così TCDecks e Scryfall (lato Python) cadono
  sulle strade di riserva che esistono già (mazzi salvati, messaggi d'errore). Le immagini e l'import delle carte
  da Scryfall li fa la pagina in JavaScript (ponte.js), che nel browser può raggiungere Scryfall.
"""
import copy
import inspect
import json
import re
import sys
import types
import typing
from urllib.parse import parse_qs, unquote, urlsplit


# --- Sostituti di fastapi, pydantic e httpx ---------------------------------------------------------

class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str = ""):
        super().__init__(detail)
        self.status_code, self.detail = status_code, detail


class FastAPI:
    def __init__(self, *a, **kw):
        self.percorsi: list[tuple[str, re.Pattern, list[str], typing.Callable]] = []

    def _registra(self, metodo: str, percorso: str):
        nomi = re.findall(r"\{(\w+)(?::path)?\}", percorso)
        schema = re.sub(r"\{\w+:path\}", "(.+)", percorso)
        schema = re.sub(r"\{\w+\}", "([^/]+)", schema)
        def decoratore(funzione):
            self.percorsi.append((metodo, re.compile(f"^{schema}$"), nomi, funzione))
            return funzione
        return decoratore

    def get(self, percorso, **kw):
        return self._registra("GET", percorso)

    def post(self, percorso, **kw):
        return self._registra("POST", percorso)

    def put(self, percorso, **kw):
        return self._registra("PUT", percorso)

    def delete(self, percorso, **kw):
        return self._registra("DELETE", percorso)

    def middleware(self, *a, **kw):
        return lambda funzione: funzione

    def mount(self, *a, **kw):
        pass


class _Qualsiasi:
    def __init__(self, *a, **kw):
        pass


class BaseModel:
    def __init__(self, **valori):
        for nome in typing.get_type_hints(type(self)):
            if nome in valori:
                setattr(self, nome, valori[nome])
            elif hasattr(type(self), nome):
                setattr(self, nome, copy.deepcopy(getattr(type(self), nome)))
            else:
                raise HTTPException(422, f"manca il campo «{nome}»")


def _httpx_get(*a, **kw):
    raise OSError("rete non disponibile in questa versione: dal browser il programma non può raggiungere il sito")


def installa_sostituti() -> None:
    fastapi = types.ModuleType("fastapi")
    fastapi.FastAPI, fastapi.HTTPException = FastAPI, HTTPException
    fastapi.Depends = lambda *a, **kw: None
    fastapi.Request = _Qualsiasi
    risposte = types.ModuleType("fastapi.responses")
    risposte.FileResponse = risposte.Response = _Qualsiasi
    statici = types.ModuleType("fastapi.staticfiles")
    statici.StaticFiles = _Qualsiasi
    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = BaseModel
    httpx = types.ModuleType("httpx")
    httpx.get = _httpx_get
    sys.modules.update({"fastapi": fastapi, "fastapi.responses": risposte, "fastapi.staticfiles": statici,
                        "pydantic": pydantic, "httpx": httpx})


# --- Chiamate dalla pagina ---------------------------------------------------------------------------

_main = None


def avvia():
    """Da chiamare una volta, dopo aver preparato /dati (salvataggi del browser): carica il programma."""
    global _main
    installa_sostituti()
    from app.api import main
    _main = main
    return main.VERSIONE


def _modello(annotazione):
    """La classe BaseModel di un parametro (anche dentro «X | None»), oppure None."""
    for tipo in (annotazione, *typing.get_args(annotazione)):
        if isinstance(tipo, type) and issubclass(tipo, BaseModel):
            return tipo
    return None


def _in_json(oggetto):
    if isinstance(oggetto, (set, frozenset, tuple)):
        return list(oggetto)
    return str(oggetto)


def chiama(metodo: str, indirizzo: str, corpo: str | None = None) -> str:
    """Esegue la richiesta come farebbe il server; risponde con JSON {"stato": codice, "dati": ...}."""
    parti = urlsplit(indirizzo)
    domanda = {k: v[-1] for k, v in parse_qs(parti.query).items()}
    for verbo, schema, nomi, funzione in _main.app.percorsi:
        if verbo != metodo or not (m := schema.match(parti.path)):
            continue
        argomenti = {n: unquote(v) for n, v in zip(nomi, m.groups())}
        firma = inspect.signature(funzione)
        suggerimenti = typing.get_type_hints(funzione)
        try:
            for nome, parametro in firma.parameters.items():
                if nome in argomenti:
                    continue
                tipo = suggerimenti.get(nome, str)
                if modello := _modello(tipo):
                    valori = json.loads(corpo) if corpo else None
                    if valori is None and parametro.default is not inspect.Parameter.empty:
                        argomenti[nome] = parametro.default
                    else:
                        argomenti[nome] = modello(**(valori or {}))
                elif nome in domanda:
                    argomenti[nome] = int(domanda[nome]) if tipo is int else domanda[nome]
            risultato = funzione(**argomenti)
            return json.dumps({"stato": 200, "dati": risultato}, default=_in_json)
        except HTTPException as e:
            return json.dumps({"stato": e.status_code, "dati": {"detail": e.detail}})
    return json.dumps({"stato": 404, "dati": {"detail": f"percorso sconosciuto: {metodo} {parti.path}"}})


def importa_carte_da_json(testo: str) -> int:
    """Le carte scaricate da Scryfall dalla pagina (ponte.js): stessa conversione dell'import del server."""
    from app.cards import database, scryfall
    from app.cards.regole_swedish import carica_regole
    righe = scryfall.converti(json.loads(testo), set(carica_regole().set_ammessi))
    return database.salva(_main.conn_carte, righe)


def carte_importate() -> int:
    """Quante carte vengono dall'import Scryfall (quelle di prova scritte a mano non hanno l'immagine)."""
    return _main.conn_carte.execute("SELECT COUNT(*) FROM carte WHERE immagine_url != ''").fetchone()[0]


def set_ammessi() -> str:
    from app.cards.regole_swedish import carica_regole
    return json.dumps(carica_regole().set_ammessi)


def indirizzi_immagini() -> str:
    """{nome in minuscolo: immagine Scryfall con la cornice del 1993} per le carte del database."""
    righe = _main.conn_carte.execute("SELECT nome, immagine_url FROM carte WHERE immagine_url != ''")
    return json.dumps({nome.lower(): url for nome, url in righe})
