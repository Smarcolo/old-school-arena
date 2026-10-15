"""Azioni che modificano lo stato. Validano, applicano e scrivono sempre nel registro eventi."""
from app.engine import mana
from app.engine.effetti import EFFETTI
from app.engine.eventi import Evento
from app.engine.stato import ORDINE_FASI, Carta, Fase, OggettoPila, Partita
from app.engine.validazione import (AzioneIllegale, fonti_di_mana, puo_giocare_terra, puo_lanciare,
                                    puo_passare, puo_tappare)
from app.engine.zone import Zona


def _log(partita: Partita, giocatore: str, tipo: str, descrizione: str, **dati) -> None:
    partita.registro.aggiungi(
        Evento(partita.turno, partita.fase.value, giocatore, tipo, descrizione, dati)
    )


def _verifica(motivo: str | None) -> None:
    if motivo:
        raise AzioneIllegale(motivo)


def trova_in_zona(partita: Partita, giocatore: str, zona: Zona, nome: str) -> Carta | None:
    """Trova per nome o id. Con più copie preferisce quelle stappate."""
    nome = nome.strip().lower()
    candidate = [c for c in partita.giocatore(giocatore)[zona] if c.nome.lower() == nome or c.id == nome]
    candidate.sort(key=lambda c: c.tappata)
    return candidate[0] if candidate else None


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


def _entra_in_campo(partita: Partita, giocatore: str, carta: Carta) -> None:
    carta.entrata_nel_turno = partita.turno
    carta.tappata = False
    partita.giocatore(giocatore)[Zona.CAMPO].append(carta)


def gioca_terra(partita: Partita, giocatore: str, carta: Carta) -> None:
    _verifica(puo_giocare_terra(partita, giocatore, carta))
    g = partita.giocatore(giocatore)
    g[Zona.MANO].remove(carta)
    _entra_in_campo(partita, giocatore, carta)
    g.terre_giocate_nel_turno += 1
    partita.passaggi = 0
    _log(partita, giocatore, "terra", f"{giocatore} gioca {carta.nome}", carta=carta.id)


def tappa(partita: Partita, giocatore: str, carta: Carta) -> None:
    """Tappa un permanente. Se ha un'abilità di mana, il mana va nella riserva (abilità di mana: niente pila)."""
    _verifica(puo_tappare(partita, giocatore, carta))
    carta.tappata = True
    colore = mana.mana_prodotto(carta)
    if colore:
        partita.giocatore(giocatore).riserva[colore] += 1
        _log(partita, giocatore, "mana", f"{giocatore} tappa {carta.nome} per {{{colore}}}", carta=carta.id)
    else:
        _log(partita, giocatore, "tappa", f"{giocatore} tappa {carta.nome}", carta=carta.id)


def lancia(partita: Partita, giocatore: str, carta: Carta) -> None:
    """Paga il costo (tappando da solo le fonti necessarie) e mette la magia in pila.
    Chi lancia mantiene la priorità."""
    _verifica(puo_lanciare(partita, giocatore, carta))
    g = partita.giocatore(giocatore)
    costo = mana.analizza_costo(carta.costo)
    for fonte in mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore), costo):
        tappa(partita, giocatore, fonte)
    g.riserva = mana.paga(g.riserva, costo)
    g[Zona.MANO].remove(carta)
    partita.pila.append(OggettoPila(carta, giocatore))
    partita.passaggi = 0
    _log(partita, giocatore, "lancia", f"{giocatore} lancia {carta.nome}", carta=carta.id)


def risolvi_pila(partita: Partita) -> None:
    oggetto = partita.pila.pop()
    carta, chi = oggetto.carta, oggetto.controllore
    if carta.is_permanente:
        _entra_in_campo(partita, chi, carta)
        _log(partita, chi, "risolve", f"{carta.nome} si risolve ed entra in campo", carta=carta.id)
    else:
        EFFETTI[carta.nome](partita, oggetto)
        partita.giocatore(carta.proprietario or chi)[Zona.CIMITERO].append(carta)
        _log(partita, chi, "risolve", f"{carta.nome} si risolve", carta=carta.id)
    partita.priorita = partita.attivo
    partita.passaggi = 0


def passa_priorita(partita: Partita, giocatore: str) -> None:
    """Quando entrambi passano di fila: si risolve la cima della pila, o se è vuota si va alla fase successiva."""
    _verifica(puo_passare(partita, giocatore))
    partita.passaggi += 1
    if partita.passaggi < 2:
        partita.priorita = 1 - partita.priorita
        return
    if partita.pila:
        risolvi_pila(partita)
    else:
        passa_fase(partita)


def modifica_vita(partita: Partita, giocatore: str, delta: int, motivo: str = "") -> None:
    g = partita.giocatore(giocatore)
    g.vita += delta
    _log(partita, giocatore, "vita", f"{giocatore} {delta:+d} vita ({g.vita}) {motivo}".strip())
    if g.vita <= 0 and not partita.vincitore:
        partita.vincitore = partita.avversario_di(giocatore).nome
        _log(partita, giocatore, "sconfitta", f"{giocatore} è a {g.vita} punti vita")


def svuota_riserve(partita: Partita) -> None:
    """93/94: a fine fase le riserve si svuotano e ogni mana inutilizzato fa perdere 1 vita (mana burn)."""
    for g in partita.giocatori:
        avanzato = sum(g.riserva.values())
        g.riserva = dict.fromkeys(g.riserva, 0)
        if avanzato:
            modifica_vita(partita, g.nome, -avanzato, "(mana burn)")


def passa_fase(partita: Partita) -> None:
    """Avanza di una fase; dopo la fase finale passa il turno all'avversario."""
    if partita.vincitore:
        raise AzioneIllegale("la partita è finita")
    if partita.pila:
        raise AzioneIllegale("non si cambia fase con la pila piena")
    svuota_riserve(partita)
    if partita.vincitore:
        return
    partita.priorita = partita.attivo
    partita.passaggi = 0
    i = ORDINE_FASI.index(partita.fase)
    if i + 1 < len(ORDINE_FASI):
        partita.fase = ORDINE_FASI[i + 1]
        _log(partita, partita.giocatore_attivo.nome, "fase", f"Fase: {partita.fase.value}")
        _automatismi_fase(partita)
        return
    # Nuovo turno
    partita.attivo = 1 - partita.attivo
    partita.priorita = partita.attivo
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
