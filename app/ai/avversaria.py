"""Avversaria AI. Fa una sola azione per chiamata e viene richiamata finché ha la priorità.

Priorità delle scelte:
0. In combattimento: dichiara attaccanti e bloccanti quando tocca a lei.
1. Giant Growth per salvare una sua creatura (da un danno in pila o in combattimento) o per chiudere la partita.
2. Lightning Bolt o un'abilità di danno su una creatura avversaria che muore (anche in risposta).
3. Nel suo turno, fase principale, pila vuota: terra, poi la creatura più cara che può pagare.
4. Sempre nella sua fase principale: Lightning Bolt all'avversario se non ci sono creature da uccidere.
5. Dopo i blocchi: pompa gli attaccanti non bloccati (es. firebreathing) con il mana che ha.
6. Nella fase finale dell'avversario: abilità di danno a {T} rimaste stappate sull'avversario.
7. Altrimenti passa.
"""
from app.engine import azioni, combattimento, mana
from app.engine.abilita import analizza_abilita
from app.engine.inneschi import analizza_inneschi
from app.engine.stato import Carta, Fase, Partita
from app.engine.validazione import FASI_PRINCIPALI, puo_attivare, puo_giocare_terra, puo_lanciare
from app.engine.zone import Zona

DANNI_BOLT = 3


def _danni_oggetto(oggetto) -> int:
    """Danni che un oggetto in pila infliggerà al suo bersaglio (0 se non è un danno noto)."""
    if oggetto.abilita:
        return oggetto.abilita.danni if oggetto.abilita.tipo == "danno" else 0
    return DANNI_BOLT if oggetto.carta.nome == "Lightning Bolt" else 0


def _danni_in_arrivo(partita: Partita, nome: str, creatura: Carta) -> int:
    """Danni che le magie e abilità dell'AI già in pila stanno per infliggere a quella creatura."""
    return sum(_danni_oggetto(o) for o in partita.pila
               if o.controllore == nome and o.bersagli == [f"carta:{creatura.id}"])


def _vita(c: Carta) -> int:
    return c.costituzione_attuale - c.danni


def _danni_in_combattimento(partita: Partita, c: Carta) -> int:
    """Stima dei danni che c subirà in combattimento."""
    comb = partita.combattimento
    if c.id in comb.blocchi:
        return sum(t[1].forza_attuale for i in comb.blocchi[c.id] if (t := partita.trova_in_campo(i)))
    for attaccante, bloccanti in comb.blocchi.items():
        if c.id in bloccanti and (t := partita.trova_in_campo(attaccante)):
            return t[1].forza_attuale
    return 0


def bersaglio_growth(partita: Partita, nome: str) -> Carta | None:
    """Creatura dell'AI da salvare (o con cui chiudere la partita) con +3/+3, se c'è."""
    mie = [c for c in partita.giocatore(nome)[Zona.CAMPO] if c.is_creatura]
    if partita.pila:
        cima = partita.pila[-1]
        if cima.controllore != nome and cima.bersagli:
            bersaglio = partita.risolvi_bersaglio(cima.bersagli[0])
            danni = _danni_oggetto(cima)
            if bersaglio in mie and _vita(bersaglio) <= danni < _vita(bersaglio) + 3:
                return bersaglio
        return None
    comb = partita.combattimento
    if not comb or not comb.bloccanti_dichiarati or comb.danni_inflitti:
        return None
    in_combattimento = set(comb.attaccanti) | comb.bloccanti()
    for c in mie:
        if c.id in in_combattimento and _vita(c) <= _danni_in_combattimento(partita, c) < _vita(c) + 3:
            return c
    if partita.giocatore_attivo.nome == nome:
        avversario = partita.avversario_di(nome)
        liberi = [t[1] for i in comb.attaccanti if i not in comb.blocchi and (t := partita.trova_in_campo(i))]
        if liberi and sum(c.forza_attuale for c in liberi) < avversario.vita <= sum(c.forza_attuale for c in liberi) + 3:
            return liberi[0]
    return None


