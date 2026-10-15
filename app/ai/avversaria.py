"""Avversaria AI: nel suo turno gioca una terra e lancia la creatura più cara che può pagare, poi passa.
Fa una sola azione per chiamata; viene richiamata finché ha la priorità."""
from app.engine import azioni, mana
from app.engine.stato import Partita
from app.engine.validazione import puo_giocare_terra, puo_lanciare
from app.engine.zone import Zona


def agisci(partita: Partita, nome: str) -> None:
    g = partita.giocatore(nome)
    mano = list(g[Zona.MANO])
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
    azioni.passa_priorita(partita, nome)
