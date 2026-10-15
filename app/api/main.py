"""API FastAPI e server del frontend statico. Avvio: uvicorn app.api.main:app"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.cards import database
from app.engine import mana
from app.engine.stato import Partita, nuova_partita
from app.engine.zone import Zona
from app.judge.giudice import Giudice
from app.regia import avanza, esegui_comando

UMANO = "Tu"
AI = "Avversaria"

# Mazzi di prova finché non c'è l'editor dei mazzi (non rispettano il limite di 4 copie).
MAZZO_VERDE = {"Forest": 20, "Llanowar Elves": 8, "Grizzly Bears": 12}
MAZZO_ROSSO = {"Mountain": 20, "Gray Ogre": 8, "Hill Giant": 6, "Lightning Bolt": 6}  # Bolt resta in mano finché non ha l'effetto

app = FastAPI(title="Old School Arena")
partite: dict[str, Partita] = {}
conn_carte = database.connetti()
database.carica_carte_base(conn_carte)  # idempotente: aggiorna le carte di prova se il JSON cambia
giudice = Giudice()


class RichiestaComando(BaseModel):
    testo: str


def vista(p: Partita) -> dict:
    """Stato visibile al giocatore umano: la mano dell'avversaria resta nascosta."""
    def zona(g, z):
        return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "costo": c.costo, "tappata": c.tappata,
                 "forza": c.forza, "costituzione": c.costituzione,
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
        "pila": [{"nome": o.carta.nome, "controllore": o.controllore} for o in p.pila],
        "vincitore": p.vincitore, "giocatori": giocatori,
        "eventi": [e.descrizione for e in p.registro.ultimi(30)],
    }


@app.get("/api/salute")
def salute() -> dict:
    return {"ok": True, "partite": len(partite)}


@app.post("/api/partite")
def crea_partita() -> dict:
    mazzi = {UMANO: database.mazzo_da_lista(conn_carte, MAZZO_VERDE),
             AI: database.mazzo_da_lista(conn_carte, MAZZO_ROSSO)}
    p = nuova_partita(mazzi)
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


@app.get("/api/giudice")
def chiedi_al_giudice(q: str) -> dict:
    return giudice.rispondi(q)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="web")
