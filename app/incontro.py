"""Incontro al meglio di tre partite (regola del torneo): nella prima chi inizia si decide lanciando una moneta,
nelle successive inizia chi ha perso la partita precedente. Vince l'incontro chi vince due partite."""
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from app.engine.eventi import Evento
from app.engine.stato import Carta, Partita, nuova_partita

PARTITE_PER_VINCERE = 2


@dataclass
class Incontro:
    giocatori: list[str]
    crea_mazzi: Callable[[], dict[str, list[Carta]]]  # mazzi nuovi (carte nuove) a ogni partita
    opzioni: dict = field(default_factory=dict)  # mana_burn, mulligan
    scelte_manuali: set[str] = field(default_factory=set)
    seed: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    vittorie: dict[str, int] = field(default_factory=dict)
    esiti: list[str] = field(default_factory=list)  # vincitore di ogni partita finita
    partita: Partita | None = None
    lancio_moneta: str = ""
    numero: int = 0  # numero della partita in corso (1, 2, 3)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.vittorie = {g: 0 for g in self.giocatori}
        self.lancio_moneta = self.rng.choice(self.giocatori)
        self._nuova_partita(self.lancio_moneta, f"Lancio della moneta: inizia {self.lancio_moneta}")

    def _nuova_partita(self, primo: str, motivo: str) -> None:
        self.numero += 1
        self.partita = nuova_partita(self.crea_mazzi(), primo=primo, seed=self.rng.randrange(10**9), **self.opzioni)
        self.partita.scelte_manuali = set(self.scelte_manuali)
        self.partita.registro.aggiungi(Evento(1, "inizio", primo, "inizio",
                                              f"Partita {self.numero} dell'incontro. {motivo}"))

    @property
    def vincitore(self) -> str | None:
        return next((g for g, v in self.vittorie.items() if v >= PARTITE_PER_VINCERE), None)

    def registra_esito(self) -> None:
        """Da chiamare dopo ogni mossa: conta la partita appena finita (una volta sola)."""
        p = self.partita
        if p and p.vincitore and len(self.esiti) < self.numero:
            self.esiti.append(p.vincitore)
            self.vittorie[p.vincitore] += 1

    def prossima(self) -> None:
        if self.partita is None or not self.partita.vincitore:
            raise ValueError("la partita in corso non è ancora finita")
        if self.vincitore:
            raise ValueError(f"l'incontro è finito: ha vinto {self.vincitore}")
        perdente = next(g for g in self.giocatori if g != self.esiti[-1])
        self._nuova_partita(perdente, f"Inizia {perdente}, che ha perso la partita precedente")
