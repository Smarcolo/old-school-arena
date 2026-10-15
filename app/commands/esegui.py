"""Esegue un Comando sulla partita e ritorna un messaggio in italiano per l'interfaccia."""
from app.commands.parser import Comando
from app.engine import azioni, mana
from app.engine.stato import Partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

AIUTO = ("Comandi: gioca <carta> (terre e magie), lancia <carta>, tappa <carta>, passa, fine turno, "
         "mano, mana, stato, pesca [n], vita <+/-n>, giudice <domanda>")


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
                azioni.lancia(partita, giocatore, carta)
                return f"Hai lanciato {carta.nome}: è in pila. Scrivi «passa» per farla risolvere."
            case "tappa":
                carta = azioni.trova_in_zona(partita, giocatore, Zona.CAMPO, cmd.argomento)
                if carta is None:
                    return f"Non hai «{cmd.argomento}» sul campo."
                azioni.tappa(partita, giocatore, carta)
                return f"Hai tappato {carta.nome}. Riserva: {mana.formatta(partita.giocatore(giocatore).riserva)}"
            case "vita":
                azioni.modifica_vita(partita, giocatore, cmd.numero, "(manuale)")
                return f"Vita: {partita.giocatore(giocatore).vita}"
            case "passa":
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
