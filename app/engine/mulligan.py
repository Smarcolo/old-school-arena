"""Mulligan London: prima del primo turno ogni giocatore tiene la mano o la rimescola e ne pesca 7 nuove.
Quando tiene, mette in fondo al grimorio una carta per ogni mulligan fatto. Finché qualcuno non ha finito,
nessuno può fare altro (validazione._priorita)."""
from dataclasses import dataclass

from app.engine.eventi import Evento
from app.engine.stato import Carta, Partita
from app.engine.validazione import AzioneIllegale
from app.engine.zone import Zona

MANO = 7


@dataclass
class StatoMulligan:
    fatti: int = 0
    tenuta: bool = False
    da_mettere_in_fondo: int = 0

    @property
    def finito(self) -> bool:
        return self.tenuta and self.da_mettere_in_fondo == 0


def _log(partita: Partita, giocatore: str, descrizione: str) -> None:
    partita.registro.aggiungi(Evento(partita.turno, "mulligan", giocatore, "mulligan", descrizione))


def avvia(partita: Partita) -> None:
    partita.mulligan = {g.nome: StatoMulligan() for g in partita.giocatori}


def in_corso(partita: Partita) -> bool:
    return bool(partita.mulligan) and not all(s.finito for s in partita.mulligan.values())


def _stato(partita: Partita, giocatore: str) -> StatoMulligan:
    if not partita.mulligan or giocatore not in partita.mulligan:
        raise AzioneIllegale("ora non si fanno mulligan")
    return partita.mulligan[giocatore]


def fai_mulligan(partita: Partita, giocatore: str) -> None:
    stato = _stato(partita, giocatore)
    if stato.tenuta:
        raise AzioneIllegale("hai già tenuto la mano")
    if stato.fatti >= MANO:
        raise AzioneIllegale("non puoi fare altri mulligan")
    g = partita.giocatore(giocatore)
    g[Zona.GRIMORIO].extend(g[Zona.MANO])
    g[Zona.MANO].clear()
    partita.rng.shuffle(g[Zona.GRIMORIO])
    for _ in range(min(MANO, len(g[Zona.GRIMORIO]))):
        g[Zona.MANO].append(g[Zona.GRIMORIO].pop())
    stato.fatti += 1
    _log(partita, giocatore, f"{giocatore} fa mulligan ({stato.fatti})")


def tieni(partita: Partita, giocatore: str) -> None:
    stato = _stato(partita, giocatore)
    if stato.tenuta:
        raise AzioneIllegale("hai già tenuto la mano")
    stato.tenuta = True
    stato.da_mettere_in_fondo = min(stato.fatti, len(partita.giocatore(giocatore)[Zona.MANO]))
    n = stato.da_mettere_in_fondo
    extra = f": deve mettere in fondo {n} {'carta' if n == 1 else 'carte'}" if n else ""
    _log(partita, giocatore, f"{giocatore} tiene la mano{extra}")


def metti_in_fondo(partita: Partita, giocatore: str, carte: list[Carta]) -> None:
    stato = _stato(partita, giocatore)
    if not stato.tenuta or stato.da_mettere_in_fondo == 0:
        raise AzioneIllegale("non devi mettere carte in fondo al mazzo")
    if len(carte) != stato.da_mettere_in_fondo or len({c.id for c in carte}) != len(carte):
        raise AzioneIllegale(f"devi scegliere esattamente {stato.da_mettere_in_fondo} carte diverse")
    g = partita.giocatore(giocatore)
    if any(c not in g[Zona.MANO] for c in carte):
        raise AzioneIllegale("puoi mettere in fondo solo carte della tua mano")
    for c in carte:
        g[Zona.MANO].remove(c)
        g[Zona.GRIMORIO].insert(0, c)  # il fondo del grimorio è l'inizio della lista (si pesca dalla fine)
    stato.da_mettere_in_fondo = 0
    _log(partita, giocatore, f"{giocatore} mette {len(carte)} {'carta' if len(carte) == 1 else 'carte'} in fondo al mazzo")
