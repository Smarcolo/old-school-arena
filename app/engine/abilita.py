"""Abilità attivate lette dal testo Oracle (NAME = nome della carta, o «this creature»). Costi: simboli di mana,
{T}, «Sacrifice NAME», «Sacrifice an artifact» / «Sacrifice a creature». Effetti riconosciuti:

- «NAME gets +X/+Y until end of turn.» (anche «Enchanted creature gets...» sulle aure)  -> pompa
- «NAME deals N damage to any target / target creature / target player.»                 -> danno
- «Regenerate NAME.»                                                                     -> rigenera
- «Destroy target land / artifact / creature / artifact or enchantment.»                 -> distruggi
- «Draw a card.» (+ «Activate only if you have exactly seven cards in your hand.»)       -> pesca
- «Tap target artifact, creature, or land.»                                              -> tappa

Le abilità di mana («...: Add ...») stanno in mana.py e non usano la pila.
"""
import re
from dataclasses import dataclass

from app.engine.stato import Carta

_PARTE = r"(?:\{[^}]+\}|Sacrifice [^:,]+|Remove a \+1/\+1 counter from [^:,]+)"
_RIGA = re.compile(rf"^(?P<costo>{_PARTE}(?:, {_PARTE})*):\s*(?P<effetto>.+)$")
_POMPA = re.compile(r"^(?P<nome>.+) gets (?P<f>[+-]\d+)/(?P<c>[+-]\d+) until end of turn\.$")
_DANNO = re.compile(r"^(?P<nome>.+) deals (?P<n>\d+) damage to (?P<bersaglio>any target|target creature|target player)\.$")
_RIGENERA = re.compile(r"^Regenerate (?P<nome>.+)\.$")
_DISTRUGGI = re.compile(r"^Destroy target (?P<cosa>land|artifact|creature|artifact or enchantment)\.$")
_PESCA = re.compile(r"^Draw a card\.(?P<sette> Activate only if you have exactly seven cards in your hand\.)?$")
_TAPPA = re.compile(r"^Tap target artifact, creature, or land\.$")
_ANIMA = re.compile(r"^(?P<nome>.+) becomes an? (?P<f>\d+)/(?P<c>\d+) (?P<tipi>[A-Za-z\- ]+?) creature until end of turn\. It's still a land\.$")
_POMPA_BERSAGLIO = re.compile(r"^Target Assembly-Worker creature gets (?P<f>[+-]\d+)/(?P<c>[+-]\d+) until end of turn\.$")
_SCARTA = re.compile(r"^Target player discards a card\.(?P<turno> Activate only during your turn\.)?$")
_BERSAGLI = {"any target": "qualsiasi", "target creature": "creatura", "target player": "giocatore"}
_DISTRUGGIBILI = {"land": "terra", "artifact": "artefatto", "creature": "creatura",
                  "artifact or enchantment": "artefatto_o_incantesimo"}


@dataclass
class AbilitaAttivata:
    indice: int  # posizione tra le abilità attivate della carta
    testo: str
    costo_mana: str  # es. "{R}" o "" se costa solo {T}
    tappa: bool
    tipo: str  # "pompa", "danno", "rigenera", "distruggi", "pesca", "tappa"
    forza: int = 0
    costituzione: int = 0
    danni: int = 0
    bersaglio: str | None = None
    su_incantata: bool = False  # abilità di un'aura che pompa la creatura incantata (es. Firebreathing)
    sacrifica_se: bool = False  # «Sacrifice NAME» nel costo
    sacrifica_tipo: str = ""  # "artefatto" / "creatura" per «Sacrifice an artifact / a creature»
    solo_con_sette: bool = False  # Library of Alexandria
    solo_nel_tuo_turno: bool = False  # Disrupting Scepter
    togli_segnalino: bool = False  # «Remove a +1/+1 counter from NAME» (Triskelion)
    tipo_animato: str = ""  # per «anima»: es. "Artifact Creature — Assembly-Worker"


def _di_se_stessa(nome_nel_testo: str, carta: Carta) -> bool:
    return nome_nel_testo.lower() in (carta.nome.lower(), "this creature", "cardname", "~", "it")


