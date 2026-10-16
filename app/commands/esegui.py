"""Esegue un Comando sulla partita e ritorna un messaggio in italiano per l'interfaccia."""
from app.commands.parser import Comando
import re

from app.engine import azioni, combattimento, mana
from app.engine.abilita import analizza_abilita
from app.engine.stato import Partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

GIOCATORI_IO = {"me", "io", "me stesso", "tu"}
GIOCATORI_AVVERSARIO = {"avversaria", "avversario", "lei", "faccia", "lui"}


def trova_bersaglio(partita: Partita, giocatore: str, testo: str) -> str | None:
    """Da testo libero a riferimento: nome di un giocatore, «me»/«avversaria», nome o id di una creatura
    in campo (con più omonime preferisce quelle dell'avversario)."""
    t = testo.strip().lower()
    if t in GIOCATORI_IO:
        return f"giocatore:{giocatore}"
    if t in GIOCATORI_AVVERSARIO:
        return f"giocatore:{partita.avversario_di(giocatore).nome}"
    for g in partita.giocatori:
        if g.nome.lower() == t:
            return f"giocatore:{g.nome}"
    ordine = [partita.avversario_di(giocatore), partita.giocatore(giocatore)]
    for g in ordine:
        for c in g[Zona.CAMPO]:
            if c.id == t or c.nome.lower() == t:
                return f"carta:{c.id}"
    return None


AIUTO = ("Comandi: gioca <carta> (terre e magie), gioca <carta> su <bersaglio>, tappa <carta>, "
         "attiva <carta> [su <bersaglio>], passa, fine turno, "
         "attacca con <carte>|tutto, non attacco, blocca <attaccante> con <bloccante>; ..., nessun blocco, "
         "mano, mana, stato, pesca [n], vita <+/-n>, giudice <domanda>")
TUTTO = {"", "tutto", "tutte", "tutti", "con tutto", "con tutte"}


def _scegli(candidate, testo: str, gia_usate: set[str]):
    """Prima carta tra le candidate con quel nome o id, non ancora usata."""
    t = testo.strip().lower()
    return next((c for c in candidate if c.id not in gia_usate and (c.id == t or c.nome.lower() == t)), None)


def _attacca(partita: Partita, giocatore: str, argomento: str) -> str:
    possibili = combattimento.possibili_attaccanti(partita, giocatore)
    if argomento.strip() in TUTTO:
        scelti = possibili
    else:
        scelti, usati = [], set()
        for nome in re.split(r",|\s+e\s+", argomento):
            if not nome.strip():
                continue
            c = _scegli(possibili, nome, usati)
            if c is None:
                return f"«{nome.strip()}» non può attaccare."
            scelti.append(c)
            usati.add(c.id)
    combattimento.dichiara_attaccanti(partita, giocatore, scelti)
    return "Attacchi con " + (", ".join(c.nome for c in scelti) or "nessuna creatura") + "."


def _blocca(partita: Partita, giocatore: str, argomento: str) -> str:
    attaccanti = combattimento.attaccanti_in_campo(partita)
    possibili = combattimento.possibili_bloccanti(partita, giocatore)
    coppie, usati = [], set()
    for parte in re.split(r";|\s+poi\s+", argomento):
        if not parte.strip():
            continue
        if " con " not in parte:
            return "Scrivi «blocca <attaccante> con <tua creatura>»."
        nome_att, nome_blocc = parte.split(" con ", 1)
        attaccante = _scegli(attaccanti, nome_att, set())
        if attaccante is None:
            return f"«{nome_att.strip()}» non sta attaccando."
        bloccante = _scegli(possibili, nome_blocc, usati)
        if bloccante is None:
            return f"«{nome_blocc.strip()}» non può bloccare."
        coppie.append((bloccante, attaccante))
        usati.add(bloccante.id)
    combattimento.dichiara_bloccanti(partita, giocatore, coppie)
    return "Blocchi: " + "; ".join(f"{b.nome} blocca {a.nome}" for b, a in coppie) + "."


