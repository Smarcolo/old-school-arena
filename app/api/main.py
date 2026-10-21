"""API FastAPI e server del frontend statico. Avvio: uvicorn app.api.main:app"""
import random
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.cards import database, immagini, mazzi, scryfall, tcdecks
from app.cards.regole_swedish import carica_regole
from app.engine import combattimento, mana
from app.engine.eventi import Evento
from app.engine.abilita import analizza_abilita
from app.engine.azioni import descrivi_bersaglio
from app.engine.stato import NOMI_COLORI, PAROLE_CHIAVE, PROTEZIONI_INGLESE, Fase, Partita
from app.engine.effetti import bersaglio_legale
from app.engine.validazione import puo_attivare, puo_giocare_terra, puo_lanciare, tipo_bersaglio
from app.engine.zone import Zona
from app.judge.giudice import Giudice
from app.ai.sideboard import scegli_cambi
from app.incontro import Incontro, Lista
from app.torneo import Partecipante, Torneo
from app.regia import avanza, esegui_comando
from app.salvataggio import Archivio

UMANO = "Tu"
AI = "Avversaria"

# Mazzi di prova finché non c'è l'editor dei mazzi (non rispettano il limite di 4 copie).
MAZZO_VERDE = {"Forest": 17, "Llanowar Elves": 4, "Elvish Archers": 4, "Grizzly Bears": 2, "Timber Wolves": 2, "War Mammoth": 4,
               "Giant Spider": 3, "Giant Growth": 4}
MAZZO_ROSSO = {"Mountain": 17, "Mons's Goblin Raiders": 2, "Uthden Troll": 2, "Hurloon Minotaur": 4, "Gray Ogre": 4, "Ball Lightning": 2,
               "Shivan Dragon": 1,
               "Roc of Kher Ridges": 4, "Lightning Bolt": 4}

_una_alla_volta = threading.Lock()


def _serializza(request: Request):
    """Le richieste all'API si servono una alla volta: incontri, tornei e la connessione SQLite sono condivisi e non
    reggono due richieste in parallelo (es. doppio clic su «Passa»). Le immagini no: hanno una connessione loro."""
    if request.url.path.startswith("/api/immagini/"):
        yield
        return
    with _una_alla_volta:
        yield


app = FastAPI(title="Old School Arena", dependencies=[Depends(_serializza)])

# Incontri e tornei si salvano dopo ogni mossa e si ricaricano all'avvio (app/salvataggio.py).
archivio = Archivio()
tornei: dict[str, Torneo] = archivio.carica_tutti("torneo")
partite: dict[str, Incontro] = archivio.carica_tutti("incontro")  # incontri al meglio di tre, per id
for _t in tornei.values():
    partite.update(_t.incontri)  # gli incontri di un torneo stanno dentro il torneo: stesso oggetto
costruttore = database.CostruttoreMazzi()
conn_carte = database.connetti()
database.carica_carte_base(conn_carte)  # idempotente: aggiorna le carte di prova se il JSON cambia
MAZZO_UMANO_PREDEFINITO = "Verde (prova)"
MAZZO_AI_PREDEFINITO = "Rosso (prova)"
mazzi.salva_se_manca(conn_carte, MAZZO_UMANO_PREDEFINITO, MAZZO_VERDE)
mazzi.salva_se_manca(conn_carte, MAZZO_AI_PREDEFINITO, MAZZO_ROSSO)
giudice = Giudice()


class RichiestaComando(BaseModel):
    testo: str


AUTOMATICO = "auto"  # l'avversaria sceglie un mazzo dalla top 8 dei tornei (TCDecks)


class RichiestaPartita(BaseModel):
    mazzo: str = MAZZO_UMANO_PREDEFINITO
    mazzo_avversaria: str = AUTOMATICO


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


def _bersagli_possibili(p: Partita) -> list[str]:
    rif = [f"giocatore:{g.nome}" for g in p.giocatori]
    rif += [f"carta:{c.id}" for g in p.giocatori for c in g[Zona.CAMPO]]
    rif += [f"pila:{o.id}" for o in p.pila]
    rif += [f"cimitero:{c.id}" for g in p.giocatori for c in g[Zona.CIMITERO]]
    return rif


def _giocabile(p: Partita, c, in_mano: bool) -> bool:
    """Per evidenziare nell'interfaccia cosa l'umano può usare adesso (con almeno un bersaglio valido)."""
    if p.vincitore:
        return False
    if not in_mano:
        return any(puo_attivare(p, UMANO, c, a) is None for a in analizza_abilita(c) if a.tipo != "mana")
    if c.is_terra:
        return puo_giocare_terra(p, UMANO, c) is None
    if puo_lanciare(p, UMANO, c) is not None:
        return False
    tipo = tipo_bersaglio(c)
    return tipo is None or any(bersaglio_legale(p, tipo, r, c) for r in _bersagli_possibili(p))


