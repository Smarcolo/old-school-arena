"""Previsione: per le decisioni importanti (attaccanti e bloccanti) l'avversaria prova ogni alternativa su copie
della partita, le gioca qualche turno avanti con le sue regole normali per entrambi i giocatori e sceglie quella
che porta alla posizione migliore.

- Non bara: nelle copie le carte che non può conoscere (mano e grimorio dell'avversario, il suo grimorio) sono
  rimescolate, quindi prova mani possibili, non quella vera.
- Ogni alternativa si gioca PROVE volte con rimescolamenti diversi (gli stessi per tutte le alternative, così il
  confronto è alla pari), finché c'è tempo (LIMITE_SECONDI); a parità vince la scelta delle regole normali.
- Dentro le copie la previsione è spenta (`_in_corso`): le simulazioni usano solo le regole veloci. Spenta anche
  nelle partite AI contro AI dei tornei simulati (`spenta()` in simulazione.py).
"""
import copy
import math
import random
import time
from collections.abc import Callable
from contextlib import contextmanager

from app.engine import mulligan
from app.engine.eventi import RegistroEventi
from app.engine.stato import Partita
from app.engine.zone import Zona

PROVE = 6
LIMITE_SECONDI = 1.5  # sull'iPad il Python è più lento: oltre questo tempo si decide con le prove già fatte
TURNI_AVANTI = 2  # fino alla fine del proprio prossimo turno (attaccando) o del turno dopo (bloccando)
MAX_PASSI = 4000
ABILITATA = True  # spenta nei test (conftest) per tenerli veloci e indipendenti dai tempi
_in_corso = False


def attiva() -> bool:
    return ABILITATA and not _in_corso


@contextmanager
def spenta():
    """Partite AI contro AI (tornei simulati): solo le regole veloci."""
    global _in_corso
    prima, _in_corso = _in_corso, True
    try:
        yield
    finally:
        _in_corso = prima


def _copia(partita: Partita, nome: str, seme: int) -> Partita:
    registro, partita.registro = partita.registro, RegistroEventi()
    try:
        c = copy.deepcopy(partita)
    finally:
        partita.registro = registro
    rng = random.Random(seme)
    c.rng = random.Random(seme)
    c.scelte_manuali = set()
    io, avv = c.giocatore(nome), c.avversario_di(nome)
    nascoste = avv[Zona.MANO] + avv[Zona.GRIMORIO]
    rng.shuffle(nascoste)
    n = len(avv[Zona.MANO])
    avv[Zona.MANO][:], avv[Zona.GRIMORIO][:] = nascoste[:n], nascoste[n:]
    rng.shuffle(io[Zona.GRIMORIO])
    return c


def valuta(p: Partita, nome: str) -> float:
    """Da -1 (persa) a +1 (vinta): vita, creature in campo, carte in mano e terre."""
    if p.vincitore:
        return 1.0 if p.vincitore == nome else -1.0 if p.vincitore in {g.nome for g in p.giocatori} else 0.0

    def forza(g) -> float:
        campo = g[Zona.CAMPO]
        creature = sum(1.5 * (c.forza_attuale or 0) + 0.5 * (c.costituzione_attuale or 0) + 1
                       for c in campo if c.is_creatura)
        altri = sum(1.5 for c in campo if not c.is_creatura and not c.is_terra)
        terre = min(sum(1 for c in campo if c.is_terra), 7)
        return 0.6 * max(g.vita, 0) + creature + altri + 1.2 * len(g[Zona.MANO]) + terre
    io, avv = p.giocatore(nome), p.avversario_di(nome)
    return math.tanh((forza(io) - forza(avv)) / 15)


def _gioca_avanti(p: Partita, fino_al_turno: int) -> None:
    from app.ai import avversaria
    for _ in range(MAX_PASSI):
        if p.vincitore or p.turno > fino_al_turno:
            return
        if mulligan.in_corso(p):
            return
        if p.scelta:
            avversaria.decidi_scelta(p, p.scelta.giocatore)
        else:
            avversaria.agisci(p, p.giocatore_con_priorita.nome)


def migliore(partita: Partita, nome: str, opzioni: list, applica: Callable[[Partita, object], None]):
    """L'opzione con la media migliore. opzioni[0] è quella delle regole normali (vince a parità)."""
    global _in_corso
    if len(opzioni) < 2:
        return opzioni[0]
    semi = [partita.rng.randrange(1 << 30) for _ in range(PROVE)]
    fino = partita.turno + TURNI_AVANTI
    totali = [0.0] * len(opzioni)
    inizio = time.monotonic()
    _in_corso = True
    try:
        for n, seme in enumerate(semi):
            if n >= 2 and time.monotonic() - inizio > LIMITE_SECONDI:
                break
            for i, opzione in enumerate(opzioni):
                c = _copia(partita, nome, seme)
                applica(c, opzione)
                _gioca_avanti(c, fino)
                totali[i] += valuta(c, nome)
    finally:
        _in_corso = False
    migliore_punti = max(totali)
    if totali[0] >= migliore_punti - 1e-9:
        return opzioni[0]
    return opzioni[totali.index(migliore_punti)]
