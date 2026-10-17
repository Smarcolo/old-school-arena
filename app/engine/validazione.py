"""Controlli di legalità delle azioni. Ogni funzione ritorna None se l'azione è legale, altrimenti il motivo."""
from app.engine import mana
from app.engine.effetti import EFFETTI, bersaglio_legale
from app.engine.stato import Carta, Fase, Partita
from app.engine.zone import Zona

FASI_PRINCIPALI = {Fase.PRINCIPALE_1, Fase.PRINCIPALE_2}


class _NomiBersagli(dict):
    def __missing__(self, tipo):
        from app.engine.effetti import nome_tipo
        return nome_tipo(tipo)


NOMI_BERSAGLI = _NomiBersagli()


class AzioneIllegale(Exception):
    pass


def _mulligan_in_corso(partita: Partita) -> bool:
    return bool(partita.mulligan) and not all(s.finito for s in partita.mulligan.values())


def _priorita(partita: Partita, nome_giocatore: str) -> str | None:
    if partita.vincitore:
        return "la partita è finita"
    if partita.scelta:
        return f"prima {partita.scelta.giocatore} deve rispondere: {partita.scelta.testo}"
    if _mulligan_in_corso(partita):
        return "prima finite i mulligan"
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
    if _mulligan_in_corso(partita):
        return "prima finite i mulligan"
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
    # il mana si produce quando hai la priorità o quando devi pagare una scelta tua («paga»)
    if not (partita.scelta and partita.scelta.giocatore == nome_giocatore and not partita.vincitore):
        if motivo := _priorita(partita, nome_giocatore):
            return motivo
    if carta not in g[Zona.CAMPO]:
        return f"{carta.nome} non è sul tuo campo di battaglia"
    if carta.tappata:
        return f"{carta.nome} è già tappata"
    if partita.ha_debolezza_da_evocazione(carta):
        return f"{carta.nome} è entrata in questo turno e non può tappare"
    return None


def fonti_di_mana(partita: Partita, nome_giocatore: str, esclusa: Carta | None = None) -> list:
    """Fonti di mana (mana.FonteMana) su permanenti stappati che possono produrre mana adesso."""
    fonti = []
    for c in partita.giocatore(nome_giocatore)[Zona.CAMPO]:
        fonte = mana.mana_prodotto(c)
        if fonte and c is not esclusa and puo_tappare(partita, nome_giocatore, c) is None:
            fonti.append(fonte)
    return fonti


def _motivo_bersaglio(partita: Partita, rif: str, fonte: Carta, altrimenti: str) -> str:
    from app.engine.stato import NOMI_COLORI
    oggetto = partita.risolvi_bersaglio(rif)
    if isinstance(oggetto, Carta) and oggetto.protetta_da(fonte):
        colori = ", ".join(NOMI_COLORI[c] for c in sorted(oggetto.protezioni & fonte.caratteristiche_protezione))
        return f"{oggetto.nome} ha protezione {'dagli' if colori == 'artefatti' else 'dal'} {colori}"
    return altrimenti


def tipo_bersaglio(carta: Carta) -> str | None:
    from app.engine.statici import is_aura_creatura
    if is_aura_creatura(carta):
        return "creatura"
    effetto = EFFETTI.get(carta.nome)
    return effetto.bersaglio if effetto else None


