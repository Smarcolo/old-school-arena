"""Azioni che modificano lo stato. Validano, applicano e scrivono sempre nel registro eventi."""
from app.engine import carte_implementate  # noqa: F401  registra gli effetti delle carte
from app.engine import mana, speciali, statici
from app.engine.effetti import EFFETTI
from app.engine.eventi import Evento
from app.engine.inneschi import Innesco, analizza_inneschi
from app.engine.stato import ORDINE_FASI, PAREGGIO, Carta, Fase, OggettoPila, Partita, Scelta
from app.engine.effetti import bersaglio_legale
from app.engine.validazione import (AzioneIllegale, costo_di_lancio, da_sacrificare, fonti_di_mana, puo_attivare,
                                    puo_giocare_terra, puo_lanciare, puo_passare, puo_tappare)
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
            # 93/94: chi deve pescare da un grimorio vuoto perde (al controllo successivo, vedi controlla_sconfitte)
            if not g.pescato_da_vuoto:
                _log(partita, giocatore, "grimorio_vuoto", f"{giocatore} non può pescare: grimorio vuoto")
            g.pescato_da_vuoto = True
            break
        carta = g[Zona.GRIMORIO].pop()
        carta.pescata_nel_turno = partita.turno
        g[Zona.MANO].append(carta)
        pescate.append(carta)
    _log(partita, giocatore, "pesca", f"{giocatore} pesca {len(pescate)} carta/e")
    return pescate


def _entra_in_campo(partita: Partita, giocatore: str, carta: Carta) -> None:
    carta.entrata_nel_turno = partita.turno
    carta.tappata = False
    partita.giocatore(giocatore)[Zona.CAMPO].append(carta)
    carta.segnalini = speciali.segnalini_iniziali(carta)
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
            modifica_vita(partita, chi, -inn.n, f"(danni da {carta.nome})", danno=True)
        case "perdi_vita":
            modifica_vita(partita, chi, -inn.n, f"({carta.nome})")
        case "guadagna_vita":
            modifica_vita(partita, chi, inn.n, f"({carta.nome})")
        case "danno_mano_meno" | "danno_meno_mano":
            x = max(0, mano - inn.n if inn.effetto == "danno_mano_meno" else inn.n - mano)
            if x:
                modifica_vita(partita, quel_giocatore, -x, f"(danni da {carta.nome})", danno=True)
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
        case "sylvan":
            pesca(partita, chi, 2)
            carte_implementate.continua_sylvan(partita, chi, 0, ())
        case "segnalino_su_se":
            if in_campo:
                carta.segnalini += 1
                _log(partita, chi, "segnalino", f"{carta.nome} prende un segnalino +1/+1", carta=carta.id)
        case "sacrifica":
            if in_campo:
                distruggi(partita, carta, "(sacrificata)", rigenerabile=False)
        case "scarta_caso":
            scarta_a_caso(partita, quel_giocatore, 1, f"({carta.nome})")
        case "aggiungi_incolore":
            aggiungi_mana(partita, chi, "C", inn.n, f"({carta.nome})")
        case "abisso":
            creature = [c for c in partita.giocatore(quel_giocatore)[Zona.CAMPO]
                        if c.is_creatura and "Artifact" not in c.tipo_attuale]
            scegli_o_decidi(partita, quel_giocatore, carta.nome, "distruggi", creature,
                            f"{carta.nome}: scegli una tua creatura non artefatto da distruggere")
        case "erhnam":
            avversario = partita.avversario_di(chi).nome
            creature = [c for c in partita.giocatore(avversario)[Zona.CAMPO]
                        if c.is_creatura and "Wall" not in c.tipo_attuale and not c.protetta_da(carta)]
            scegli_o_decidi(partita, chi, carta.nome, "passaforeste", creature,
                            f"{carta.nome}: scegli una creatura avversaria che ottiene passa-foreste")
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
    if scelta.tipo != "paga":
        raise AzioneIllegale("ora non c'è niente da pagare: " + (scelta.testo or "c'è un'altra scelta in sospeso"))
    if scelta.giocatore != giocatore:
        raise AzioneIllegale(f"tocca a {scelta.giocatore} scegliere")
    g = partita.giocatore(giocatore)
    oggetto = scelta.oggetto
    if paga:
        costo = mana.analizza_costo(scelta.costo)
        piano = mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore), costo)
        if piano is None:
            raise AzioneIllegale(f"non hai abbastanza mana per pagare {scelta.costo}")
        for fonte, colore in piano:
            tappa(partita, giocatore, fonte.carta, colore)
        g.riserva = mana.paga(g.riserva, costo)
        _log(partita, giocatore, "paga", f"{giocatore} paga {scelta.costo} per {oggetto.carta.nome}")
    else:
        _log(partita, giocatore, "non_paga", f"{giocatore} non paga per {oggetto.carta.nome}")
        if oggetto.innesco.effetto == "sacrifica_salvo_paga":
            distruggi(partita, oggetto.carta, "(sacrificata)", rigenerabile=False)
        else:
            modifica_vita(partita, giocatore, -oggetto.innesco.n, f"(danni da {oggetto.carta.nome})", danno=True)
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


