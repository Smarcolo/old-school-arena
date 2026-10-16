"""API FastAPI e server del frontend statico. Avvio: uvicorn app.api.main:app"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.cards import database, immagini, mazzi
from app.engine import combattimento, mana
from app.engine.abilita import analizza_abilita
from app.engine.azioni import descrivi_bersaglio
from app.engine.stato import PAROLE_CHIAVE, Partita, nuova_partita, parole_chiave_da_testo
from app.engine.validazione import tipo_bersaglio
from app.engine.zone import Zona
from app.judge.giudice import Giudice
from app.regia import avanza, esegui_comando

UMANO = "Tu"
AI = "Avversaria"

# Mazzi di prova finché non c'è l'editor dei mazzi (non rispettano il limite di 4 copie).
MAZZO_VERDE = {"Forest": 17, "Llanowar Elves": 4, "Elvish Archers": 4, "Grizzly Bears": 4, "War Mammoth": 4,
               "Giant Spider": 3, "Giant Growth": 4}
MAZZO_ROSSO = {"Mountain": 17, "Mons's Goblin Raiders": 2, "Uthden Troll": 2, "Hurloon Minotaur": 4, "Gray Ogre": 4, "Ball Lightning": 2,
               "Shivan Dragon": 1,
               "Roc of Kher Ridges": 4, "Lightning Bolt": 4}

app = FastAPI(title="Old School Arena")
partite: dict[str, Partita] = {}
conn_carte = database.connetti()
database.carica_carte_base(conn_carte)  # idempotente: aggiorna le carte di prova se il JSON cambia
MAZZO_UMANO_PREDEFINITO = "Verde (prova)"
MAZZO_AI_PREDEFINITO = "Rosso (prova)"
mazzi.salva_se_manca(conn_carte, MAZZO_UMANO_PREDEFINITO, MAZZO_VERDE)
mazzi.salva_se_manca(conn_carte, MAZZO_AI_PREDEFINITO, MAZZO_ROSSO)
giudice = Giudice()


class RichiestaComando(BaseModel):
    testo: str


class RichiestaPartita(BaseModel):
    mazzo: str = MAZZO_UMANO_PREDEFINITO
    mazzo_avversaria: str = MAZZO_AI_PREDEFINITO


class TestoMazzo(BaseModel):
    testo: str


def _abilita(c) -> list[str]:
    return sorted(PAROLE_CHIAVE.get(k, f"passa-{k[:-4]}") for k in parole_chiave_da_testo(c.testo))


def vista(p: Partita) -> dict:
    """Stato visibile al giocatore umano: la mano dell'avversaria resta nascosta."""
    def zona(g, z):
        return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "costo": c.costo, "tappata": c.tappata,
                 "forza": c.forza_attuale if c.is_creatura else None,
                 "costituzione": c.costituzione_attuale if c.is_creatura else None,
                 "danni": c.danni, "bersaglio": tipo_bersaglio(c), "abilita": _abilita(c), "scudi": c.scudi_rigenerazione,
                 "attivabili": [{"testo": a.testo, "bersaglio": a.bersaglio} for a in analizza_abilita(c)],
                 "appena_entrata": p.ha_debolezza_da_evocazione(c)} for c in g[z]]

    giocatori = []
    for g in p.giocatori:
        dati = {"nome": g.nome, "vita": g.vita, "grimorio": len(g[Zona.GRIMORIO]),
                "riserva": mana.formatta(g.riserva),
                "campo": zona(g, Zona.CAMPO), "cimitero": zona(g, Zona.CIMITERO),
                "mano": zona(g, Zona.MANO) if g.nome == UMANO else len(g[Zona.MANO])}
        giocatori.append(dati)
    return {
        "id": p.id, "turno": p.turno, "fase": p.fase.value, "attivo": p.giocatore_attivo.nome,
        "priorita": p.giocatore_con_priorita.nome,
        "pila": [{"nome": o.descrizione, "controllore": o.controllore,
                  "bersaglio": descrivi_bersaglio(p, o.bersagli[0]) if o.bersagli else None} for o in p.pila],
        "vincitore": p.vincitore, "giocatori": giocatori,
        "combattimento": _vista_combattimento(p),
        "scelta": ({"testo": p.scelta.testo, "costo": p.scelta.costo, "carta": p.scelta.oggetto.carta.nome}
                   if p.scelta and p.scelta.giocatore == UMANO else None),
        "richiesta": ("scelta" if p.scelta and p.scelta.giocatore == UMANO
                      else "attaccanti" if combattimento.deve_dichiarare_attaccanti(p, UMANO)
                      else "bloccanti" if combattimento.deve_dichiarare_bloccanti(p, UMANO) else None),
        "eventi": [e.descrizione for e in p.registro.ultimi(30)],
    }


