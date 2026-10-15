"""Event log: ogni cambiamento di stato lascia una riga leggibile, in ordine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Evento:
    turno: int
    fase: str
    giocatore: str
    tipo: str
    descrizione: str
    dati: dict[str, Any] = field(default_factory=dict)
    quando: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RegistroEventi:
    def __init__(self) -> None:
        self.eventi: list[Evento] = []

    def aggiungi(self, evento: Evento) -> Evento:
        self.eventi.append(evento)
        return evento

    def ultimi(self, n: int = 20) -> list[Evento]:
        return self.eventi[-n:]
