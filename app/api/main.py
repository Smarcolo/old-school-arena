"""API FastAPI e server del frontend statico. Avvio: uvicorn app.api.main:app"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.ai import avversaria
from app.cards import database
from app.commands.esegui import esegui
from app.commands.parser import analizza
from app.engine.stato import Partita, nuova_partita
from app.engine.zone import Zona
from app.judge.giudice import Giudice

UMANO = "Tu"
AI = "Avversaria"

# Mazzi di prova finché non c'è l'editor dei mazzi (non rispettano il limite di 4 copie).
MAZZO_VERDE = {"Forest": 20, "Llanowar Elves": 8, "Grizzly Bears": 12}
MAZZO_ROSSO = {"Mountain": 20, "Lightning Bolt": 20}

app = FastAPI(title="Old School Arena")
partite: dict[str, Partita] = {}
conn_carte = database.connetti()
if conn_carte.execute("SELECT COUNT(*) FROM carte").fetchone()[0] == 0:
    database.carica_carte_base(conn_carte)
giudice = Giudice()


class RichiestaComando(BaseModel):
    testo: str


def vista(p: Partita) -> dict:
    """Stato visibile al giocatore umano: la mano dell'avversaria resta nascosta."""
    def zona(g, z):
        return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "tappata": c.tappata} for c in g[z]]

    giocatori = []
    for g in p.giocatori:
        dati = {"nome": g.nome, "vita": g.vita, "grimorio": len(g[Zona.GRIMORIO]),
                "campo": zona(g, Zona.CAMPO), "cimitero": zona(g, Zona.CIMITERO),
                "mano": zona(g, Zona.MANO) if g.nome == UMANO else len(g[Zona.MANO])}
        giocatori.append(dati)
    return {
        "id": p.id, "turno": p.turno, "fase": p.fase.value, "attivo": p.giocatore_attivo.nome,
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
    messaggio = esegui(p, UMANO, analizza(richiesta.testo), giudice)
    if p.giocatore_attivo.nome == AI and not p.vincitore:
        avversaria.gioca_turno(p, AI)
    return {"messaggio": messaggio, "partita": vista(p)}


@app.get("/api/giudice")
def chiedi_al_giudice(q: str) -> dict:
    return giudice.rispondi(q)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="web")