def _puo_attaccare_ora(p: Partita, c) -> bool:
    """Nella tua fase principale 1 (o quando si dichiarano gli attaccanti) questa creatura potrebbe attaccare."""
    if p.vincitore or p.pila or p.scelta or p.giocatore_attivo.nome != UMANO or p.giocatore_con_priorita.nome != UMANO:
        return False
    in_tempo = p.fase == Fase.PRINCIPALE_1 or combattimento.deve_dichiarare_attaccanti(p, UMANO)
    return c.is_creatura and in_tempo and combattimento.puo_attaccare(p, UMANO, c) is None


def vista(p: Partita) -> dict:
    """Stato visibile al giocatore umano: la mano dell'avversaria resta nascosta."""
    def zona(g, z):
        return [{"id": c.id, "nome": c.nome, "tipo": c.tipo, "testo": c.testo, "costo": c.costo, "tappata": c.tappata,
                 "forza": c.forza_attuale if c.is_creatura else None,
                 "costituzione": c.costituzione_attuale if c.is_creatura else None,
                 "danni": c.danni, "bersaglio": tipo_bersaglio(c),
                 "incanta": _nome_incantata(p, c), "abilita": _abilita(c), "scudi": c.scudi_rigenerazione,
                 "attivabili": [{"testo": a.testo, "bersaglio": a.bersaglio,
                                 "ora": g.nome == UMANO and z == Zona.CAMPO and puo_attivare(p, UMANO, c, a) is None}
                                for a in analizza_abilita(c)],
                 "puo_attaccare": g.nome == UMANO and z == Zona.CAMPO and _puo_attaccare_ora(p, c),
                 "x": "X" in c.costo,
                 "appena_entrata": p.ha_debolezza_da_evocazione(c),
                 "giocabile": g.nome == UMANO and z in (Zona.MANO, Zona.CAMPO) and _giocabile(p, c, z == Zona.MANO)}
                for c in g[z]]

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
    if s.tipo in ("cerca", "scegli"):
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
            "attesa_bloccanti": comb.attesa_bloccanti,
            "attaccanti_dichiarati": comb.attaccanti_dichiarati, "bloccanti_dichiarati": comb.bloccanti_dichiarati,
            "danni_inflitti": comb.danni_inflitti, "primo_passo_fatto": "primo" in comb.passi_fatti}


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


def vista_incontro(inc: Incontro) -> dict:
    return {**vista(inc.partita), "id": inc.id, "incontro": {
        "numero": inc.numero, "vittorie": inc.vittorie, "esiti": inc.esiti, "lancio_moneta": inc.lancio_moneta,
        "vincitore": inc.vincitore, "prossima_possibile": bool(inc.partita.vincitore and not inc.vincitore),
        "mazzo_avversaria": inc.avversaria,
        "torneo": inc.torneo or None,
        "liste": ({"mazzo": inc.liste[UMANO].mazzo, "sideboard": inc.liste[UMANO].sideboard}
                  if inc.partita.vincitore and not inc.vincitore else None)}}


@app.post("/api/partite")
def crea_partita(richiesta: RichiestaPartita | None = None) -> dict:
    """Crea un incontro al meglio di tre e ne avvia la prima partita."""
    richiesta = richiesta or RichiestaPartita()
    regole = carica_regole()
    mazzo_ai = richiesta.mazzo_avversaria
    if mazzo_ai == AUTOMATICO:
        mazzo_ai = mazzi.scegli_mazzo_avversaria(conn_carte, random.Random()) or MAZZO_AI_PREDEFINITO
    inc = Incontro(
        [UMANO, AI],
        {UMANO: _carica_lista(richiesta.mazzo), AI: _carica_lista(mazzo_ai)},
        costruttore,
        opzioni={"mana_burn": regole.mana_burn, "mulligan": regole.mulligan == "london"},
        scelte_manuali={UMANO}, avversaria=mazzo_ai)
    partite[inc.id] = inc
    inc.partita.registro.aggiungi(Evento(1, "inizio", AI, "mazzo", f"L'avversaria gioca «{mazzo_ai}»"))
    avanza(inc.partita, UMANO, AI)
    _salva(inc)
    return vista_incontro(inc)


def _salva(inc: Incontro) -> None:
    """Salva l'incontro, o il torneo che lo contiene."""
    if inc.torneo and inc.torneo in tornei:
        _salva_torneo(tornei[inc.torneo])
        return
    punteggio = "-".join(str(inc.vittorie[g]) for g in inc.giocatori)
    stato = f"vince {inc.vincitore}" if inc.vincitore else f"partita {inc.numero}"
    archivio.salva("incontro", inc.id, inc, f"Contro «{inc.avversaria}», {punteggio}, {stato}")