def tappa(partita: Partita, giocatore: str, carta: Carta, colore: str | None = None) -> None:
    """Tappa un permanente. Se ha un'abilità di mana, il mana va nella riserva (abilità di mana: niente pila);
    `colore` sceglie tra le opzioni della fonte (di default la prima). Black Lotus si sacrifica, City of Brass fa
    1 danno a chi la tappa."""
    _verifica(puo_tappare(partita, giocatore, carta))
    fonte = mana.fonte_in_partita(carta, partita.avversario_di(giocatore)[Zona.CAMPO])
    if fonte and colore and colore not in fonte.colori:
        raise AzioneIllegale(f"{carta.nome} non produce {{{colore}}}")
    carta.tappata = True
    if not fonte:
        _log(partita, giocatore, "tappa", f"{giocatore} tappa {carta.nome}", carta=carta.id)
        return
    colore = colore or fonte.colori[0]
    partita.giocatore(giocatore).riserva[colore] += fonte.quantita
    _log(partita, giocatore, "mana", f"{giocatore} tappa {carta.nome} per {('{' + colore + '}') * fonte.quantita}",
         carta=carta.id)
    if fonte.sacrifica:
        distruggi(partita, carta, "(sacrificata)", rigenerabile=False)
    if fonte.danno:
        # la sconfitta arriva al prossimo controllo (anche a metà pagamento di una magia: non la interrompe)
        modifica_vita(partita, giocatore, -fonte.danno, f"(danni da {carta.nome})", danno=True)


def lancia(partita: Partita, giocatore: str, carta: Carta, bersagli: list[str] | None = None, x: int = 0) -> None:
    """Paga il costo (tappando da solo le fonti necessarie, con X scelto) e mette la magia in pila.
    Chi lancia mantiene la priorità."""
    bersagli = bersagli or []
    _verifica(puo_lanciare(partita, giocatore, carta, bersagli, x))
    carta.proprietario = carta.proprietario or giocatore
    g = partita.giocatore(giocatore)
    costo = costo_di_lancio(carta, x, len(bersagli))
    for fonte, colore in mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore), costo):
        tappa(partita, giocatore, fonte.carta, colore)
    g.riserva = mana.paga(g.riserva, costo)
    g[Zona.MANO].remove(carta)
    partita.pila.append(OggettoPila(carta, giocatore, bersagli, x=x))
    partita.passaggi = 0
    su = " su " + " e ".join(descrivi_bersaglio(partita, b) for b in bersagli) if bersagli else ""
    con_x = f" (X={x})" if "X" in carta.costo else ""
    _log(partita, giocatore, "lancia", f"{giocatore} lancia {carta.nome}{con_x}{su}", carta=carta.id)


