"""Azioni che modificano lo stato. Validano, applicano e scrivono sempre nel registro eventi."""
from app.engine.eventi import Evento
from app.engine.stato import ORDINE_FASI, Carta, Fase, Partita
from app.engine.validazione import AzioneIllegale, puo_giocare_terra, puo_tappare
from app.engine.zone import Zona


def _log(partita: Partita, giocatore: str, tipo: str, descrizione: str, **dati) -> None:
    partita.registro.aggiungi(
        Evento(partita.turno, partita.fase.value, giocatore, tipo, descrizione, dati)
    )


def trova_in_zona(partita: Partita, giocatore: str, zona: Zona, nome: str) -> Carta | None:
    nome = nome.strip().lower()
    for c in partita.giocatore(giocatore)[zona]:
        if c.nome.lower() == nome or c.id == nome:
            return c
    return None


def pesca(partita: Partita, giocatore: str, quante: int = 1) -> list[Carta]:
    g = partita.giocatore(giocatore)
    pescate = []
    for _ in range(quante):
        if not g[Zona.GRIMORIO]:
            # 93/94: chi deve pescare da un grimorio vuoto perde.
            partita.vincitore = partita.avversario_di(giocatore).nome
            _log(partita, giocatore, "sconfitta", f"{giocatore} non può pescare: grimorio vuoto")
            break
        carta = g[Zona.GRIMORIO].pop()
        g[Zona.MANO].append(carta)
        pescate.append(carta)
    _log(partita, giocatore, "pesca", f"{giocatore} pesca {len(pescate)} carta/e")
    return pescate


def gioca_terra(partita: Partita, giocatore: str, carta: Carta) -> None:
    motivo = puo_giocare_terra(partita, giocatore, carta)
    if motivo:
        raise AzioneIllegale(motivo)
    g = partita.giocatore(giocatore)
    g[Zona.MANO].remove(carta)
    g[Zona.CAMPO].append(carta)
    g.terre_giocate_nel_turno += 1
    _log(partita, giocatore, "terra", f"{giocatore} gioca {carta.nome}", carta=carta.id)


def tappa(partita: Partita, giocatore: str, carta: Carta) -> None:
    motivo = puo_tappare(partita, giocatore, carta)
    if motivo:
        raise AzioneIllegale(motivo)
    carta.tappata = True
    _log(partita, giocatore, "tappa", f"{giocatore} tappa {carta.nome}", carta=carta.id)


def modifica_vita(partita: Partita, giocatore: str, delta: int, motivo: str = "") -> None:
    g = partita.giocatore(giocatore)
    g.vita += delta
    _log(partita, giocatore, "vita", f"{giocatore} {delta:+d} vita ({g.vita}) {motivo}".strip())
    if g.vita <= 0 and not partita.vincitore:
        partita.vincitore = partita.avversario_di(giocatore).nome
        _log(partita, giocatore, "sconfitta", f"{giocatore} è a {g.vita} punti vita")


def passa_fase(partita: Partita) -> None:
    """Avanza di una fase; dopo la fase finale passa il turno all'avversario."""
    if partita.vincitore:
        raise AzioneIllegale("la partita è finita")
    i = ORDINE_FASI.index(partita.fase)
    if i + 1 < len(ORDINE_FASI):
        partita.fase = ORDINE_FASI[i + 1]
        _log(partita, partita.giocatore_attivo.nome, "fase", f"Fase: {partita.fase.value}")
        _automatismi_fase(partita)
        return
    # Nuovo turno
    partita.attivo = 1 - partita.attivo
    partita.turno += 1
    partita.fase = Fase.STAP
    g = partita.giocatore_attivo
    g.terre_giocate_nel_turno = 0
    _log(partita, g.nome, "turno", f"Turno {partita.turno} di {g.nome}")
    _automatismi_fase(partita)


def _automatismi_fase(partita: Partita) -> None:
    g = partita.giocatore_attivo
    if partita.fase == Fase.STAP:
        for c in g[Zona.CAMPO]:
            c.tappata = False
        _log(partita, g.nome, "stap", f"{g.nome} stappa i suoi permanenti")
    elif partita.fase == Fase.PESCATA:
        pesca(partita, g.nome)