def _salva_torneo(t: Torneo) -> None:
    archivio.salva("torneo", t.id, t, f"Top 8 di {t.nome}: {t.fase}")


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
    if inc.vincitore and inc.torneo in tornei:
        tornei[inc.torneo].registra_incontro(inc)
    _salva(inc)
    return {"messaggio": messaggio, "partita": vista_incontro(inc)}


@app.post("/api/partite/{id_partita}/sideboard")
def cambia_sideboard(id_partita: str, cambi: CambiSideboard) -> dict:
    inc = _incontro(id_partita)
    try:
        inc.cambia_sideboard(UMANO, cambi.entra, cambi.esce)
    except ValueError as e:
        raise HTTPException(400, str(e))
    _salva(inc)
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
    _salva(inc)
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


@app.get("/api/mazzi/{nome:path}")
def leggi_mazzo(nome: str) -> dict:
    salvato = mazzi.leggi(conn_carte, nome)
    if salvato is None:
        raise HTTPException(404, "mazzo non trovato")
    return {"nome": nome, "testo": mazzi.formatta_testo(*salvato), **mazzi.analizza(conn_carte, *salvato)}


@app.put("/api/mazzi/{nome:path}")
def salva_mazzo(nome: str, corpo: TestoMazzo) -> dict:
    if not nome.strip():
        raise HTTPException(400, "il mazzo deve avere un nome")
    mazzo, sideboard, errori = mazzi.analizza_testo(corpo.testo)
    if errori:
        raise HTTPException(400, "righe non capite: " + "; ".join(errori))
    analisi = mazzi.analizza(conn_carte, mazzo, sideboard)
    mazzi.salva(conn_carte, nome.strip(), analisi["mazzo"], analisi["sideboard"])
    return {"nome": nome.strip(), "testo": mazzi.formatta_testo(analisi["mazzo"], analisi["sideboard"]), **analisi}


@app.delete("/api/mazzi/{nome:path}")
def elimina_mazzo(nome: str) -> dict:
    if not mazzi.elimina(conn_carte, nome):
        raise HTTPException(404, "mazzo non trovato")
    return {"ok": True}


@app.post("/api/carte/importa")
def importa_carte() -> dict:
    """Scarica da Scryfall le carte dei set ammessi (serve internet)."""
    try:
        n = scryfall.importa(conn_carte)
    except Exception as e:
        raise HTTPException(502, f"Scryfall non raggiungibile: {e}")
    return {"importate": n}


@app.post("/api/tcdecks/aggiorna")
def aggiorna_tcdecks(tornei: int = 3) -> dict:
    """Scarica la top 8 degli ultimi tornei Old School da TCDecks (serve internet; ci vuole circa un minuto)."""
    res = tcdecks.importa(conn_carte, tornei=min(tornei, 10))
    return {"salvati": res.salvati, "errori": res.errori, "carte_sconosciute": sorted(res.carte_sconosciute)}


class IndirizzoMazzo(BaseModel):
    url: str


@app.post("/api/tcdecks/mazzo")
def importa_mazzo_tcdecks(corpo: IndirizzoMazzo) -> dict:
    res = tcdecks.importa_url(conn_carte, corpo.url)
    return {"salvati": res.salvati, "errori": res.errori, "carte_sconosciute": sorted(res.carte_sconosciute)}


class RichiestaTorneo(BaseModel):
    torneo: str = ""  # nome (o parte del nome) del torneo su TCDecks; vuoto = il più recente
    mazzo: str = MAZZO_UMANO_PREDEFINITO  # il tuo mazzo
    posto: int = 8  # il piazzamento del torneo vero che prendi tu


TERRE_PER_COLORE = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}


def _lista_giocabile(mazzo: dict[str, int], sideboard: dict[str, int]) -> tuple[Lista, int]:
    """Carte sconosciute al database sostituite da terre base del colore più presente nel mazzo."""
    colori: dict[str, int] = {}
    noti: dict[str, int] = {}
    sostituite = 0
    for nome, q in mazzo.items():
        carta = database.cerca(conn_carte, nome)
        if carta is None:
            sostituite += q
            continue
        noti[carta.nome] = noti.get(carta.nome, 0) + q
        for c in carta.colori:
            colori[c] = colori.get(c, 0) + q
    if sostituite:
        terra = TERRE_PER_COLORE[max(colori, key=colori.get)] if colori else "Plains"
        noti[terra] = noti.get(terra, 0) + sostituite
    side = {n: q for n, q in sideboard.items() if database.cerca(conn_carte, n)}
    return Lista(noti, side), sostituite