def attiva(partita: Partita, giocatore: str, carta: Carta, abilita, bersagli: list[str] | None = None,
           sacrificio: Carta | None = None) -> None:
    """Paga il costo dell'abilità (mana, {T}, sacrifici) e la mette in pila. Per «Sacrifice an artifact» si può
    indicare quale; altrimenti si sacrifica quello di valore più basso."""
    bersagli = bersagli or []
    _verifica(puo_attivare(partita, giocatore, carta, abilita, bersagli))
    if abilita.sacrifica_tipo:
        possibili = da_sacrificare(partita, giocatore, carta, abilita.sacrifica_tipo)
        if sacrificio is not None and sacrificio not in possibili:
            raise AzioneIllegale(f"non puoi sacrificare {sacrificio.nome} per questa abilità")
        sacrificio = sacrificio or min(possibili, key=lambda c: (mana.valore(c.costo), c is carta))
    g = partita.giocatore(giocatore)
    costo = mana.analizza_costo(abilita.costo_mana)
    # prima prova senza tappare la carta stessa (es. Mishra's Factory che si anima per attaccare)
    piano = mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore, carta), costo)
    if piano is None and abilita.tipo != "anima":  # animarsi col proprio mana non serve (vedi puo_attivare)
        piano = mana.piano_pagamento(g.riserva, fonti_di_mana(partita, giocatore, carta if abilita.tappa else None), costo)
    for fonte, colore in piano:
        tappa(partita, giocatore, fonte.carta, colore)
    g.riserva = mana.paga(g.riserva, costo)
    if abilita.tappa:
        carta.tappata = True
    if sacrificio is not None:
        distruggi(partita, sacrificio, f"(sacrificata per {carta.nome})", rigenerabile=False)
    if abilita.sacrifica_se:
        distruggi(partita, carta, "(sacrificata)", rigenerabile=False)
    if abilita.togli_segnalino:
        carta.segnalini -= 1
        azioni_di_stato(partita)
    partita.pila.append(OggettoPila(carta, giocatore, bersagli, abilita=abilita))
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
    elif ab.tipo == "anima":
        if not partita.trova_in_campo(fonte.id):
            return
        fonte.animata = (ab.forza, ab.costituzione, ab.tipo_animato)
        _log(partita, chi, "anima", f"{fonte.nome} diventa una creatura {ab.forza}/{ab.costituzione} fino a fine turno")
        statici.aggiorna(partita)
    elif ab.tipo == "pompa_bersaglio":
        creatura = partita.risolvi_bersaglio(oggetto.bersagli[0])
        creatura.bonus_forza += ab.forza
        creatura.bonus_costituzione += ab.costituzione
        _log(partita, chi, "risolve", f"{creatura.nome} prende {ab.forza:+d}/{ab.costituzione:+d} fino a fine turno")
    elif ab.tipo == "scarta":
        bersaglio = partita.risolvi_bersaglio(oggetto.bersagli[0])
        mano = list(bersaglio[Zona.MANO])
        scegli_o_decidi(partita, bersaglio.nome, fonte.nome, "scarta", mano, f"{fonte.nome}: scegli una carta da scartare")
    elif ab.tipo == "distruggi":
        distruggi(partita, partita.risolvi_bersaglio(oggetto.bersagli[0]), f"({fonte.nome})")
    elif ab.tipo == "pesca":
        pesca(partita, chi)
    elif ab.tipo == "tappa":
        bersaglio = partita.risolvi_bersaglio(oggetto.bersagli[0])
        bersaglio.tappata = True
        _log(partita, chi, "tappa", f"{fonte.nome} tappa {bersaglio.nome}")
    elif ab.tipo == "macina":
        macina(partita, partita.risolvi_bersaglio(oggetto.bersagli[0]).nome, ab.quante, f"({fonte.nome})")
    elif ab.tipo == "scambia_vita":
        altro = partita.risolvi_bersaglio(oggetto.bersagli[0])
        mia, sua = partita.giocatore(chi).vita, altro.vita
        modifica_vita(partita, chi, sua - mia, f"({fonte.nome}: scambio dei punti vita)")
        modifica_vita(partita, altro.nome, mia - sua, f"({fonte.nome}: scambio dei punti vita)")
    elif ab.tipo == "chaos_orb":
        if not partita.trova_in_campo(fonte.id):  # «If Chaos Orb is on the battlefield»: distrutta in risposta
            _log(partita, chi, "neutralizzata", f"{fonte.nome} non è più in campo: non cade su niente")
            return
        colpito = partita.risolvi_bersaglio(oggetto.bersagli[0])
        _log(partita, chi, "chaos_orb", f"{fonte.nome} cade su {colpito.nome}")
        distruggi(partita, colpito, f"(colpita da {fonte.nome})")
        if partita.trova_in_campo(fonte.id):
            distruggi(partita, fonte, "(Chaos Orb si distrugge)")
    elif ab.tipo == "rigenera":
        if not partita.trova_in_campo(fonte.id):
            _log(partita, chi, "neutralizzata", f"{fonte.nome} non è più in campo: niente rigenerazione")
            return
        fonte.scudi_rigenerazione += 1
        _log(partita, chi, "risolve", f"{fonte.nome} ha uno scudo di rigenerazione fino a fine turno")


