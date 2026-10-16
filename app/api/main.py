"""API FastAPI e server del frontend statico. Avvio: uvicorn app.api.main:app"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.cards import database, immagini, mazzi
from app.cards.regole_swedish import carica_regole
from app.engine import combattimento, mana
from app.engine.eventi import Evento
from app.engine.abilita import analizza_abilita
from app.engine.azioni import descrivi_bersaglio
from app.engine.stato import NOMI_COLORI, PAROLE_CHIAVE, PROTEZIONI_INGLESE, Partita, nuova_partita, parole_chiave_da_testo
from app.engine.validazione import tipo_bersaglio
from app.engine.zone import Zona
from app.judge.giudice import Giudice
from app.ai.sideboard import scegli_cambi
from app.incontro import Incontro, Lista
from app.regia import avanza, esegui_comando

UMANO = "Tu"
AI = "Avversaria"

# Mazzi di prova finché non c'è l'editor dei mazzi (non rispettano il limite di 4 copie).
MAZZO_VERDE = {"Forest": 17, "Llanowar Elves": 4, "Elvish Archers": 4, "Grizzly Bears": 2, "Timber Wolves": 2, "War Mammoth": 4,
               "Giant Spider": 3, "Giant Growth": 4}
MAZZO_ROSSO = {"Mountain": 17, "Mons's Goblin Raiders": 2, "Uthden Troll": 2, "Hurloon Minotaur": 4, "Gray Ogre": 4, "Ball Lightning": 2,
               "Shivan Dragon": 1,
               "Roc of Kher Ridges": 4, "Lightning Bolt": 4}

app = FastAPI(title="Old School Arena")
partite: dict[str, Incontro] = {}  # incontri al meglio di tre, per id
richieste_mazzo: dict[str, str] = {}  # id incontro -> nome del mazzo dell'avversaria
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


class CambiSideboard(BaseModel):
    entra: dict[str, int] = {}
    esce: dict[str, int] = {}


def _nome_abilita(k: str) -> str:
    if k in PAROLE_CHIAVE:
        return PAROLE_CHIAVE[k]
    if k == "protection from artifacts":
        return "protezione dagli artefatti"
    if k.startswith("protection from "):
        return f"protezione dal {NOMI_COLORI[PROTEZIONI_INGLESE[k.removeprefix('protection from ')]]}"
    return f"passa-{k[:-4]}"


def _abilita(c) -> list[str]:
    return sorted(_nome_abilita(k) for k in c.parole())


def _nome_incantata(p: Partita, c) -> str | None:
    trovato = p.trova_in_campo(c.attaccata_a) if c.attaccata_a else None
    return trovato[1].nome if trovato else None


def vista(p: Partita) -> dict:
    """Stato visibile al giocatore umano: la mano dell'avversaria resta nascosta."""
    def zona(g, z):
        return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "testo": c.testo, "costo": c.costo, "tappata": c.tappata,
                 "forza": c.forza_attuale if c.is_creatura else None,
                 "costituzione": c.costituzione_attuale if c.is_creatura else None,
                 "danni": c.danni, "bersaglio": tipo_bersaglio(c),
                 "incanta": _nome_incantata(p, c), "abilita": _abilita(c), "scudi": c.scudi_rigenerazione,
                 "attivabili": [{"testo": a.testo, "bersaglio": a.bersaglio} for a in analizza_abilita(c)],
                 "x": "X" in c.costo,
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
        "pila": [{"id": o.id, "nome": o.descrizione, "controllore": o.controllore, "x": o.x,
                  "bersaglio": descrivi_bersaglio(p, o.bersagli[0]) if o.bersagli else None} for o in p.pila],
        "vincitore": p.vincitore, "giocatori": giocatori,
        "combattimento": _vista_combattimento(p),
        "scelta": _vista_scelta(p),
        "mulligan": _vista_mulligan(p),
        "richiesta": ("mulligan" if p.mulligan and not p.mulligan[UMANO].finito
                      else "scelta" if p.scelta and p.scelta.giocatore == UMANO
                      else "attaccanti" if combattimento.deve_dichiarare_attaccanti(p, UMANO)
                      else "bloccanti" if combattimento.deve_dichiarare_bloccanti(p, UMANO) else None),
        "eventi": [e.descrizione for e in p.registro.ultimi(30)],
    }


def _vista_scelta(p: Partita) -> dict | None:
    s = p.scelta
    if s is None or s.giocatore != UMANO:
        return None
    if s.tipo == "cerca":
        return {"tipo": "cerca", "testo": s.testo, "fonte": s.dati["fonte"],
                "carte": [{"id": i, "nome": n} for i, n in s.dati["carte"].items()]}
    if s.tipo == "danni":
        return {"tipo": "danni", "testo": s.testo, "danni": s.dati["danni"], "fonte": s.dati["nome_fonte"],
                "candidate": [{"id": i, "nome": n} for i, n in s.dati["candidate"].items()]}
    return {"tipo": "paga", "testo": s.testo, "costo": s.costo, "carta": s.oggetto.carta.nome}


