"""Incontro al meglio di tre partite (regola del torneo): nella prima chi inizia si decide lanciando una moneta,
nelle successive inizia chi ha perso la partita precedente. Vince l'incontro chi vince due partite.
Tra una partita e l'altra ogni giocatore può scambiare carte tra mazzo e sideboard (uno per uno)."""
import random
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from app.engine.eventi import Evento
from app.engine.stato import PAREGGIO, Carta, Partita, nuova_partita
from app.engine.zone import Zona

PARTITE_PER_VINCERE = 2


@dataclass
class Lista:
    mazzo: dict[str, int]
    sideboard: dict[str, int] = field(default_factory=dict)


@dataclass
class Incontro:
    giocatori: list[str]
    liste: dict[str, Lista]  # mazzo e sideboard attuali di ogni giocatore
    costruisci: Callable[[dict[str, int]], list[Carta]]  # da {nome: copie} a carte nuove
    opzioni: dict = field(default_factory=dict)  # mana_burn, mulligan
    scelte_manuali: set[str] = field(default_factory=set)
    seed: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    vittorie: dict[str, int] = field(default_factory=dict)
    esiti: list[str] = field(default_factory=list)  # vincitore di ogni partita finita
    partita: Partita | None = None
    lancio_moneta: str = ""
    numero: int = 0  # numero della partita in corso (1, 2, 3)
    viste: dict[str, Counter] = field(default_factory=dict)  # carte giocate da ciascuno, viste dall'avversario
    avversaria: str = ""  # nome del mazzo dell'avversaria, per l'interfaccia e i salvataggi
    torneo: str = ""  # id del torneo di cui fa parte, se c'è
    primo: str = ""  # chi ha iniziato la partita in corso

    def __post_init__(self) -> None:
        # copie: la sideboard di questo incontro non deve cambiare la lista di partenza (torneo: turno successivo)
        self.liste = {g: Lista(dict(l.mazzo), dict(l.sideboard)) for g, l in self.liste.items()}
        self.rng = random.Random(self.seed)
        self.vittorie = {g: 0 for g in self.giocatori}
        self.viste = {g: Counter() for g in self.giocatori}
        self.lancio_moneta = self.rng.choice(self.giocatori)
        self._nuova_partita(self.lancio_moneta, f"Lancio della moneta: inizia {self.lancio_moneta}")

    def _nuova_partita(self, primo: str, motivo: str) -> None:
        self.numero += 1
        self.primo = primo
        mazzi = {g: self.costruisci(self.liste[g].mazzo) for g in self.giocatori}
        self.partita = nuova_partita(mazzi, primo=primo, seed=self.rng.randrange(10**9), **self.opzioni)
        self.partita.scelte_manuali = set(self.scelte_manuali)
        self.partita.registro.aggiungi(Evento(1, "inizio", primo, "inizio",
                                              f"Partita {self.numero} dell'incontro. {motivo}"))

    @property
    def vincitore(self) -> str | None:
        return next((g for g, v in self.vittorie.items() if v >= PARTITE_PER_VINCERE), None)

    def registra_esito(self) -> None:
        """Da chiamare dopo ogni mossa: conta la partita appena finita (una volta sola) e ricorda le carte viste."""
        p = self.partita
        if p and p.vincitore and len(self.esiti) < self.numero:
            self.esiti.append(p.vincitore)
            if p.vincitore != PAREGGIO:  # una partita pari non conta: se ne gioca un'altra
                self.vittorie[p.vincitore] += 1
            for g in p.giocatori:
                for zona in (Zona.CAMPO, Zona.CIMITERO, Zona.RIMOSSE):
                    self.viste[g.nome].update(c.nome for c in g[zona] if c.proprietario in ("", g.nome))

    def cambia_sideboard(self, giocatore: str, entra: dict[str, int], esce: dict[str, int]) -> None:
        """Scambi uno per uno tra sideboard (entra) e mazzo (esce), solo tra una partita e l'altra."""
        if self.partita is None or not self.partita.vincitore or self.vincitore:
            raise ValueError("la sideboard si cambia solo tra una partita e l'altra dell'incontro")
        entra = {n: q for n, q in entra.items() if q > 0}
        esce = {n: q for n, q in esce.items() if q > 0}
        if sum(entra.values()) != sum(esce.values()):
            raise ValueError("devi togliere dal mazzo tante carte quante ne metti dalla sideboard")
        lista = self.liste[giocatore]
        mazzo, side = Counter(lista.mazzo), Counter(lista.sideboard)
        for nome, q in entra.items():
            if side[nome] < q:
                raise ValueError(f"in sideboard non hai {q} {nome}")
        for nome, q in esce.items():
            if mazzo[nome] < q:
                raise ValueError(f"nel mazzo non hai {q} {nome}")
        mazzo.update(entra), side.subtract(entra), side.update(esce), mazzo.subtract(esce)
        lista.mazzo = {n: q for n, q in mazzo.items() if q > 0}
        lista.sideboard = {n: q for n, q in side.items() if q > 0}

    def prossima(self) -> None:
        if self.partita is None or not self.partita.vincitore:
            raise ValueError("la partita in corso non è ancora finita")
        if self.vincitore:
            raise ValueError(f"l'incontro è finito: ha vinto {self.vincitore}")
        if self.esiti[-1] == PAREGGIO:
            self._nuova_partita(self.primo, f"La partita precedente è finita pari: inizia di nuovo {self.primo}")
            return
        perdente = next(g for g in self.giocatori if g != self.esiti[-1])
        self._nuova_partita(perdente, f"Inizia {perdente}, che ha perso la partita precedente")