def bersaglio_bolt(partita: Partita, nome: str) -> str | None:
    avversario = partita.avversario_di(nome)
    if migliore := _creatura_uccidibile(partita, nome, DANNI_BOLT):
        return f"carta:{migliore.id}"
    if not partita.pila and partita.giocatore_attivo.nome == nome and partita.fase in FASI_PRINCIPALI:
        return f"giocatore:{avversario.nome}"
    return None


def decidi_scelta(partita: Partita, nome: str) -> None:
    """«Paga o subisci»: paga se può."""
    azioni.rispondi_scelta(partita, nome, azioni.puo_pagare_scelta(partita))


def _muore_a_fine_turno(c: Carta) -> bool:
    return any(i.momento == "finale" and i.effetto == "sacrifica" for i in analizza_inneschi(c))


def scegli_attaccanti(partita: Partita, nome: str) -> list[Carta]:
    """Attacca con ogni creatura che nessun bloccante possibile ucciderebbe senza morire a sua volta.
    Chi verrà sacrificato a fine turno (es. Ball Lightning) attacca sempre."""
    avversario = partita.avversario_di(nome).nome
    difensori = combattimento.possibili_bloccanti(partita, avversario)
    scelti = []
    for a in combattimento.possibili_attaccanti(partita, nome):
        possibili = [b for b in difensori if combattimento.puo_bloccare_contro(partita, avversario, b, a) is None]
        cattivo_scambio = any(b.forza_attuale >= a.costituzione_attuale - a.danni
                              and a.forza_attuale < b.costituzione_attuale - b.danni for b in possibili)
        if not cattivo_scambio or _muore_a_fine_turno(a):
            scelti.append(a)
    return scelti


def scegli_bloccanti(partita: Partita, nome: str) -> list[tuple[Carta, Carta]]:
    """Per ogni attaccante (dal più forte): blocca uccidendolo e sopravvivendo, altrimenti sopravvivendo,
    altrimenti scambiando alla pari o in meglio. Se i danni in arrivo la ucciderebbero, blocca comunque
    con la creatura più piccola."""
    disponibili = combattimento.possibili_bloccanti(partita, nome)
    attaccanti = sorted(combattimento.attaccanti_in_campo(partita), key=lambda c: -c.forza_attuale)
    blocchi = []

    def vita(c):
        return c.costituzione_attuale - c.danni

    def legali(a):
        return [b for b in disponibili if combattimento.puo_bloccare_contro(partita, nome, b, a) is None]

    for a in attaccanti:
        uccide = [b for b in legali(a) if b.forza_attuale >= vita(a)]
        sopravvive = [b for b in legali(a) if vita(b) > a.forza_attuale]
        scelta = (next((b for b in uccide if b in sopravvive), None)
                  or (min(sopravvive, key=lambda b: b.forza_attuale) if sopravvive else None)
                  or next((b for b in uccide if b.forza_attuale <= a.forza_attuale), None))
        if scelta:
            blocchi.append((scelta, a))
            disponibili.remove(scelta)
    bloccati = {a.id for _, a in blocchi}
    liberi = [a for a in attaccanti if a.id not in bloccati]
    if sum(a.forza_attuale for a in liberi) >= partita.giocatore(nome).vita:
        for a in liberi:
            if not legali(a):
                continue
            piccola = min(legali(a), key=lambda b: b.forza_attuale)
            blocchi.append((piccola, a))
            disponibili.remove(piccola)
    return blocchi


def _abilita_pronte(partita: Partita, nome: str, tipo: str) -> list[tuple[Carta, object]]:
    return [(c, ab) for c in partita.giocatore(nome)[Zona.CAMPO] for ab in analizza_abilita(c)
            if ab.tipo == tipo and puo_attivare(partita, nome, c, ab) is None]


