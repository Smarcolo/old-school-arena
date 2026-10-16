"""Stato della partita: giocatori, carte, zone, turno e fase."""
from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.engine.eventi import RegistroEventi
from app.engine.zone import Zona


# Parole chiave riconosciute nel testo Oracle (inglese, minuscolo) e come si dicono in italiano.
PAROLE_CHIAVE = {
    "flying": "volare", "reach": "raggiungere", "first strike": "attacca per primo", "trample": "travolgere",
    "vigilance": "cautela", "haste": "rapidità", "defender": "difensore", "banding": "banda",
}
_PASSATERRE = re.compile(r"^(plains|island|swamp|mountain|forest)walk$")
_PROTEZIONE = re.compile(r"^protection from (white|blue|black|red|green|artifacts)$")
COLORI_INGLESE = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
NOMI_COLORI = {"W": "bianco", "U": "blu", "B": "nero", "R": "rosso", "G": "verde", "A": "artefatti"}
PROTEZIONI_INGLESE = {**COLORI_INGLESE, "artifacts": "A"}  # "A" = protezione dagli artefatti


def parole_chiave_da_testo(testo: str) -> set[str]:
    """Una riga del testo Oracle fatta solo di parole chiave (es. "Flying, vigilance") le attiva tutte."""
    trovate: set[str] = set()
    for riga in testo.lower().splitlines():
        parti = [p.strip() for p in riga.split(",")]
        if parti and all(p in PAROLE_CHIAVE or _PASSATERRE.match(p) or _PROTEZIONE.match(p) for p in parti):
            trovate.update(parti)
    return trovate


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
    entrata_nel_turno: int | None = None  # per la debolezza da evocazione
    danni: int = 0  # danni subiti in questo turno
    bonus_forza: int = 0  # modifiche "fino alla fine del turno"
    bonus_costituzione: int = 0
    scudi_rigenerazione: int = 0  # fino a fine turno
    attaccata_a: str | None = None  # per le aure: id della creatura incantata
    statico_forza: int = 0  # da aure e incantesimi globali, ricalcolati da statici.aggiorna
    statico_costituzione: int = 0
    parole_extra: set[str] = field(default_factory=set)

    @property
    def forza_attuale(self) -> int:
        return (self.forza or 0) + self.bonus_forza + self.statico_forza

    @property
    def costituzione_attuale(self) -> int:
        return (self.costituzione or 0) + self.bonus_costituzione + self.statico_costituzione

    @property
    def is_aura(self) -> bool:
        return "Aura" in self.tipo

    def parole(self) -> set[str]:
        """Parole chiave dal testo più quelle date da aure e incantesimi."""
        return parole_chiave_da_testo(self.testo) | self.parole_extra

    def ha(self, parola_chiave: str) -> bool:
        return parola_chiave in self.parole()

    @property
    def colori(self) -> set[str]:
        """Colori della carta, dai simboli colorati del costo (le terre e gli artefatti sono incolori)."""
        return {c for c in "WUBRG" if f"{{{c}}}" in self.costo}

    @property
    def protezioni(self) -> set[str]:
        return {PROTEZIONI_INGLESE[m.group(1)] for p in self.parole() if (m := _PROTEZIONE.match(p))}

    @property
    def caratteristiche_protezione(self) -> set[str]:
        """Ciò da cui una protezione può proteggere contro questa carta: i suoi colori, più "A" se è un artefatto."""
        return self.colori | ({"A"} if "Artifact" in self.tipo else set())

    def protetta_da(self, fonte: "Carta | None") -> bool:
        return fonte is not None and bool(self.protezioni & fonte.caratteristiche_protezione)

    @property
    def passaterre(self) -> list[str]:
        """Tipi di terra della passaterre ("Forest" per forestwalk)."""
        return [p[:-4].capitalize() for p in self.parole() if _PASSATERRE.match(p)]

    def azzera_stato_in_campo(self) -> None:
        """Quando lascia il campo o a fine turno: niente danni né bonus."""
        self.danni = self.bonus_forza = self.bonus_costituzione = self.scudi_rigenerazione = 0

    @property
    def is_istantaneo(self) -> bool:
        return "Instant" in self.tipo

    @property
    def is_permanente(self) -> bool:
        return any(t in self.tipo for t in ("Creature", "Artifact", "Enchantment", "Land"))

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
    riserva: dict[str, int] = field(default_factory=lambda: dict.fromkeys("WUBRGC", 0))

    def __getitem__(self, zona: Zona) -> list[Carta]:
        return self.zone[zona]


