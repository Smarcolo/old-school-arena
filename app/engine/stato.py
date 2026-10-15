"""Stato della partita: giocatori, carte, zone, turno e fase."""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.engine.eventi import RegistroEventi
from app.engine.zone import Zona


class Fase(str, Enum):
    # Struttura del turno nelle regole 93/94 (niente fase di cleanup separata).
    STAP = "stap"
    MANTENIMENTO = "mantenimento"
    PESCATA = "pescata"
    PRINCIPALE_1 = "principale 1"
    COMBATTIMENTO = "combattimento"
    PRINCIPALE_2 = "principale 2"
    FINALE = "finale"


ORDINE_FASI = list(Fase)


@dataclass
class Carta:
    nome: str
    tipo: str  # riga del tipo, es. "Creature — Bear", "Basic Land — Forest"
    costo: str = ""
    forza: int | None = None
    costituzione: int | None = None
    testo: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    tappata: bool = False
    proprietario: str = ""

    @property
    def is_terra(self) -> bool:
        return "Land" in self.tipo

    @property
    def is_creatura(self) -> bool:
        return "Creature" in self.tipo


@dataclass
class Giocatore:
    nome: str
    vita: int = 20
    zone: dict[Zona, list[Carta]] = field(default_factory=lambda: {z: [] for z in Zona if z != Zona.PILA})
    terre_giocate_nel_turno: int = 0

    def __getitem__(self, zona: Zona) -> list[Carta]:
        return self.zone[zona]


@dataclass
class Partita:
    giocatori: list[Giocatore]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turno: int = 1
    attivo: int = 0
    fase: Fase = Fase.PRINCIPALE_1
    pila: list[Carta] = field(default_factory=list)
    registro: RegistroEventi = field(default_factory=RegistroEventi)
    vincitore: str | None = None

    @property
    def giocatore_attivo(self) -> Giocatore:
        return self.giocatori[self.attivo]

    def giocatore(self, nome: str) -> Giocatore:
        for g in self.giocatori:
            if g.nome == nome:
                return g
        raise KeyError(nome)

    def avversario_di(self, nome: str) -> Giocatore:
        return next(g for g in self.giocatori if g.nome != nome)


def nuova_partita(mazzi: dict[str, list[Carta]], mano_iniziale: int = 7, seed: int | None = None) -> Partita:
    """Crea la partita, mescola i mazzi e pesca la mano iniziale. Il primo giocatore salta la pescata."""
    rng = random.Random(seed)
    giocatori = []
    for nome, mazzo in mazzi.items():
        g = Giocatore(nome=nome)
        carte = list(mazzo)
        rng.shuffle(carte)
        for c in carte:
            c.proprietario = nome
        g[Zona.GRIMORIO].extend(carte)
        for _ in range(mano_iniziale):
            g[Zona.MANO].append(g[Zona.GRIMORIO].pop())
        giocatori.append(g)
    return Partita(giocatori=giocatori)