def descrivi_bersaglio(partita: Partita, rif: str) -> str:
    oggetto = partita.risolvi_bersaglio(rif)
    if isinstance(oggetto, OggettoPila):
        return oggetto.descrizione
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
        if effetto.bersaglio and not any(bersaglio_legale(partita, effetto.bersaglio, b, carta) for b in oggetto.bersagli):
            _log(partita, chi, "neutralizzata", f"{carta.nome} non ha più un bersaglio valido e non ha effetto")
        else:
            effetto.funzione(partita, oggetto)
            _log(partita, chi, "risolve", f"{carta.nome} si risolve", carta=carta.id)
        zona = Zona.RIMOSSE if effetto.rimuovi_dal_gioco else Zona.CIMITERO  # Recall: «Exile Recall»
        partita.giocatore(carta.proprietario or chi)[zona].append(carta)
    azioni_di_stato(partita)
    partita.priorita = partita.attivo
    partita.passaggi = 0


def danni_a_giocatore(partita: Partita, fonte: Carta, giocatore: str, quantita: int) -> None:
    """Danni a un giocatore, con gli inneschi «Whenever NAME deals damage to an opponent» (Hypnotic Specter)."""
    if quantita <= 0:
        return
    modifica_vita(partita, giocatore, -quantita, f"(danni da {fonte.nome})", danno=True)
    trovato = partita.trova_in_campo(fonte.id)
    if trovato and trovato[0].nome != giocatore:
        for innesco in analizza_inneschi(fonte):
            if innesco.momento == "danno_avversario":
                partita.pila.append(OggettoPila(fonte, trovato[0].nome, innesco=innesco, giocatore_del_turno=giocatore))
                partita.passaggi = 0
                _log(partita, trovato[0].nome, "innesco", f"Si innesca {fonte.nome}: {innesco.testo}", carta=fonte.id)


def danni_a_creatura(partita: Partita, fonte: Carta, creatura: Carta, quantita: int) -> None:
    if quantita <= 0:
        return
    if creatura.protetta_da(fonte):
        _log(partita, fonte.proprietario, "prevenuto", f"{creatura.nome} ha protezione: niente danni da {fonte.nome}")
        return
    creatura.danni += quantita
    creatura.danneggiata_da.add(fonte.id)
    _log(partita, fonte.proprietario, "danno", f"{fonte.nome} infligge {quantita} danni a {creatura.nome}")


def infliggi_danno(partita: Partita, fonte: Carta, rif: str, quantita: int) -> None:
    bersaglio = partita.risolvi_bersaglio(rif)
    if isinstance(bersaglio, Carta) and bersaglio.protetta_da(fonte):
        _log(partita, fonte.proprietario, "prevenuto", f"{bersaglio.nome} ha protezione: niente danni da {fonte.nome}")
    elif isinstance(bersaglio, Carta):
        bersaglio.danni += quantita
        bersaglio.danneggiata_da.add(fonte.id)
        _log(partita, fonte.proprietario, "danno", f"{fonte.nome} infligge {quantita} danni a {bersaglio.nome}")
    elif bersaglio is not None:
        danni_a_giocatore(partita, fonte, bersaglio.nome, quantita)


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
            for banda in comb.bande:
                if carta.id in banda:
                    banda.remove(carta.id)
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
    if rigenerabile and carta.scudi_rigenerazione > 0 and not carta.disintegrata:
        _rigenera(partita, controllore.nome, carta)
        return
    if carta.disintegrata:  # non muore: viene rimossa dal gioco (niente inneschi «quando muore»)
        rimuovi_dal_gioco(partita, carta, motivo)
        return
    danneggiata_da = set(carta.danneggiata_da)
    controllore[Zona.CAMPO].remove(carta)
    carta.lascia_il_campo()
    partita.giocatore(carta.proprietario or controllore.nome)[Zona.CIMITERO].append(carta)
    _log(partita, controllore.nome, "muore", f"{carta.nome} va al cimitero {motivo}".strip(), carta=carta.id)
    if carta.is_creatura:
        for id_fonte in danneggiata_da:  # Sengir Vampire: l'innesco va in pila
            if (t := partita.trova_in_campo(id_fonte)) and speciali.cresce_quando_muore_un_danneggiato(t[1]):
                _metti_innesco(partita, t[0].nome, t[1], Innesco(
                    f"una creatura danneggiata da {t[1].nome} è morta: prende un segnalino +1/+1", "muore", "ogni",
                    "segnalino_su_se"))
        for innesco in analizza_inneschi(carta):
            if innesco.momento == "muore":
                _metti_innesco(partita, controllore.nome, carta, innesco)