def analizza_abilita(carta: Carta) -> list[AbilitaAttivata]:
    trovate = []
    for riga in carta.testo.splitlines():
        riga = riga.strip()
        m = _RIGA.match(riga)
        if not m or m["effetto"].startswith("Add "):
            continue
        parti = [p.strip() for p in m["costo"].split(",")]
        simboli = [p for p in parti if p.startswith("{")]
        sacrifici = [p.removeprefix("Sacrifice ").strip() for p in parti if p.startswith("Sacrifice ")]
        togli_segnalino = any(p.startswith("Remove a +1/+1 counter from ") and _di_se_stessa(p.removeprefix(
            "Remove a +1/+1 counter from "), carta) for p in parti)
        sacrifica_se = any(_di_se_stessa(s, carta) for s in sacrifici)
        sacrifica_tipo = next(({"an artifact": "artefatto", "a creature": "creatura"}[s] for s in sacrifici
                               if s in ("an artifact", "a creature")), "")
        if len(sacrifici) != int(sacrifica_se) + int(bool(sacrifica_tipo)):
            continue  # un sacrificio che non sappiamo pagare
        base = dict(indice=len(trovate), testo=riga, costo_mana="".join(s for s in simboli if s != "{T}"),
                    tappa="{T}" in simboli, sacrifica_se=sacrifica_se, sacrifica_tipo=sacrifica_tipo,
                    togli_segnalino=togli_segnalino)
        effetto = m["effetto"].strip()
        if (p := _POMPA.match(effetto)) and _di_se_stessa(p["nome"], carta):
            trovate.append(AbilitaAttivata(**base, tipo="pompa", forza=int(p["f"]), costituzione=int(p["c"])))
        elif p and p["nome"].lower() == "enchanted creature" and carta.is_aura:
            trovate.append(AbilitaAttivata(**base, tipo="pompa", forza=int(p["f"]), costituzione=int(p["c"]), su_incantata=True))
        elif (r := _RIGENERA.match(effetto)) and _di_se_stessa(r["nome"], carta):
            trovate.append(AbilitaAttivata(**base, tipo="rigenera"))
        elif (d := _DANNO.match(effetto)) and _di_se_stessa(d["nome"], carta):
            trovate.append(AbilitaAttivata(**base, tipo="danno", danni=int(d["n"]), bersaglio=_BERSAGLI[d["bersaglio"]]))
        elif d := _DISTRUGGI.match(effetto):
            trovate.append(AbilitaAttivata(**base, tipo="distruggi", bersaglio=_DISTRUGGIBILI[d["cosa"]]))
        elif pe := _PESCA.match(effetto):
            trovate.append(AbilitaAttivata(**base, tipo="pesca", solo_con_sette=bool(pe["sette"])))
        elif _TAPPA.match(effetto):
            trovate.append(AbilitaAttivata(**base, tipo="tappa", bersaglio="artefatto_creatura_o_terra"))
        elif (an := _ANIMA.match(effetto)) and _di_se_stessa(an["nome"], carta):
            tipi = an["tipi"].split()
            sottotipo = " ".join(t for t in tipi if t not in ("artifact", "Artifact"))
            tipo = ("Artifact " if any(t.lower() == "artifact" for t in tipi) else "") + f"Creature — {sottotipo}"
            trovate.append(AbilitaAttivata(**base, tipo="anima", forza=int(an["f"]), costituzione=int(an["c"]), tipo_animato=tipo))
        elif pb := _POMPA_BERSAGLIO.match(effetto):
            trovate.append(AbilitaAttivata(**base, tipo="pompa_bersaglio", forza=int(pb["f"]), costituzione=int(pb["c"]),
                                           bersaglio="assembly_worker"))
        elif sc := _SCARTA.match(effetto):
            trovate.append(AbilitaAttivata(**base, tipo="scarta", bersaglio="giocatore", solo_nel_tuo_turno=bool(sc["turno"])))
    return trovate


def riga_capita(carta: Carta, riga: str) -> bool:
    """True se la riga di testo è un'abilità attivata che il motore sa usare."""
    return any(a.testo == riga.strip() for a in analizza_abilita(carta))