def _vista_combattimento(p: Partita) -> dict | None:
    comb = p.combattimento
    if comb is None:
        return None
    return {"attaccanti": comb.attaccanti, "bloccanti": sorted(comb.bloccanti()), "blocchi": comb.blocchi,
            "attesa_bloccanti": comb.attesa_bloccanti}


@app.get("/api/salute")
def salute() -> dict:
    return {"ok": True, "partite": len(partite)}


def _carica_mazzo(nome: str) -> list:
    salvato = mazzi.leggi(conn_carte, nome)
    if salvato is None:
        raise HTTPException(404, f"mazzo non trovato: {nome}")
    analisi = mazzi.analizza(conn_carte, *salvato)
    if not analisi["giocabile"]:
        motivi = [p for p in analisi["problemi"] if p.startswith("carta sconosciuta")]
        motivi = motivi or [f"servono almeno {mazzi.MINIMO_PER_GIOCARE} carte"]
        raise HTTPException(400, f"il mazzo «{nome}» non si può usare: " + "; ".join(motivi))
    return database.mazzo_da_lista(conn_carte, analisi["mazzo"])


@app.post("/api/partite")
def crea_partita(richiesta: RichiestaPartita | None = None) -> dict:
    richiesta = richiesta or RichiestaPartita()
    p = nuova_partita({UMANO: _carica_mazzo(richiesta.mazzo), AI: _carica_mazzo(richiesta.mazzo_avversaria)})
    partite[p.id] = p
    avanza(p, UMANO, AI)
    return vista(p)


def _partita(id_partita: str) -> Partita:
    if id_partita not in partite:
        raise HTTPException(404, "partita non trovata")
    return partite[id_partita]


@app.get("/api/partite/{id_partita}")
def leggi_partita(id_partita: str) -> dict:
    return vista(_partita(id_partita))


@app.post("/api/partite/{id_partita}/comando")
def comando(id_partita: str, richiesta: RichiestaComando) -> dict:
    p = _partita(id_partita)
    messaggio = esegui_comando(p, UMANO, AI, richiesta.testo, giudice)
    return {"messaggio": messaggio, "partita": vista(p)}


@app.get("/api/carte")
def cerca_carte(q: str = "", limite: int = 30) -> list[dict]:
    return database.cerca_per_testo(conn_carte, q, min(limite, 100))


@app.get("/api/mazzi")
def elenco_mazzi() -> list[dict]:
    return mazzi.elenco(conn_carte)


@app.post("/api/mazzi/analizza")
def analizza_mazzo(corpo: TestoMazzo) -> dict:
    mazzo, sideboard, errori = mazzi.analizza_testo(corpo.testo)
    return {**mazzi.analizza(conn_carte, mazzo, sideboard), "righe_non_capite": errori}


@app.get("/api/mazzi/{nome}")
def leggi_mazzo(nome: str) -> dict:
    salvato = mazzi.leggi(conn_carte, nome)
    if salvato is None:
        raise HTTPException(404, "mazzo non trovato")
    return {"nome": nome, "testo": mazzi.formatta_testo(*salvato), **mazzi.analizza(conn_carte, *salvato)}


@app.put("/api/mazzi/{nome}")
def salva_mazzo(nome: str, corpo: TestoMazzo) -> dict:
    if not nome.strip():
        raise HTTPException(400, "il mazzo deve avere un nome")
    mazzo, sideboard, errori = mazzi.analizza_testo(corpo.testo)
    if errori:
        raise HTTPException(400, "righe non capite: " + "; ".join(errori))
    analisi = mazzi.analizza(conn_carte, mazzo, sideboard)
    mazzi.salva(conn_carte, nome.strip(), analisi["mazzo"], analisi["sideboard"])
    return {"nome": nome.strip(), "testo": mazzi.formatta_testo(analisi["mazzo"], analisi["sideboard"]), **analisi}


@app.delete("/api/mazzi/{nome}")
def elimina_mazzo(nome: str) -> dict:
    if not mazzi.elimina(conn_carte, nome):
        raise HTTPException(404, "mazzo non trovato")
    return {"ok": True}


@app.get("/api/immagini/{nome}")
def immagine_carta(nome: str) -> FileResponse:
    file = immagini.ottieni(conn_carte, nome)
    if file is None:
        raise HTTPException(404, "immagine non disponibile")
    return FileResponse(file, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


@app.get("/api/giudice")
def chiedi_al_giudice(q: str) -> dict:
    return giudice.rispondi(q)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="web")