# --- Spostamenti di carte usati dagli effetti ---------------------------------------------------

def _lascia_il_campo(partita: Partita, carta: Carta) -> str | None:
    """Toglie la carta dal campo (se c'è) azzerandone lo stato; ritorna il nome del controllore."""
    trovato = partita.trova_in_campo(carta.id)
    if not trovato:
        return None
    trovato[0][Zona.CAMPO].remove(carta)
    carta.lascia_il_campo()
    return trovato[0].nome


def macina(partita: Partita, giocatore: str, quante: int, motivo: str = "") -> list[Carta]:
    """Le prime carte del grimorio nel cimitero (Millstone). Con il grimorio vuoto non succede niente:
    si perde solo quando si deve pescare."""
    g = partita.giocatore(giocatore)
    macinate = [g[Zona.GRIMORIO].pop() for _ in range(min(quante, len(g[Zona.GRIMORIO])))]
    g[Zona.CIMITERO].extend(macinate)
    nomi = ", ".join(c.nome for c in macinate) or "nessuna carta"
    _log(partita, giocatore, "macina", f"{giocatore} mette nel cimitero dal grimorio: {nomi} {motivo}".strip())
    return macinate


def rimuovi_dal_gioco(partita: Partita, carta: Carta, motivo: str = "") -> None:
    """Esilio («rimossa dal gioco» nel 93/94): non si rigenera."""
    chi = _lascia_il_campo(partita, carta)
    if chi is None:
        return
    partita.giocatore(carta.proprietario or chi)[Zona.RIMOSSE].append(carta)
    _log(partita, chi, "rimossa", f"{carta.nome} è rimossa dal gioco {motivo}".strip(), carta=carta.id)


def torna_in_mano(partita: Partita, carta: Carta) -> None:
    chi = _lascia_il_campo(partita, carta)
    if chi is None:
        return
    partita.giocatore(carta.proprietario or chi)[Zona.MANO].append(carta)
    _log(partita, chi, "in_mano", f"{carta.nome} torna in mano a {carta.proprietario or chi}", carta=carta.id)


def scarta(partita: Partita, giocatore: str, carta: Carta, motivo: str = "") -> None:
    g = partita.giocatore(giocatore)
    g[Zona.MANO].remove(carta)
    g[Zona.CIMITERO].append(carta)
    _log(partita, giocatore, "scarta", f"{giocatore} scarta {carta.nome} {motivo}".strip(), carta=carta.id)


def scarta_a_caso(partita: Partita, giocatore: str, quante: int, motivo: str = "") -> None:
    mano = partita.giocatore(giocatore)[Zona.MANO]
    for carta in partita.rng.sample(mano, min(quante, len(mano))):
        scarta(partita, giocatore, carta, motivo)


def neutralizza(partita: Partita, oggetto: OggettoPila, da: str) -> None:
    """Toglie una magia dalla pila e la mette nel cimitero del proprietario."""
    if oggetto not in partita.pila:
        return
    partita.pila.remove(oggetto)
    partita.giocatore(oggetto.carta.proprietario or oggetto.controllore)[Zona.CIMITERO].append(oggetto.carta)
    _log(partita, oggetto.controllore, "neutralizzata", f"{oggetto.carta.nome} è neutralizzata da {da}")


def mescola_nel_grimorio(partita: Partita, giocatore: str, *zone: Zona) -> None:
    g = partita.giocatore(giocatore)
    for zona in zone:
        g[Zona.GRIMORIO].extend(g[zona])
        g[zona].clear()
    partita.rng.shuffle(g[Zona.GRIMORIO])


def aggiungi_mana(partita: Partita, giocatore: str, colore: str, quanto: int, motivo: str = "") -> None:
    partita.giocatore(giocatore).riserva[colore] += quanto
    _log(partita, giocatore, "mana", f"{giocatore} aggiunge {('{' + colore + '}') * quanto} {motivo}".strip())


