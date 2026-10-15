"""Controlli di legalità delle azioni. Ogni funzione ritorna None se l'azione è legale, altrimenti il motivo."""
from app.engine.stato import Carta, Fase, Partita
from app.engine.zone import Zona

FASI_PRINCIPALI = {Fase.PRINCIPALE_1, Fase.PRINCIPALE_2}


class AzioneIllegale(Exception):
    pass


def puo_giocare_terra(partita: Partita, nome_giocatore: str, carta: Carta) -> str | None:
    g = partita.giocatore(nome_giocatore)
    if partita.vincitore:
        return "la partita è finita"
    if g is not partita.giocatore_attivo:
        return "puoi giocare terre solo nel tuo turno"
    if partita.fase not in FASI_PRINCIPALI:
        return "le terre si giocano solo in una fase principale"
    if partita.pila:
        return "la pila deve essere vuota"
    if not carta.is_terra:
        return f"{carta.nome} non è una terra"
    if carta not in g[Zona.MANO]:
        return f"{carta.nome} non è nella tua mano"
    if g.terre_giocate_nel_turno >= 1:
        return "hai già giocato una terra in questo turno"
    return None


def puo_tappare(partita: Partita, nome_giocatore: str, carta: Carta) -> str | None:
    g = partita.giocatore(nome_giocatore)
    if carta not in g[Zona.CAMPO]:
        return f"{carta.nome} non è sul tuo campo di battaglia"
    if carta.tappata:
        return f"{carta.nome} è già tappata"
    return None
