"""Azioni che modificano lo stato. Validano, applicano e scrivono sempre nel registro eventi."""
from app.engine import carte_implementate  # noqa: F401  registra gli effetti delle carte
from app.engine import mana, statici
from app.engine.effetti import EFFETTI
from app.engine.eventi import Evento
from app.engine.inneschi import analizza_inneschi
from app.engine.stato import ORDINE_FASI, Carta, Fase, OggettoPila, Partita, Scelta
from app.engine.effetti import bersaglio_legale
from app.engine.validazione import (AzioneIllegale, fonti_di_mana, puo_attivare, puo_giocare_terra,
                                    puo_lanciare, puo_passare, puo_tappare)
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
    statici.aggiorna(partita)
    for innesco in analizza_inneschi(carta):
        if innesco.momento == "entra":
            _metti_innesco(partita, giocatore, carta, innesco)


# --- Abilità innescate -------------------------------------------------------------------------

def _metti_innesco(partita: Partita, controllore: str, carta: Carta, innesco) -> None:
    partita.pila.append(OggettoPila(carta, controllore, innesco=innesco,
                                    giocatore_del_turno=partita.giocatore_attivo.nome))
    partita.passaggi = 0
    _log(partita, controllore, "innesco", f"Si innesca {carta.nome}: {innesco.testo}", carta=carta.id)


def metti_inneschi(partita: Partita, momento: str) -> None:
    """Mette in pila gli inneschi di quel momento: prima quelli del giocatore attivo, poi dell'altro
    (così quelli dell'altro si risolvono per primi)."""
    attivo = partita.giocatore_attivo.nome
    for g in sorted(partita.giocatori, key=lambda x: x.nome != attivo):
        for carta in list(g[Zona.CAMPO]):
            for innesco in analizza_inneschi(carta):
                if innesco.momento != momento or (innesco.se_stappata and carta.tappata):
                    continue
                if (innesco.chi == "tuo" and g.nome != attivo) or (innesco.chi == "avversario" and g.nome == attivo):
                    continue
                _metti_innesco(partita, g.nome, carta, innesco)
    partita.priorita = partita.attivo


def _risolvi_innesco(partita: Partita, oggetto: OggettoPila) -> None:
    inn, carta, chi = oggetto.innesco, oggetto.carta, oggetto.controllore
    quel_giocatore = oggetto.giocatore_del_turno or chi
    in_campo = partita.trova_in_campo(carta.id) is not None
    if inn.se_stappata and (not in_campo or carta.tappata):
        _log(partita, chi, "neutralizzata", f"{carta.nome} non è stappata: l'innesco non ha effetto")
        return
    mano = len(partita.giocatore(quel_giocatore)[Zona.MANO])
    match inn.effetto:
        case "danno_te":
            modifica_vita(partita, chi, -inn.n, f"(danni da {carta.nome})")
        case "perdi_vita":
            modifica_vita(partita, chi, -inn.n, f"({carta.nome})")
        case "guadagna_vita":
            modifica_vita(partita, chi, inn.n, f"({carta.nome})")
        case "danno_mano_meno" | "danno_meno_mano":
            x = max(0, mano - inn.n if inn.effetto == "danno_mano_meno" else inn.n - mano)
            if x:
                modifica_vita(partita, quel_giocatore, -x, f"(danni da {carta.nome})")
            else:
                _log(partita, chi, "risolve", f"{carta.nome} non infligge danni")
        case "vita_mano_meno":
            x = max(0, len(partita.giocatore(chi)[Zona.MANO]) - inn.n)
            if x:
                modifica_vita(partita, chi, x, f"({carta.nome})")
        case "pesca_quel_giocatore":
            pesca(partita, quel_giocatore)
        case "pesca_tu":
            pesca(partita, chi)
        case "sacrifica":
            if in_campo:
                distruggi(partita, carta, "(sacrificata)", rigenerabile=False)
        case "sacrifica_salvo_paga" | "danno_te_salvo_paga":
            if inn.effetto == "sacrifica_salvo_paga" and not in_campo:
                return
            cosa = "sacrificare" if inn.effetto == "sacrifica_salvo_paga" else f"subire {inn.n} danni"
            partita.scelta = Scelta(chi, oggetto, inn.costo, f"pagare {inn.costo} per {carta.nome} o {cosa}?")
            _log(partita, chi, "scelta", f"{chi} deve scegliere: pagare {inn.costo} o {cosa}")


