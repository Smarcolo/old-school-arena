"""Avversaria AI, prima versione: gioca una terra se può e passa fino alla fine del suo turno."""
from app.engine import azioni
from app.engine.stato import Partita
from app.engine.validazione import puo_giocare_terra
from app.engine.zone import Zona


def gioca_turno(partita: Partita, nome: str) -> None:
    """Chiamata quando tocca all'AI: avanza le fasi finché il turno non torna all'umano."""
    while partita.giocatore_attivo.nome == nome and not partita.vincitore:
        g = partita.giocatore(nome)
        for carta in list(g[Zona.MANO]):
            if puo_giocare_terra(partita, nome, carta) is None:
                azioni.gioca_terra(partita, nome, carta)
                break
        azioni.passa_fase(partita)
