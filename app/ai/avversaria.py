"""Avversaria AI. Fa una sola azione per chiamata e viene richiamata finché ha la priorità.

Priorità delle scelte:
0. In combattimento: dichiara attaccanti e bloccanti quando tocca a lei.
1. Lightning Bolt su una creatura avversaria che muore con 3 danni (anche in risposta, es. a un Giant Growth).
2. Nel suo turno, fase principale, pila vuota: terra, poi la creatura più cara che può pagare.
3. Sempre nella sua fase principale: Lightning Bolt all'avversario se non ci sono creature da uccidere.
4. Altrimenti passa.
"""
from app.engine import azioni, combattimento, mana
from app.engine.stato import Carta, Partita
from app.engine.validazione import FASI_PRINCIPALI, puo_giocare_terra, puo_lanciare
from app.engine.zone import Zona

DANNI_BOLT = 3


def _danni_in_arrivo(partita: Partita, nome: str, creatura: Carta) -> int:
    """Danni che le magie dell'AI già in pila stanno per infliggere a quella creatura."""
    return sum(DANNI_BOLT for o in partita.pila
               if o.controllore == nome and o.carta.nome == "Lightning Bolt" and o.bersagli == [f"carta:{creatura.id}"])


def bersaglio_bolt(partita: Partita, nome: str) -> str | None:
    avversario = partita.avversario_di(nome)
    uccidibili = [c for c in avversario[Zona.CAMPO] if c.is_creatura
                  and 0 < c.costituzione_attuale - c.danni - _danni_in_arrivo(partita, nome, c) <= DANNI_BOLT]
    if uccidibili:
        migliore = max(uccidibili, key=lambda c: (c.forza_attuale, c.costituzione_attuale))
        return f"carta:{migliore.id}"
    if not partita.pila and partita.giocatore_attivo.nome == nome and partita.fase in FASI_PRINCIPALI:
        return f"giocatore:{avversario.nome}"
    return None


def scegli_attaccanti(partita: Partita, nome: str) -> list[Carta]:
    """Attacca con ogni creatura che nessun bloccante possibile ucciderebbe senza morire a sua volta."""
    difensori = combattimento.possibili_bloccanti(partita, partita.avversario_di(nome).nome)
    scelti = []
    for a in combattimento.possibili_attaccanti(partita, nome):
        cattivo_scambio = any(b.forza_attuale >= a.costituzione_attuale - a.danni
                              and a.forza_attuale < b.costituzione_attuale - b.danni for b in difensori)
        if not cattivo_scambio:
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

    for a in attaccanti:
        uccide = [b for b in disponibili if b.forza_attuale >= vita(a)]
        sopravvive = [b for b in disponibili if vita(b) > a.forza_attuale]
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
            if not disponibili:
                break
            piccola = min(disponibili, key=lambda b: b.forza_attuale)
            blocchi.append((piccola, a))
            disponibili.remove(piccola)
    return blocchi


def agisci(partita: Partita, nome: str) -> None:
    g = partita.giocatore(nome)
    mano = list(g[Zona.MANO])

    if combattimento.deve_dichiarare_bloccanti(partita, nome):
        combattimento.dichiara_bloccanti(partita, nome, scegli_bloccanti(partita, nome))
        return
    if combattimento.deve_dichiarare_attaccanti(partita, nome):
        combattimento.dichiara_attaccanti(partita, nome, scegli_attaccanti(partita, nome))
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
        if lanciabili:
            piu_cara = max(lanciabili, key=lambda c: sum(mana.analizza_costo(c.costo).values()))
            azioni.lancia(partita, nome, piu_cara)
            return
        if bolt and (rif := bersaglio_bolt(partita, nome)):
            azioni.lancia(partita, nome, bolt, [rif])
            return

    azioni.passa_priorita(partita, nome)