def cerca_nel_grimorio(partita: Partita, giocatore: str, fonte: Carta, scegli_auto) -> None:
    """Demonic Tutor e simili: chi è in scelte_manuali sceglie (Scelta "cerca"), gli altri con scegli_auto(carte)."""
    g = partita.giocatore(giocatore)
    if not g[Zona.GRIMORIO]:
        return
    if giocatore in partita.scelte_manuali:
        nomi = {}
        for c in g[Zona.GRIMORIO]:
            nomi.setdefault(c.nome, c.id)  # una voce per nome
        partita.scelta = Scelta(giocatore, testo=f"scegli una carta dal grimorio per {fonte.nome}", tipo="cerca",
                                dati={"carte": {i: n for n, i in sorted(nomi.items())}, "fonte": fonte.nome})
        return
    _prendi_dal_grimorio(partita, giocatore, scegli_auto(list(g[Zona.GRIMORIO])), fonte.nome)


def _prendi_dal_grimorio(partita: Partita, giocatore: str, carta: Carta, fonte: str) -> None:
    g = partita.giocatore(giocatore)
    g[Zona.GRIMORIO].remove(carta)
    g[Zona.MANO].append(carta)
    partita.rng.shuffle(g[Zona.GRIMORIO])
    _log(partita, giocatore, "cerca", f"{giocatore} prende una carta dal grimorio con {fonte} e rimescola")


def _applica_scelta(partita: Partita, giocatore: str, azione: str, carta: Carta, fonte: str) -> None:
    if azione == "distruggi":
        distruggi(partita, carta, f"({fonte})", rigenerabile=False)
    elif azione == "passaforeste":
        carta.passaforeste_fino_al_turno = partita.turno + 2  # fino al prossimo mantenimento di chi l'ha scelto
        _log(partita, giocatore, "passaforeste", f"{carta.nome} ha passa-foreste fino al prossimo mantenimento di {giocatore}")
        statici.aggiorna(partita)
    elif azione == "scarta":
        scarta(partita, giocatore, carta, f"({fonte})")
    elif azione == "riprendi":
        g = partita.giocatore(giocatore)
        if carta in g[Zona.CIMITERO]:
            g[Zona.CIMITERO].remove(carta)
            g[Zona.MANO].append(carta)
            _log(partita, giocatore, "riprende", f"{giocatore} riprende in mano {carta.nome} ({fonte})")
    elif azione == "in_cima":
        g = partita.giocatore(giocatore)
        if carta in g[Zona.MANO]:
            g[Zona.MANO].remove(carta)
            g[Zona.GRIMORIO].append(carta)  # l'ultima della lista è la cima
            _log(partita, giocatore, "in_cima", f"{giocatore} rimette una carta in cima al grimorio ({fonte})")
    elif azione == "tieni_pagando":
        modifica_vita(partita, giocatore, -4, f"({fonte}: tiene {carta.nome})")
    azioni_di_stato(partita)


def scegli_o_decidi(partita: Partita, giocatore: str, fonte: str, azione: str, candidate: list[Carta], testo: str,
                    seguito: tuple | None = None) -> None:
    """Una scelta tra carte: chi è in scelte_manuali risponde con «scelgo» (Scelta "scegli"); per gli altri decide
    l'AI (avversaria.scelta_automatica). Con una sola candidata non si chiede niente. `seguito` = (nome in
    carte_implementate.SEGUITI, argomenti...): l'effetto da riprendere dopo la scelta (Balance)."""
    if not candidate:
        _log(partita, giocatore, "nulla", f"{fonte}: nessuna carta da scegliere")
        return
    if len(candidate) == 1 or giocatore not in partita.scelte_manuali:
        from app.ai.avversaria import scelta_automatica
        carta = candidate[0] if len(candidate) == 1 else scelta_automatica(partita, giocatore, azione, candidate)
        _applica_scelta(partita, giocatore, azione, carta, fonte)
        _riprendi(partita, seguito)
        return
    partita.scelta = Scelta(giocatore, testo=testo, tipo="scegli",
                            dati={"carte": {c.id: c.nome for c in candidate}, "fonte": fonte, "azione": azione,
                                  "seguito": seguito})


def _riprendi(partita: Partita, seguito: tuple | None) -> None:
    if seguito:
        carte_implementate.SEGUITI[seguito[0]](partita, *seguito[1:])