def rispondi_scelta(partita: Partita, giocatore: str, paga: bool) -> None:
    scelta = partita.scelta
    if scelta is None:
        raise AzioneIllegale("non c'è nessuna scelta in sospeso")
    if scelta.giocatore != giocatore:
        raise AzioneIllegale(f"tocca a {scelta.giocatore} scegliere")
    g = partita.giocatore(giocatore)
    oggetto = scelta.oggetto
    if paga:
        costo = mana.analizza_costo(scelta.costo)
        piano = mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore), costo)
        if piano is None:
            raise AzioneIllegale(f"non hai abbastanza mana per pagare {scelta.costo}")
        for fonte in piano:
            tappa(partita, giocatore, fonte)
        g.riserva = mana.paga(g.riserva, costo)
        _log(partita, giocatore, "paga", f"{giocatore} paga {scelta.costo} per {oggetto.carta.nome}")
    else:
        _log(partita, giocatore, "non_paga", f"{giocatore} non paga per {oggetto.carta.nome}")
        if oggetto.innesco.effetto == "sacrifica_salvo_paga":
            distruggi(partita, oggetto.carta, "(sacrificata)", rigenerabile=False)
        else:
            modifica_vita(partita, giocatore, -oggetto.innesco.n, f"(danni da {oggetto.carta.nome})")
    partita.scelta = None
    azioni_di_stato(partita)
    partita.priorita = partita.attivo
    partita.passaggi = 0


def puo_pagare_scelta(partita: Partita) -> bool:
    s = partita.scelta
    if s is None:
        return False
    g = partita.giocatore(s.giocatore)
    return mana.piano_pagamento(g.riserva, fonti_di_mana(partita, s.giocatore), mana.analizza_costo(s.costo)) is not None


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


def lancia(partita: Partita, giocatore: str, carta: Carta, bersagli: list[str] | None = None) -> None:
    """Paga il costo (tappando da solo le fonti necessarie) e mette la magia in pila.
    Chi lancia mantiene la priorità."""
    bersagli = bersagli or []
    _verifica(puo_lanciare(partita, giocatore, carta, bersagli))
    g = partita.giocatore(giocatore)
    costo = mana.analizza_costo(carta.costo)
    for fonte in mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore), costo):
        tappa(partita, giocatore, fonte)
    g.riserva = mana.paga(g.riserva, costo)
    g[Zona.MANO].remove(carta)
    partita.pila.append(OggettoPila(carta, giocatore, bersagli))
    partita.passaggi = 0
    su = f" su {descrivi_bersaglio(partita, bersagli[0])}" if bersagli else ""
    _log(partita, giocatore, "lancia", f"{giocatore} lancia {carta.nome}{su}", carta=carta.id)


def attiva(partita: Partita, giocatore: str, carta: Carta, abilita, bersagli: list[str] | None = None) -> None:
    """Paga il costo dell'abilità (tappando la carta se serve {T}) e la mette in pila."""
    bersagli = bersagli or []
    _verifica(puo_attivare(partita, giocatore, carta, abilita, bersagli))
    g = partita.giocatore(giocatore)
    costo = mana.analizza_costo(abilita.costo_mana)
    fonti = [f for f in fonti_di_mana(partita, giocatore) if not (abilita.tappa and f[0] is carta)]
    for fonte in mana.piano_pagamento(g.riserva, fonti, costo):
        tappa(partita, giocatore, fonte)
    g.riserva = mana.paga(g.riserva, costo)
    if abilita.tappa:
        carta.tappata = True
    partita.pila.append(OggettoPila(carta, giocatore, bersagli, abilita))
    partita.passaggi = 0
    su = f" su {descrivi_bersaglio(partita, bersagli[0])}" if bersagli else ""
    _log(partita, giocatore, "attiva", f"{giocatore} attiva l'abilità di {carta.nome}{su}", carta=carta.id)


def creatura_pompata(partita: Partita, fonte: Carta, ab) -> Carta | None:
    """La creatura che riceve un pompaggio: la fonte stessa o, per un'aura, la creatura incantata."""
    if not partita.trova_in_campo(fonte.id):
        return None
    if getattr(ab, "su_incantata", False):
        trovato = partita.trova_in_campo(fonte.attaccata_a) if fonte.attaccata_a else None
        return trovato[1] if trovato else None
    return fonte


