"""Controlli di legalità delle azioni. Ogni funzione ritorna None se l'azione è legale, altrimenti il motivo."""
from app.engine import mana
from app.engine.effetti import EFFETTI, bersaglio_legale
from app.engine.stato import Carta, Fase, Partita
from app.engine.zone import Zona

FASI_PRINCIPALI = {Fase.PRINCIPALE_1, Fase.PRINCIPALE_2}
NOMI_BERSAGLI = {"qualsiasi": "una creatura o un giocatore", "creatura": "una creatura", "giocatore": "un giocatore"}


class AzioneIllegale(Exception):
    pass


def _priorita(partita: Partita, nome_giocatore: str) -> str | None:
    if partita.vincitore:
        return "la partita è finita"
    if partita.scelta:
        return f"prima {partita.scelta.giocatore} deve rispondere: {partita.scelta.testo}"
    if partita.giocatore_con_priorita.nome != nome_giocatore:
        return "non hai la priorità"
    return None


def _velocita_stregoneria(partita: Partita, nome_giocatore: str, cosa: str) -> str | None:
    if partita.giocatore_attivo.nome != nome_giocatore:
        return f"{cosa} solo nel tuo turno"
    if partita.fase not in FASI_PRINCIPALI:
        return f"{cosa} solo in una fase principale"
    if partita.pila:
        return "la pila deve essere vuota"
    return None


def puo_giocare_terra(partita: Partita, nome_giocatore: str, carta: Carta) -> str | None:
    g = partita.giocatore(nome_giocatore)
    if partita.vincitore:
        return "la partita è finita"
    if partita.scelta:
        return "c'è una scelta in sospeso"
    if g is not partita.giocatore_attivo:
        return "puoi giocare terre solo nel tuo turno"
    if motivo := _velocita_stregoneria(partita, nome_giocatore, "le terre si giocano"):
        return motivo
    if motivo := _priorita(partita, nome_giocatore):
        return motivo
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
    if partita.ha_debolezza_da_evocazione(carta):
        return f"{carta.nome} è entrata in questo turno e non può tappare"
    return None


def fonti_di_mana(partita: Partita, nome_giocatore: str) -> list[tuple[Carta, str]]:
    """Permanenti stappati che possono produrre mana adesso."""
    fonti = []
    for c in partita.giocatore(nome_giocatore)[Zona.CAMPO]:
        colore = mana.mana_prodotto(c)
        if colore and puo_tappare(partita, nome_giocatore, c) is None:
            fonti.append((c, colore))
    return fonti


def _motivo_bersaglio(partita: Partita, rif: str, fonte: Carta, altrimenti: str) -> str:
    from app.engine.stato import NOMI_COLORI
    oggetto = partita.risolvi_bersaglio(rif)
    if isinstance(oggetto, Carta) and oggetto.protetta_da(fonte):
        colori = ", ".join(NOMI_COLORI[c] for c in sorted(oggetto.protezioni & fonte.colori))
        return f"{oggetto.nome} ha protezione dal {colori}"
    return altrimenti


def tipo_bersaglio(carta: Carta) -> str | None:
    effetto = EFFETTI.get(carta.nome)
    return effetto.bersaglio if effetto else None


def puo_lanciare(partita: Partita, nome_giocatore: str, carta: Carta, bersagli: list[str] | None = None) -> str | None:
    g = partita.giocatore(nome_giocatore)
    if partita.combattimento and partita.combattimento.attesa_bloccanti:
        return "prima vanno dichiarati i bloccanti"
    if motivo := _priorita(partita, nome_giocatore):
        return motivo
    if carta not in g[Zona.MANO]:
        return f"{carta.nome} non è nella tua mano"
    if carta.is_terra:
        return f"{carta.nome} è una terra: si gioca, non si lancia"
    if not carta.is_istantaneo:
        if motivo := _velocita_stregoneria(partita, nome_giocatore, f"{carta.nome} si può lanciare"):
            return motivo
    if not carta.is_permanente and carta.nome not in EFFETTI:
        return f"l'effetto di {carta.nome} non è ancora implementato"
    if bersagli is not None:  # None = controlla solo se è lanciabile, senza ancora il bersaglio
        tipo = tipo_bersaglio(carta)
        if tipo and len(bersagli) != 1:
            return f"{carta.nome} ha bisogno di un bersaglio ({NOMI_BERSAGLI[tipo]})"
        if tipo and not bersaglio_legale(partita, tipo, bersagli[0], carta):
            return _motivo_bersaglio(partita, bersagli[0], carta, f"bersaglio non valido per {carta.nome}: serve {NOMI_BERSAGLI[tipo]}")
        if not tipo and bersagli:
            return f"{carta.nome} non ha bersagli"
    costo = mana.analizza_costo(carta.costo)
    if mana.piano_pagamento(g.riserva, fonti_di_mana(partita, nome_giocatore), costo) is None:
        return f"non hai abbastanza mana per {carta.nome} ({carta.costo})"
    return None


def puo_passare(partita: Partita, nome_giocatore: str) -> str | None:
    if partita.combattimento and partita.combattimento.attesa_bloccanti:
        return "prima vanno dichiarati i bloccanti (anche «nessun blocco»)"
    return _priorita(partita, nome_giocatore)


def puo_attivare(partita: Partita, nome_giocatore: str, carta: Carta, abilita, bersagli: list[str] | None = None) -> str | None:
    """abilita è un AbilitaAttivata di quella carta. bersagli None = controlla solo se è attivabile."""
    if partita.combattimento and partita.combattimento.attesa_bloccanti:
        return "prima vanno dichiarati i bloccanti"
    if motivo := _priorita(partita, nome_giocatore):
        return motivo
    if carta not in partita.giocatore(nome_giocatore)[Zona.CAMPO]:
        return f"{carta.nome} non è sul tuo campo di battaglia"
    if abilita.tappa and (motivo := puo_tappare(partita, nome_giocatore, carta)):
        return motivo
    fonti = [f for f in fonti_di_mana(partita, nome_giocatore) if not (abilita.tappa and f[0] is carta)]
    if mana.piano_pagamento(partita.giocatore(nome_giocatore).riserva, fonti, mana.analizza_costo(abilita.costo_mana)) is None:
        return f"non hai abbastanza mana per l'abilità di {carta.nome} ({abilita.costo_mana})"
    if bersagli is not None:
        if abilita.bersaglio and len(bersagli) != 1:
            return f"l'abilità di {carta.nome} ha bisogno di un bersaglio ({NOMI_BERSAGLI[abilita.bersaglio]})"
        if abilita.bersaglio and not bersaglio_legale(partita, abilita.bersaglio, bersagli[0], carta):
            return _motivo_bersaglio(partita, bersagli[0], carta, f"bersaglio non valido: serve {NOMI_BERSAGLI[abilita.bersaglio]}")
    return None