def rispondi_scegli(partita: Partita, giocatore: str, id_carta: str) -> None:
    scelta = partita.scelta
    if scelta is None or scelta.tipo != "scegli":
        raise AzioneIllegale("ora non c'è da scegliere una carta")
    if scelta.giocatore != giocatore:
        raise AzioneIllegale(f"tocca a {scelta.giocatore} scegliere")
    if id_carta not in scelta.dati["carte"]:
        raise AzioneIllegale("non puoi scegliere quella carta")
    azione = scelta.dati["azione"]
    if ":" in id_carta:  # opzioni con l'azione dentro: «in_cima:<id>» / «tieni_pagando:<id>»
        azione, id_carta = id_carta.split(":", 1)
    carta = next(c for g in partita.giocatori for z in (Zona.CAMPO, Zona.MANO, Zona.CIMITERO) for c in g[z]
                 if c.id == id_carta)
    partita.scelta = None
    _applica_scelta(partita, giocatore, azione, carta, scelta.dati["fonte"])
    seguito = scelta.dati.get("seguito")
    if seguito and seguito[0] == "sylvan":
        seguito = (*seguito[:-1], seguito[-1] + (carta.id,))
    _riprendi(partita, seguito)
    partita.priorita = partita.attivo
    partita.passaggi = 0


def rispondi_cerca(partita: Partita, giocatore: str, id_carta: str) -> None:
    scelta = partita.scelta
    if scelta is None or scelta.tipo != "cerca":
        raise AzioneIllegale("ora non c'è da scegliere una carta dal grimorio")
    if scelta.giocatore != giocatore:
        raise AzioneIllegale(f"tocca a {scelta.giocatore} scegliere")
    carta = next((c for c in partita.giocatore(giocatore)[Zona.GRIMORIO] if c.id == id_carta), None)
    if carta is None:
        raise AzioneIllegale("quella carta non è nel tuo grimorio")
    partita.scelta = None
    _prendi_dal_grimorio(partita, giocatore, carta, scelta.dati["fonte"])
    partita.priorita = partita.attivo
    partita.passaggi = 0


def azioni_di_stato(partita: Partita) -> None:
    """Controlli automatici, ripetuti finché qualcosa cambia: aure senza creatura (o su una creatura protetta dal
    loro colore) al cimitero, creature con danni letali o costituzione 0 al cimitero. Ricalcola gli effetti statici."""
    for _ in range(20):
        statici.aggiorna(partita)
        if not _un_giro_di_controlli(partita):
            break
    controlla_sconfitte(partita)


def _un_giro_di_controlli(partita: Partita) -> bool:
    cambiato = False
    mondi = [c for g in partita.giocatori for c in g[Zona.CAMPO] if "World" in c.tipo]
    for vecchio in mondi[:-1] if len(mondi) > 1 else []:  # un solo incantesimo del mondo: resta il più recente
        recente = max(mondi, key=lambda c: c.entrata_nel_turno or 0)
        if vecchio is not recente:
            distruggi(partita, vecchio, "(c'è un altro incantesimo del mondo)", rigenerabile=False)
            cambiato = True
    for g in partita.giocatori:
        for c in list(g[Zona.CAMPO]):
            if c.is_aura:
                trovato = partita.trova_in_campo(c.attaccata_a) if c.attaccata_a else None
                if trovato is None or not trovato[1].is_creatura or trovato[1].protetta_da(c):
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
    if not partita.vincitore:
        controlla_sconfitte(partita)  # es. City of Brass tappata a 1 punto vita
        if partita.vincitore:
            return
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


def concedi(partita: Partita, giocatore: str) -> None:
    partita.vincitore = partita.avversario_di(giocatore).nome
    partita.scelta = None
    _log(partita, giocatore, "sconfitta", f"{giocatore} concede la partita")


def modifica_vita(partita: Partita, giocatore: str, delta: int, motivo: str = "", danno: bool = False) -> None:
    """danno=True per i danni veri (Ali from Cairo li ferma a 1 punto vita), False per perdite e guadagni di vita."""
    g = partita.giocatore(giocatore)
    if danno and delta < 0 and g.vita >= 1 and g.vita + delta < 1 and speciali.ali_protegge(partita, giocatore):
        delta = 1 - g.vita
        motivo = (motivo + " (Ali from Cairo: resta a 1)").strip()
    g.vita += delta
    _log(partita, giocatore, "vita", f"{giocatore} {delta:+d} vita ({g.vita}) {motivo}".strip())