@dataclass
class OggettoPila:
    carta: Carta
    controllore: str
    bersagli: list[str] = field(default_factory=list)  # "giocatore:<nome>" o "carta:<id>"
    abilita: object | None = None  # AbilitaAttivata se in pila c'è un'abilità e non la carta stessa
    innesco: object | None = None  # Innesco se in pila c'è un'abilità innescata
    giocatore_del_turno: str = ""  # per gli inneschi: «that player» = chi era di turno quando è scattato

    @property
    def descrizione(self) -> str:
        if self.innesco:
            return f"innesco di {self.carta.nome}"
        return f"abilità di {self.carta.nome}" if self.abilita else self.carta.nome


@dataclass
class Scelta:
    """Una decisione che blocca la partita finché il giocatore non risponde (es. «paga o subisci»)."""
    giocatore: str
    oggetto: OggettoPila
    costo: str
    testo: str


@dataclass
class Combattimento:
    """Stato della fase di combattimento in corso."""
    attaccanti: list[str] = field(default_factory=list)  # id delle creature attaccanti
    blocchi: dict[str, list[str]] = field(default_factory=dict)  # id attaccante -> id bloccanti, in ordine
    bande: list[list[str]] = field(default_factory=list)  # gruppi di attaccanti che attaccano in banda
    attaccanti_dichiarati: bool = False
    attesa_bloccanti: bool = False  # il difensore deve dichiarare i bloccanti
    bloccanti_dichiarati: bool = False
    danni_inflitti: bool = False

    def bloccanti(self) -> set[str]:
        return {b for lista in self.blocchi.values() for b in lista}

    def banda_di(self, id_attaccante: str) -> list[str]:
        return next((b for b in self.bande if id_attaccante in b), [id_attaccante])


@dataclass
class Partita:
    giocatori: list[Giocatore]
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    turno: int = 1
    attivo: int = 0
    fase: Fase = Fase.PRINCIPALE_1
    pila: list[OggettoPila] = field(default_factory=list)
    priorita: int = 0  # indice del giocatore che ha la priorità
    passaggi: int = 0  # passaggi consecutivi di priorità: a 2 si risolve la pila o si cambia fase
    registro: RegistroEventi = field(default_factory=RegistroEventi)
    vincitore: str | None = None
    combattimento: Combattimento | None = None
    scelta: Scelta | None = None

    @property
    def giocatore_attivo(self) -> Giocatore:
        return self.giocatori[self.attivo]

    @property
    def giocatore_con_priorita(self) -> Giocatore:
        return self.giocatori[self.priorita]

    def ha_debolezza_da_evocazione(self, carta: Carta) -> bool:
        """Una creatura entrata in questo turno non può attaccare né usare abilità con {T} (salvo rapidità)."""
        return carta.is_creatura and carta.entrata_nel_turno == self.turno and not carta.ha("haste")

    def giocatore(self, nome: str) -> Giocatore:
        for g in self.giocatori:
            if g.nome == nome:
                return g
        raise KeyError(nome)

    def avversario_di(self, nome: str) -> Giocatore:
        return next(g for g in self.giocatori if g.nome != nome)

    def trova_in_campo(self, id_carta: str) -> tuple[Giocatore, Carta] | None:
        for g in self.giocatori:
            for c in g[Zona.CAMPO]:
                if c.id == id_carta:
                    return g, c
        return None

    def risolvi_bersaglio(self, rif: str) -> Giocatore | Carta | None:
        """Da "giocatore:<nome>" o "carta:<id>" all'oggetto, se è ancora un bersaglio esistente."""
        tipo, _, valore = rif.partition(":")
        if tipo == "giocatore":
            return next((g for g in self.giocatori if g.nome == valore), None)
        trovato = self.trova_in_campo(valore)
        return trovato[1] if trovato else None


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