def _risolvi_abilita(partita: Partita, oggetto: OggettoPila) -> None:
    ab, fonte, chi = oggetto.abilita, oggetto.carta, oggetto.controllore
    if ab.bersaglio and not bersaglio_legale(partita, ab.bersaglio, oggetto.bersagli[0], fonte):
        _log(partita, chi, "neutralizzata", f"L'abilità di {fonte.nome} non ha più un bersaglio valido")
        return
    if ab.tipo == "pompa":
        creatura = creatura_pompata(partita, fonte, ab)
        if creatura is None:
            _log(partita, chi, "neutralizzata", f"{fonte.nome}: la creatura non è più in campo, l'abilità non ha effetto")
            return
        creatura.bonus_forza += ab.forza
        creatura.bonus_costituzione += ab.costituzione
        _log(partita, chi, "risolve", f"{creatura.nome} prende {ab.forza:+d}/{ab.costituzione:+d} fino a fine turno")
    elif ab.tipo == "danno":
        infliggi_danno(partita, fonte, oggetto.bersagli[0], ab.danni)
    elif ab.tipo == "rigenera":
        if not partita.trova_in_campo(fonte.id):
            _log(partita, chi, "neutralizzata", f"{fonte.nome} non è più in campo: niente rigenerazione")
            return
        fonte.scudi_rigenerazione += 1
        _log(partita, chi, "risolve", f"{fonte.nome} ha uno scudo di rigenerazione fino a fine turno")


def descrivi_bersaglio(partita: Partita, rif: str) -> str:
    oggetto = partita.risolvi_bersaglio(rif)
    return getattr(oggetto, "nome", "un bersaglio scomparso")


def risolvi_pila(partita: Partita) -> None:
    oggetto = partita.pila.pop()
    carta, chi = oggetto.carta, oggetto.controllore
    if oggetto.innesco:
        _risolvi_innesco(partita, oggetto)
    elif oggetto.abilita:
        _risolvi_abilita(partita, oggetto)
    elif carta.is_aura:
        if not bersaglio_legale(partita, "creatura", oggetto.bersagli[0], carta):
            _log(partita, chi, "neutralizzata", f"{carta.nome} non ha più una creatura valida e va al cimitero")
            partita.giocatore(carta.proprietario or chi)[Zona.CIMITERO].append(carta)
        else:
            carta.attaccata_a = oggetto.bersagli[0].removeprefix("carta:")
            _log(partita, chi, "risolve", f"{carta.nome} incanta {descrivi_bersaglio(partita, oggetto.bersagli[0])}",
                 carta=carta.id)
            _entra_in_campo(partita, chi, carta)
    elif carta.is_permanente:
        _log(partita, chi, "risolve", f"{carta.nome} si risolve ed entra in campo", carta=carta.id)
        _entra_in_campo(partita, chi, carta)
    else:
        effetto = EFFETTI[carta.nome]
        if effetto.bersaglio and not bersaglio_legale(partita, effetto.bersaglio, oggetto.bersagli[0], carta):
            _log(partita, chi, "neutralizzata", f"{carta.nome} non ha più un bersaglio valido e non ha effetto")
        else:
            effetto.funzione(partita, oggetto)
            _log(partita, chi, "risolve", f"{carta.nome} si risolve", carta=carta.id)
        partita.giocatore(carta.proprietario or chi)[Zona.CIMITERO].append(carta)
    azioni_di_stato(partita)
    partita.priorita = partita.attivo
    partita.passaggi = 0


def infliggi_danno(partita: Partita, fonte: Carta, rif: str, quantita: int) -> None:
    bersaglio = partita.risolvi_bersaglio(rif)
    if isinstance(bersaglio, Carta) and bersaglio.protetta_da(fonte):
        _log(partita, fonte.proprietario, "prevenuto", f"{bersaglio.nome} ha protezione: niente danni da {fonte.nome}")
    elif isinstance(bersaglio, Carta):
        bersaglio.danni += quantita
        _log(partita, fonte.proprietario, "danno", f"{fonte.nome} infligge {quantita} danni a {bersaglio.nome}")
    elif bersaglio is not None:
        modifica_vita(partita, bersaglio.nome, -quantita, f"(danni da {fonte.nome})")