def controlla_sconfitte(partita: Partita) -> None:
    """Azione di stato: perde chi è a 0 o meno punti vita o ha pescato da un grimorio vuoto. Si controlla dopo
    l'effetto intero, non a metà: se perdono tutti insieme (Earthquake, Timetwister) la partita è pari."""
    if partita.vincitore:
        return
    perdenti = [g for g in partita.giocatori if g.vita <= 0 or g.pescato_da_vuoto]
    for g in perdenti:
        motivo = f"è a {g.vita} punti vita" if g.vita <= 0 else "ha dovuto pescare da un grimorio vuoto"
        _log(partita, g.nome, "sconfitta", f"{g.nome} {motivo}")
    if len(perdenti) == len(partita.giocatori):
        partita.vincitore = PAREGGIO
        _log(partita, perdenti[0].nome, "pareggio", "Perdono entrambi: la partita è pari")
    elif perdenti:
        partita.vincitore = partita.avversario_di(perdenti[0].nome).nome
    if partita.vincitore:
        partita.scelta = None


def svuota_riserve(partita: Partita) -> None:
    """A fine fase le riserve si svuotano; con il mana burn (regola 93/94, opzione del formato) ogni mana
    inutilizzato fa perdere 1 vita."""
    for g in partita.giocatori:
        avanzato = sum(g.riserva.values())
        g.riserva = dict.fromkeys(g.riserva, 0)
        if avanzato and partita.mana_burn:
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
    controlla_sconfitte(partita)
    if partita.vincitore:
        return
    if partita.fase == ORDINE_FASI[-1] and _scarta_fino_a_sette(partita):
        return  # l'umano sceglie cosa scartare; dopo la scelta passa_fase riparte (SEGUITI["fine_turno"])
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
    # Nuovo turno (Time Walk: prima i turni extra)
    if partita.turni_extra:
        partita.attivo = [g.nome for g in partita.giocatori].index(partita.turni_extra.pop(0))
    else:
        partita.attivo = 1 - partita.attivo
    partita.priorita = partita.attivo
    partita.turno += 1
    partita.fase = Fase.STAP
    g = partita.giocatore_attivo
    g.terre_giocate_nel_turno = 0
    azioni_di_stato(partita)  # effetti che scadono a un certo turno (Erhnam Djinn), aure su una Factory tornata terra
    _log(partita, g.nome, "turno", f"Turno {partita.turno} di {g.nome}")
    _automatismi_fase(partita)


MANO_MASSIMA = 7


def _scarta_fino_a_sette(partita: Partita) -> bool:
    """A fine turno chi è di turno scarta fino ad avere 7 carte in mano. True se aspetta una scelta dell'umano."""
    g = partita.giocatore_attivo
    eccesso = len(g[Zona.MANO]) - MANO_MASSIMA
    if eccesso <= 0:
        return False
    if g.nome in partita.scelte_manuali:
        scegli_o_decidi(partita, g.nome, "fine turno", "scarta", list(g[Zona.MANO]),
                        f"Fine turno: hai {len(g[Zona.MANO])} carte in mano, scartane una (ancora {eccesso})",
                        seguito=("fine_turno",))
        return True
    from app.ai.avversaria import scelta_automatica
    for _ in range(eccesso):
        _applica_scelta(partita, g.nome, "scarta", scelta_automatica(partita, g.nome, "scarta", list(g[Zona.MANO])),
                        "fine turno: massimo 7 carte")
    return False


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
        controlla_sconfitte(partita)
        if not partita.vincitore:
            metti_inneschi(partita, "pescata")
    elif partita.fase in (Fase.PRINCIPALE_1, Fase.PRINCIPALE_2):
        # Mana Drain: alla prossima fase principale di chi l'ha lanciata (la 2 dello stesso turno, se era nella 1)
        for m in [m for m in partita.mana_ritardato if m[0] == g.nome and tuple(m[2:]) != (partita.turno, partita.fase)]:
            partita.mana_ritardato.remove(m)
            aggiungi_mana(partita, m[0], "C", m[1], "(Mana Drain)")
    elif partita.fase == Fase.FINALE:
        metti_inneschi(partita, "finale")
    elif partita.fase == Fase.COMBATTIMENTO:
        from app.engine import combattimento
        combattimento.inizia(partita)