@app.post("/api/tornei")
def crea_torneo(richiesta: RichiestaTorneo) -> dict:
    """Top 8 di un torneo vero da TCDecks con il tuo mazzo al posto di uno dei piazzati (serve internet la
    prima volta; poi bastano i mazzi salvati)."""
    if not 1 <= richiesta.posto <= 8:
        raise HTTPException(400, "il posto va da 1 a 8")
    tuo = _carica_lista(richiesta.mazzo)
    top = tcdecks.carica_torneo(conn_carte, richiesta.torneo)
    per_posto = {voce.posizione: (voce, mazzo, side) for voce, mazzo, side in top.mazzi}
    mancanti = [p for p in range(1, 9) if p != richiesta.posto and p not in per_posto]
    if mancanti:
        raise HTTPException(502, f"top 8 di «{top.torneo}» incompleta (mancano i posti {mancanti}). " + "; ".join(top.errori))
    partecipanti, avvisi = [], list(top.errori)
    for posto in range(1, 9):
        if posto == richiesta.posto:
            partecipanti.append(Partecipante(posto, richiesta.mazzo, "", tuo, umano=True))
            continue
        voce, mazzo, side = per_posto[posto]
        lista, sostituite = _lista_giocabile(mazzo, side)
        if sostituite:
            avvisi.append(f"{voce.nome}: {sostituite} carte sconosciute sostituite da terre base")
        partecipanti.append(Partecipante(posto, voce.nome, voce.giocatore, lista))
    regole = carica_regole()
    nomi = {n for p in partecipanti for n in list(p.lista.mazzo) + list(p.lista.sideboard)}
    t = Torneo(top.torneo, partecipanti, costruttore,
               opzioni={"mana_burn": regole.mana_burn, "mulligan": regole.mulligan == "london"},
               info_carte={n: c for n in nomi if (c := database.cerca(conn_carte, n))})
    tornei[t.id] = t
    _salva_torneo(t)
    return {**t.stato(), "avvisi": avvisi}


def _torneo(id_torneo: str) -> Torneo:
    if id_torneo not in tornei:
        raise HTTPException(404, "torneo non trovato")
    return tornei[id_torneo]


@app.get("/api/tornei/{id_torneo}")
def leggi_torneo(id_torneo: str) -> dict:
    return _torneo(id_torneo).stato()


@app.post("/api/tornei/{id_torneo}/gioca")
def gioca_incontro_torneo(id_torneo: str) -> dict:
    """Crea (o riprende) il tuo incontro del turno in corso e lo restituisce come una partita normale."""
    t = _torneo(id_torneo)
    try:
        inc = t.crea_incontro_umano({UMANO})
    except ValueError as e:
        raise HTTPException(400, str(e))
    if inc.id not in partite:
        sfida = t.sfida_umano()
        avversario = sfida.b if sfida.a.umano else sfida.a
        partite[inc.id] = inc
        inc.torneo = t.id
        inc.avversaria = avversario.etichetta
        inc.partita.registro.aggiungi(Evento(1, "inizio", AI, "mazzo",
                                             f"{t.fase} di {t.nome}: l'avversaria gioca {avversario.etichetta}"))
        avanza(inc.partita, UMANO, AI)
        _salva_torneo(t)
    return vista_incontro(inc)


@app.get("/api/salvataggi")
def elenco_salvataggi() -> list[dict]:
    """Incontri e tornei salvati, dal più recente; gli incontri di un torneo stanno nel torneo."""
    return [v for v in archivio.elenco() if v["id"] in partite or v["id"] in tornei]


@app.delete("/api/salvataggi/{id_salvataggio}")
def elimina_salvataggio(id_salvataggio: str) -> dict:
    if id_salvataggio in partite and partite[id_salvataggio].torneo:
        raise HTTPException(400, "questo incontro fa parte di un torneo: elimina il torneo")
    t = tornei.pop(id_salvataggio, None)
    if t is not None:
        for id_inc in t.incontri:
            partite.pop(id_inc, None)
    else:
        partite.pop(id_salvataggio, None)
    if not archivio.elimina(id_salvataggio):
        raise HTTPException(404, "salvataggio non trovato")
    return {"ok": True}


@app.get("/api/immagini/{nome}")
def immagine_carta(nome: str) -> FileResponse:
    conn = database.connetti()  # non quella condivisa: le immagini si servono in parallelo al resto
    try:
        file = immagini.ottieni(conn, nome)
    finally:
        conn.close()
    if file is None:
        raise HTTPException(404, "immagine non disponibile")
    return FileResponse(file, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


@app.get("/api/giudice")
def chiedi_al_giudice(q: str) -> dict:
    return giudice.rispondi(q)


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent.parent / "web", html=True), name="web")