def _vista_mulligan(p: Partita) -> dict | None:
    if not p.mulligan or p.mulligan[UMANO].finito:
        return None
    s = p.mulligan[UMANO]
    return {"fatti": s.fatti, "tenuta": s.tenuta, "da_mettere_in_fondo": s.da_mettere_in_fondo}


def _vista_combattimento(p: Partita) -> dict | None:
    comb = p.combattimento
    if comb is None:
        return None
    return {"attaccanti": comb.attaccanti, "bloccanti": sorted(comb.bloccanti()), "blocchi": comb.blocchi,
            "bande": comb.bande,
            "attesa_bloccanti": comb.attesa_bloccanti}


@app.get("/api/salute")
def salute() -> dict:
    return {"ok": True, "partite": len(partite)}


def _carica_lista(nome: str) -> Lista:
    salvato = mazzi.leggi(conn_carte, nome)
    if salvato is None:
        raise HTTPException(404, f"mazzo non trovato: {nome}")
    analisi = mazzi.analizza(conn_carte, *salvato)
    if not analisi["giocabile"]:
        motivi = [p for p in analisi["problemi"] if p.startswith("carta sconosciuta")]
        motivi = motivi or [f"servono almeno {mazzi.MINIMO_PER_GIOCARE} carte"]
        raise HTTPException(400, f"il mazzo «{nome}» non si può usare: " + "; ".join(motivi))
    sideboard = {n: q for n, q in analisi["sideboard"].items() if database.cerca(conn_carte, n)}
    return Lista(analisi["mazzo"], sideboard)


def _carica_mazzo(nome: str) -> list:
    return database.mazzo_da_lista(conn_carte, _carica_lista(nome).mazzo)


def vista_incontro(inc: Incontro) -> dict:
    return {**vista(inc.partita), "id": inc.id, "incontro": {
        "numero": inc.numero, "vittorie": inc.vittorie, "esiti": inc.esiti, "lancio_moneta": inc.lancio_moneta,
        "vincitore": inc.vincitore, "prossima_possibile": bool(inc.partita.vincitore and not inc.vincitore),
        "mazzo_avversaria": richieste_mazzo.get(inc.id, ""),
        "liste": ({"mazzo": inc.liste[UMANO].mazzo, "sideboard": inc.liste[UMANO].sideboard}
                  if inc.partita.vincitore and not inc.vincitore else None)}}


@app.post("/api/partite")
def crea_partita(richiesta: RichiestaPartita | None = None) -> dict:
    """Crea un incontro al meglio di tre e ne avvia la prima partita."""
    richiesta = richiesta or RichiestaPartita()
    regole = carica_regole()
    inc = Incontro(
        [UMANO, AI],
        {UMANO: _carica_lista(richiesta.mazzo), AI: _carica_lista(richiesta.mazzo_avversaria)},
        lambda lista: database.mazzo_da_lista(conn_carte, lista),
        opzioni={"mana_burn": regole.mana_burn, "mulligan": regole.mulligan == "london"},
        scelte_manuali={UMANO})
    partite[inc.id] = inc
    richieste_mazzo[inc.id] = richiesta.mazzo_avversaria
    avanza(inc.partita, UMANO, AI)
    return vista_incontro(inc)


def _incontro(id_partita: str) -> Incontro:
    if id_partita not in partite:
        raise HTTPException(404, "partita non trovata")
    return partite[id_partita]


@app.get("/api/partite/{id_partita}")
def leggi_partita(id_partita: str) -> dict:
    return vista_incontro(_incontro(id_partita))


@app.post("/api/partite/{id_partita}/comando")
def comando(id_partita: str, richiesta: RichiestaComando) -> dict:
    inc = _incontro(id_partita)
    messaggio = esegui_comando(inc.partita, UMANO, AI, richiesta.testo, giudice)
    inc.registra_esito()
    return {"messaggio": messaggio, "partita": vista_incontro(inc)}


@app.post("/api/partite/{id_partita}/sideboard")
def cambia_sideboard(id_partita: str, cambi: CambiSideboard) -> dict:
    inc = _incontro(id_partita)
    try:
        inc.cambia_sideboard(UMANO, cambi.entra, cambi.esce)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return vista_incontro(inc)


def _sideboard_avversaria(inc: Incontro) -> None:
    lista = inc.liste[AI]
    nomi = set(lista.mazzo) | set(lista.sideboard) | set(inc.viste[UMANO])
    info = {n: c for n in nomi if (c := database.cerca(conn_carte, n))}
    entra, esce = scegli_cambi(lista.sideboard, lista.mazzo, inc.viste[UMANO], info)
    if entra:
        inc.cambia_sideboard(AI, entra, esce)
        inc.partita.registro.aggiungi(Evento(inc.partita.turno, "sideboard", AI, "sideboard",
                                             f"{AI} cambia {sum(entra.values())} carte con la sideboard"))


@app.post("/api/partite/{id_partita}/prossima")
def prossima_partita(id_partita: str) -> dict:
    inc = _incontro(id_partita)
    try:
        if inc.partita.vincitore and not inc.vincitore:
            _sideboard_avversaria(inc)
        inc.prossima()
    except ValueError as e:
        raise HTTPException(400, str(e))
    avanza(inc.partita, UMANO, AI)
    return vista_incontro(inc)


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
