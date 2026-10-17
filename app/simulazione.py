"""Partite e incontri giocati interamente dall'avversaria AI su entrambi i lati (per i tornei simulati)."""
from app.ai import avversaria
from app.ai.sideboard import scegli_cambi
from app.engine import mulligan
from app.engine.eventi import Evento
from app.engine.stato import Partita
from app.incontro import Incontro

MAX_PASSI = 30000


def gioca_da_sola(partita: Partita, max_passi: int = MAX_PASSI) -> str:
    """Fa giocare la partita all'AI per entrambi i giocatori fino alla fine. Se non finisce entro max_passi
    (stallo), vince chi ha più punti vita (a parità, chi ha più carte nel grimorio)."""
    for _ in range(max_passi):
        if partita.vincitore:
            return partita.vincitore
        if mulligan.in_corso(partita):
            nome = next(n for n, s in partita.mulligan.items() if not s.finito)
            avversaria.decidi_mulligan(partita, nome)
        elif partita.scelta:
            avversaria.decidi_scelta(partita, partita.scelta.giocatore)
        else:
            avversaria.agisci(partita, partita.giocatore_con_priorita.nome)
    from app.engine.zone import Zona
    a, b = partita.giocatori
    migliore = max((a, b), key=lambda g: (g.vita, len(g[Zona.GRIMORIO])))
    partita.vincitore = migliore.nome
    partita.registro.aggiungi(Evento(partita.turno, "fine", migliore.nome, "fine",
                                     f"Partita interrotta per stallo: vince {migliore.nome} ai punti vita"))
    return migliore.nome


def gioca_incontro_da_solo(inc: Incontro, info_carte: dict | None = None) -> str:
    """Gioca tutte le partite rimaste di un incontro AI contro AI (con sideboard tra una partita e l'altra)."""
    while True:
        gioca_da_sola(inc.partita)
        inc.registra_esito()
        if inc.vincitore:
            return inc.vincitore
        if info_carte is not None:
            for chi, avv in (inc.giocatori, reversed(inc.giocatori)):
                lista = inc.liste[chi]
                entra, esce = scegli_cambi(lista.sideboard, lista.mazzo, inc.viste[avv], info_carte)
                if entra:
                    inc.cambia_sideboard(chi, entra, esce)
        inc.prossima()