def esegui(partita: Partita, giocatore: str, cmd: Comando, giudice=None) -> str:
    try:
        match cmd.azione:
            case "aiuto":
                return AIUTO
            case "mano":
                mano = partita.giocatore(giocatore)[Zona.MANO]
                return "Mano: " + (", ".join(f"{c.nome} {c.costo}".strip() for c in mano) or "vuota")
            case "mana":
                return "Riserva di mana: " + mana.formatta(partita.giocatore(giocatore).riserva)
            case "stato":
                return " | ".join(f"{g.nome}: {g.vita} vita, {len(g[Zona.MANO])} in mano, "
                                  f"{len(g[Zona.GRIMORIO])} nel grimorio" for g in partita.giocatori)
            case "pesca":
                carte = azioni.pesca(partita, giocatore, cmd.numero or 1)
                return "Hai pescato: " + ", ".join(c.nome for c in carte)
            case "gioca" | "lancia":
                carta = azioni.trova_in_zona(partita, giocatore, Zona.MANO, cmd.argomento)
                if carta is None:
                    return f"Non hai «{cmd.argomento}» in mano."
                if carta.is_terra:
                    azioni.gioca_terra(partita, giocatore, carta)
                    return f"Hai giocato {carta.nome}."
                bersagli = []
                if cmd.bersaglio:
                    rif = trova_bersaglio(partita, giocatore, cmd.bersaglio)
                    if rif is None:
                        return f"Non trovo il bersaglio «{cmd.bersaglio}»."
                    bersagli = [rif]
                azioni.lancia(partita, giocatore, carta, bersagli)
                return f"Hai lanciato {carta.nome}: è in pila. Scrivi «passa» per farla risolvere."
            case "attiva":
                nome, indice = cmd.argomento, 0
                if m := re.match(r"^(.+?)\s+(\d)$", nome):
                    nome, indice = m.group(1), int(m.group(2)) - 1
                carta = azioni.trova_in_zona(partita, giocatore, Zona.CAMPO, nome)
                if carta is None:
                    return f"Non hai «{nome}» sul campo."
                abilita = analizza_abilita(carta)
                if not abilita:
                    return f"{carta.nome} non ha abilità attivabili che il motore conosca."
                if indice >= len(abilita):
                    return f"{carta.nome} ha solo {len(abilita)} abilità."
                bersagli = []
                if cmd.bersaglio:
                    rif = trova_bersaglio(partita, giocatore, cmd.bersaglio)
                    if rif is None:
                        return f"Non trovo il bersaglio «{cmd.bersaglio}»."
                    bersagli = [rif]
                azioni.attiva(partita, giocatore, carta, abilita[indice], bersagli)
                return f"Hai attivato l'abilità di {carta.nome}: è in pila."
            case "tappa":
                carta = azioni.trova_in_zona(partita, giocatore, Zona.CAMPO, cmd.argomento)
                if carta is None:
                    return f"Non hai «{cmd.argomento}» sul campo."
                azioni.tappa(partita, giocatore, carta)
                return f"Hai tappato {carta.nome}. Riserva: {mana.formatta(partita.giocatore(giocatore).riserva)}"
            case "vita":
                azioni.modifica_vita(partita, giocatore, cmd.numero, "(manuale)")
                return f"Vita: {partita.giocatore(giocatore).vita}"
            case "attacca":
                return _attacca(partita, giocatore, cmd.argomento)
            case "nonattacco":
                combattimento.dichiara_attaccanti(partita, giocatore, [])
                return "Non attacchi."
            case "blocca":
                return _blocca(partita, giocatore, cmd.argomento)
            case "nonblocco":
                combattimento.dichiara_bloccanti(partita, giocatore, [])
                return "Non blocchi."
            case "passa":
                if combattimento.deve_dichiarare_bloccanti(partita, giocatore):
                    combattimento.dichiara_bloccanti(partita, giocatore, [])
                    return "Non blocchi."
                azioni.passa_priorita(partita, giocatore)
                return "Passi."
            case "giudice":
                if giudice is None:
                    return "Il giudice non è disponibile."
                return giudice.rispondi(cmd.argomento)["risposta"]
            case _:
                return f"Non ho capito «{cmd.argomento}». {AIUTO}"
    except AzioneIllegale as e:
        return f"Mossa non valida: {e}."