def _rigenera(partita: Partita, controllore: str, carta: Carta) -> None:
    """Usa uno scudo: niente danni, tappata, fuori dal combattimento. Un attaccante resta «bloccato»."""
    carta.scudi_rigenerazione -= 1
    carta.danni = 0
    carta.tappata = True
    comb = partita.combattimento
    if comb:
        if carta.id in comb.attaccanti:
            comb.attaccanti.remove(carta.id)
            comb.blocchi.pop(carta.id, None)
        for bloccanti in comb.blocchi.values():
            if carta.id in bloccanti:
                bloccanti.remove(carta.id)
    _log(partita, controllore, "rigenera", f"{carta.nome} si rigenera", carta=carta.id)


def distruggi(partita: Partita, carta: Carta, motivo: str = "", rigenerabile: bool = True) -> None:
    """Distrugge (o sacrifica, con rigenerabile=False) un permanente. Uno scudo di rigenerazione lo salva."""
    trovato = partita.trova_in_campo(carta.id)
    if not trovato:
        return
    controllore, _ = trovato
    if rigenerabile and carta.scudi_rigenerazione > 0:
        _rigenera(partita, controllore.nome, carta)
        return
    controllore[Zona.CAMPO].remove(carta)
    carta.azzera_stato_in_campo()
    carta.tappata = False
    carta.attaccata_a = None
    partita.giocatore(carta.proprietario or controllore.nome)[Zona.CIMITERO].append(carta)
    _log(partita, controllore.nome, "muore", f"{carta.nome} va al cimitero {motivo}".strip(), carta=carta.id)


def azioni_di_stato(partita: Partita) -> None:
    """Controlli automatici, ripetuti finché qualcosa cambia: aure senza creatura (o su una creatura protetta dal
    loro colore) al cimitero, creature con danni letali o costituzione 0 al cimitero. Ricalcola gli effetti statici."""
    for _ in range(20):
        statici.aggiorna(partita)
        if not _un_giro_di_controlli(partita):
            return


def _un_giro_di_controlli(partita: Partita) -> bool:
    cambiato = False
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if c.is_aura:
                trovato = partita.trova_in_campo(c.attaccata_a) if c.attaccata_a else None
                if trovato is None or trovato[1].protetta_da(c):
                    distruggi(partita, c, "(non incanta più una creatura valida)", rigenerabile=False)
                    cambiato = True
    statici.aggiorna(partita)
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if c.is_creatura and c.costituzione_attuale <= 0:
                distruggi(partita, c, "(costituzione 0)", rigenerabile=False)
                cambiato = True
            elif c.is_creatura and c.danni >= c.costituzione_attuale:
                prima = c.scudi_rigenerazione
                distruggi(partita, c, "(danni letali)")
                cambiato = cambiato or prima == 0 or c.danni == 0
    return cambiato


def passa_priorita(partita: Partita, giocatore: str) -> None:
    """Quando entrambi passano di fila: si risolve la cima della pila, o se è vuota si va alla fase successiva."""
    _verifica(puo_passare(partita, giocatore))
    partita.passaggi += 1
    if partita.passaggi < 2:
        partita.priorita = 1 - partita.priorita
        return
    if partita.pila:
        risolvi_pila(partita)
        return
    from app.engine import combattimento
    if not combattimento.dopo_doppio_passaggio(partita):
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
    if partita.scelta:
        raise AzioneIllegale("c'è una scelta in sospeso")
    svuota_riserve(partita)
    if partita.vincitore:
        return
    partita.priorita = partita.attivo
    partita.passaggi = 0
    partita.combattimento = None
    i = ORDINE_FASI.index(partita.fase)
    if i + 1 < len(ORDINE_FASI):
        partita.fase = ORDINE_FASI[i + 1]
        _log(partita, partita.giocatore_attivo.nome, "fase", f"Fase: {partita.fase.value}")
        _automatismi_fase(partita)
        return
    # Fine turno: danni e effetti "fino alla fine del turno" svaniscono.
    for giocatore in partita.giocatori:
        for c in giocatore[Zona.CAMPO]:
            c.azzera_stato_in_campo()
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
    elif partita.fase == Fase.MANTENIMENTO:
        metti_inneschi(partita, "mantenimento")
    elif partita.fase == Fase.PESCATA:
        pesca(partita, g.nome)
        if not partita.vincitore:
            metti_inneschi(partita, "pescata")
    elif partita.fase == Fase.FINALE:
        metti_inneschi(partita, "finale")
    elif partita.fase == Fase.COMBATTIMENTO:
        from app.engine import combattimento
        combattimento.inizia(partita)
