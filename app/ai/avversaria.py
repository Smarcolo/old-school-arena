"""Avversaria AI. Fa una sola azione per chiamata e viene richiamata finché ha la priorità.

Priorità delle scelte:
1. Lightning Bolt su una creatura avversaria che muore con 3 danni (anche in risposta, es. a un Giant Growth).
2. Nel suo turno, fase principale, pila vuota: terra, poi la creatura più cara che può pagare.
3. Sempre nella sua fase principale: Lightning Bolt all'avversario se non ci sono creature da uccidere.
4. Altrimenti passa.
"""
from app.engine import azioni, mana
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


def agisci(partita: Partita, nome: str) -> None:
    g = partita.giocatore(nome)
    mano = list(g[Zona.MANO])

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