def puo_lanciare(partita: Partita, nome_giocatore: str, carta: Carta, bersagli: list[str] | None = None,
                 x: int = 0) -> str | None:
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
    if carta.is_aura and tipo_bersaglio(carta) is None:
        return f"{carta.nome}: questo tipo di aura non è ancora gestito"
    if bersagli is not None:  # None = controlla solo se è lanciabile, senza ancora il bersaglio
        tipo = tipo_bersaglio(carta)
        massimo = max_bersagli(carta)
        if tipo and not bersagli:
            return f"{carta.nome} ha bisogno di un bersaglio ({NOMI_BERSAGLI[tipo]})"
        if tipo and massimo and len(bersagli) > massimo:
            return f"{carta.nome} ha un solo bersaglio" if massimo == 1 else f"{carta.nome} ha al massimo {massimo} bersagli"
        if len(set(bersagli)) != len(bersagli):
            return "lo stesso bersaglio non si può scegliere due volte"
        for rif in bersagli if tipo else []:
            if not bersaglio_legale(partita, tipo, rif, carta):
                return _motivo_bersaglio(partita, rif, carta, f"bersaglio non valido per {carta.nome}: serve {NOMI_BERSAGLI[tipo]}")
        if not tipo and bersagli:
            return f"{carta.nome} non ha bersagli"
    if x < 0:
        return "X non può essere negativo"
    costo = costo_di_lancio(carta, x, len(bersagli or []))
    if mana.piano_pagamento(g.riserva, fonti_di_mana(partita, nome_giocatore), costo) is None:
        con = f" con X={x}" if "X" in carta.costo else ""
        extra = f" per {len(bersagli)} bersagli" if bersagli and len(bersagli) > 1 else ""
        return f"non hai abbastanza mana per {carta.nome} ({carta.costo}{con}{extra})"
    return None


def max_bersagli(carta: Carta) -> int:
    effetto = EFFETTI.get(carta.nome)
    return effetto.max_bersagli if effetto else 1


def costo_di_lancio(carta: Carta, x: int = 0, n_bersagli: int = 1) -> dict[str, int]:
    """Costo con X scelto, più l'eventuale costo per ogni bersaglio oltre il primo (Fireball)."""
    costo = mana.con_x(mana.analizza_costo(carta.costo), x)
    effetto = EFFETTI.get(carta.nome)
    if effetto and effetto.costo_per_bersaglio and n_bersagli > 1:
        for colore, q in mana.analizza_costo(effetto.costo_per_bersaglio).items():
            costo[colore] = costo.get(colore, 0) + q * (n_bersagli - 1)
    return costo


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
    if abilita.solo_nel_tuo_turno and partita.giocatore_attivo.nome != nome_giocatore:
        return f"{carta.nome}: si attiva solo nel tuo turno"
    if abilita.tappa and (motivo := puo_tappare(partita, nome_giocatore, carta)):
        return motivo
    if abilita.togli_segnalino and carta.segnalini < 1:
        return f"{carta.nome} non ha segnalini +1/+1 da togliere"
    if abilita.solo_con_sette and len(partita.giocatore(nome_giocatore)[Zona.MANO]) != 7:
        return f"{carta.nome}: si attiva solo con esattamente sette carte in mano"
    if abilita.sacrifica_tipo and not da_sacrificare(partita, nome_giocatore, carta, abilita.sacrifica_tipo):
        return f"non hai un {'artefatto' if abilita.sacrifica_tipo == 'artefatto' else 'creatura'} da sacrificare"
    fonti = fonti_di_mana(partita, nome_giocatore, carta if abilita.tappa else None)
    if mana.piano_pagamento(partita.giocatore(nome_giocatore).riserva, fonti, mana.analizza_costo(abilita.costo_mana)) is None:
        return f"non hai abbastanza mana per l'abilità di {carta.nome} ({abilita.costo_mana})"
    if bersagli is not None:
        if abilita.bersaglio and len(bersagli) != 1:
            return f"l'abilità di {carta.nome} ha bisogno di un bersaglio ({NOMI_BERSAGLI[abilita.bersaglio]})"
        if abilita.bersaglio and not bersaglio_legale(partita, abilita.bersaglio, bersagli[0], carta):
            return _motivo_bersaglio(partita, bersagli[0], carta, f"bersaglio non valido: serve {NOMI_BERSAGLI[abilita.bersaglio]}")
    return None


def da_sacrificare(partita: Partita, nome_giocatore: str, fonte: Carta, tipo: str) -> list[Carta]:
    """Permanenti che si possono sacrificare per un costo «Sacrifice an artifact / a creature»."""
    def adatto(c: Carta) -> bool:
        return ("Artifact" in c.tipo_attuale) if tipo == "artefatto" else c.is_creatura
    return [c for c in partita.giocatore(nome_giocatore)[Zona.CAMPO] if adatto(c)]