def _creatura_uccidibile(partita: Partita, nome: str, danni: int) -> Carta | None:
    avversario = partita.avversario_di(nome)
    uccidibili = [c for c in avversario[Zona.CAMPO] if c.is_creatura
                  and 0 < _vita(c) - _danni_in_arrivo(partita, nome, c) <= danni]
    return max(uccidibili, key=lambda c: (c.forza_attuale, c.costituzione_attuale)) if uccidibili else None


def agisci(partita: Partita, nome: str) -> None:
    g = partita.giocatore(nome)
    mano = list(g[Zona.MANO])
    avversario = partita.avversario_di(nome).nome

    if combattimento.deve_dichiarare_bloccanti(partita, nome):
        combattimento.dichiara_bloccanti(partita, nome, scegli_bloccanti(partita, nome))
        return
    if combattimento.deve_dichiarare_attaccanti(partita, nome):
        combattimento.dichiara_attaccanti(partita, nome, scegli_attaccanti(partita, nome))
        return

    growth = next((c for c in mano if c.nome == "Giant Growth" and puo_lanciare(partita, nome, c) is None), None)
    if growth and (da_salvare := bersaglio_growth(partita, nome)):
        azioni.lancia(partita, nome, growth, [f"carta:{da_salvare.id}"])
        return

    for fonte, ab in _abilita_pronte(partita, nome, "danno"):
        if ab.bersaglio in ("qualsiasi", "creatura") and (vittima := _creatura_uccidibile(partita, nome, ab.danni)):
            azioni.attiva(partita, nome, fonte, ab, [f"carta:{vittima.id}"])
            return

    bolt = next((c for c in mano if c.nome == "Lightning Bolt" and puo_lanciare(partita, nome, c) is None), None)
    if bolt:
        rif = bersaglio_bolt(partita, nome)
        if rif and rif.startswith("carta:"):
            azioni.lancia(partita, nome, bolt, [rif])
            return

    if partita.giocatore_attivo.nome == nome and not partita.pila:
        terra = next((c for c in mano if puo_giocare_terra(partita, nome, c) is None), None)
        if terra:
            azioni.gioca_terra(partita, nome, terra)
            return
        lanciabili = [c for c in mano if c.is_creatura and puo_lanciare(partita, nome, c) is None]
        if not lanciabili:  # poi gli altri permanenti (artefatti, incantesimi)
            lanciabili = [c for c in mano if c.is_permanente and not c.is_terra and puo_lanciare(partita, nome, c) is None]
        if lanciabili:
            piu_cara = max(lanciabili, key=lambda c: sum(mana.analizza_costo(c.costo).values()))
            azioni.lancia(partita, nome, piu_cara)
            return
        if bolt and (rif := bersaglio_bolt(partita, nome)):
            azioni.lancia(partita, nome, bolt, [rif])
            return

    comb = partita.combattimento
    solo_miei_pompaggi = all(o.controllore == nome and o.abilita and o.abilita.tipo == "pompa" for o in partita.pila)
    if (comb and comb.bloccanti_dichiarati and not comb.danni_inflitti and solo_miei_pompaggi
            and partita.giocatore_attivo.nome == nome):
        for fonte, ab in _abilita_pronte(partita, nome, "pompa"):
            if fonte.id in comb.attaccanti and fonte.id not in comb.blocchi and ab.forza > 0:
                azioni.attiva(partita, nome, fonte, ab)
                return

    if not partita.pila and partita.fase == Fase.FINALE and partita.giocatore_attivo.nome == avversario:
        for fonte, ab in _abilita_pronte(partita, nome, "danno"):
            if ab.tappa and ab.bersaglio in ("qualsiasi", "giocatore"):
                azioni.attiva(partita, nome, fonte, ab, [f"giocatore:{avversario}"])
                return

    azioni.passa_priorita(partita, nome)
