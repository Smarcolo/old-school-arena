"""Top 8 simulata: 7 mazzi di un torneo vero (da TCDecks) più il tuo al posto di uno di loro, poi quarti,
semifinali e finale, ogni turno al meglio di tre. Gli incontri tra mazzi dell'avversaria si giocano da soli;
i tuoi li giochi tu sul tavolo (un Incontro come gli altri)."""
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from app.incontro import Incontro, Lista
from app.simulazione import gioca_incontro_da_solo

TU = "Tu"
AVVERSARIA = "Avversaria"
# Tabellone classico: 1-8 e 4-5 nella metà alta, 2-7 e 3-6 in quella bassa
ACCOPPIAMENTI_QUARTI = [(1, 8), (4, 5), (2, 7), (3, 6)]
FASI = ["Quarti di finale", "Semifinali", "Finale"]


@dataclass
class Partecipante:
    posto: int  # piazzamento nel torneo vero (seed)
    nome: str  # nome del mazzo / archetipo
    giocatore: str
    lista: Lista
    umano: bool = False

    @property
    def etichetta(self) -> str:
        if self.umano:
            return f"Tu ({self.nome})"
        return f"#{self.posto} {self.nome}" + (f" ({self.giocatore})" if self.giocatore else "")


@dataclass
class Sfida:
    a: Partecipante
    b: Partecipante
    vincitore: Partecipante | None = None
    punteggio: str = ""
    id_incontro: str = ""  # per la sfida dell'umano

    @property
    def con_umano(self) -> bool:
        return self.a.umano or self.b.umano


@dataclass
class Torneo:
    nome: str
    partecipanti: list[Partecipante]
    costruisci: Callable
    opzioni: dict = field(default_factory=dict)
    info_carte: dict = field(default_factory=dict)
    seed: int | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turni: list[list[Sfida]] = field(default_factory=list)
    incontri: dict[str, Incontro] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        per_posto = {p.posto: p for p in self.partecipanti}
        self.turni = [[Sfida(per_posto[a], per_posto[b]) for a, b in ACCOPPIAMENTI_QUARTI]]
        self._simula_turno_corrente()

    @property
    def fase(self) -> str:
        return FASI[len(self.turni) - 1] if not self.campione else "Finito"

    @property
    def campione(self) -> Partecipante | None:
        ultimo = self.turni[-1]
        return ultimo[0].vincitore if len(ultimo) == 1 and ultimo[0].vincitore else None

    @property
    def umano_in_gara(self) -> bool:
        return any(s.con_umano and s.vincitore is None for s in self.turni[-1])

    def sfida_umano(self) -> Sfida | None:
        return next((s for s in self.turni[-1] if s.con_umano and s.vincitore is None), None)

    def _simula_turno_corrente(self) -> None:
        for sfida in self.turni[-1]:
            if sfida.vincitore is None and not sfida.con_umano:
                inc = Incontro([sfida.a.etichetta, sfida.b.etichetta],
                               {sfida.a.etichetta: sfida.a.lista, sfida.b.etichetta: sfida.b.lista},
                               self.costruisci, opzioni=self.opzioni, seed=self.rng.randrange(10**9))
                vincitore = gioca_incontro_da_solo(inc, self.info_carte)
                sfida.vincitore = sfida.a if vincitore == sfida.a.etichetta else sfida.b
                sfida.punteggio = f"{max(inc.vittorie.values())}-{min(inc.vittorie.values())}"
        self._avanza_se_finito()

    def _avanza_se_finito(self) -> None:
        turno = self.turni[-1]
        if any(s.vincitore is None for s in turno) or len(turno) == 1:
            return
        vincitori = [s.vincitore for s in turno]
        self.turni.append([Sfida(vincitori[i], vincitori[i + 1]) for i in range(0, len(vincitori), 2)])
        self._simula_turno_corrente()

    def crea_incontro_umano(self, scelte_manuali: set[str]) -> Incontro:
        """L'incontro (al meglio di tre) dell'umano nel turno in corso; lo stesso se è già stato creato."""
        sfida = self.sfida_umano()
        if sfida is None:
            raise ValueError("in questo turno non hai incontri da giocare")
        if sfida.id_incontro:
            return self.incontri[sfida.id_incontro]
        avversario = sfida.b if sfida.a.umano else sfida.a
        umano = sfida.a if sfida.a.umano else sfida.b
        inc = Incontro([TU, AVVERSARIA], {TU: umano.lista, AVVERSARIA: avversario.lista}, self.costruisci,
                       opzioni=self.opzioni, scelte_manuali=scelte_manuali, seed=self.rng.randrange(10**9))
        sfida.id_incontro = inc.id
        self.incontri[inc.id] = inc
        return inc

    def registra_incontro(self, inc: Incontro) -> None:
        """Da chiamare quando l'incontro dell'umano ha un vincitore: chiude la sfida e fa proseguire il torneo."""
        sfida = next((s for t in self.turni for s in t if s.id_incontro == inc.id), None)
        if sfida is None or sfida.vincitore or not inc.vincitore:
            return
        umano = sfida.a if sfida.a.umano else sfida.b
        sfida.vincitore = umano if inc.vincitore == TU else (sfida.b if sfida.a.umano else sfida.a)
        sfida.punteggio = f"{max(inc.vittorie.values())}-{min(inc.vittorie.values())}"
        self._avanza_se_finito()

    def stato(self) -> dict:
        return {
            "id": self.id, "nome": self.nome, "fase": self.fase,
            "campione": self.campione.etichetta if self.campione else None,
            "partecipanti": [{"posto": p.posto, "nome": p.etichetta, "umano": p.umano}
                             for p in sorted(self.partecipanti, key=lambda p: p.posto)],
            "turni": [{"fase": FASI[i], "sfide": [{
                "a": s.a.etichetta, "b": s.b.etichetta, "posti": [s.a.posto, s.b.posto],
                "vincitore": s.vincitore.etichetta if s.vincitore else None, "punteggio": s.punteggio,
                "con_umano": s.con_umano, "id_incontro": s.id_incontro} for s in turno]}
                for i, turno in enumerate(self.turni)],
            "da_giocare": bool(self.sfida_umano()),
        }
