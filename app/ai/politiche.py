"""Quando e su cosa l'avversaria lancia le magie (e usa le abilità) diverse da creature, terre e Lightning Bolt.
Ogni politica riceve (partita, nome, carta) e ritorna (bersagli, x) se vuole lanciarla adesso, altrimenti None."""
from app.engine import mana
from app.engine.abilita import analizza_abilita
from app.engine.carte_implementate import CARTE_MIGLIORI, valore_carta
from app.engine.effetti import bersaglio_legale
from app.engine.stato import Carta, Fase, Partita
from app.engine.validazione import FASI_PRINCIPALI, puo_attivare, puo_lanciare
from app.engine.zone import Zona


def _mia_principale(p: Partita, nome: str) -> bool:
    return p.giocatore_attivo.nome == nome and p.fase in FASI_PRINCIPALI and not p.pila


def _fine_turno_avversario(p: Partita, nome: str) -> bool:
    return p.giocatore_attivo.nome != nome and p.fase == Fase.FINALE and not p.pila


def _x_massimo(p: Partita, nome: str, carta: Carta, bersagli: list[str]) -> int:
    for x in range(20, -1, -1):
        if puo_lanciare(p, nome, carta, bersagli, x) is None:
            return x
    return -1


def _forza_totale(p: Partita, chi: str) -> int:
    return sum(c.forza_attuale for c in p.giocatore(chi)[Zona.CAMPO] if c.is_creatura)


def _migliore_creatura_avversaria(p: Partita, nome: str, fonte: Carta, tipo: str) -> Carta | None:
    avv = p.avversario_di(nome)
    candidate = [c for c in avv[Zona.CAMPO] if c.is_creatura and bersaglio_legale(p, tipo, f"carta:{c.id}", fonte)]
    return max(candidate, key=lambda c: (c.forza_attuale, c.costituzione_attuale)) if candidate else None


def contromagia(p: Partita, nome: str, carta: Carta):
    if not p.pila:
        return None
    cima = p.pila[-1]
    if cima.controllore == nome or cima.abilita or cima.innesco:
        return None
    rif = f"pila:{cima.id}"
    tipo = {"Counterspell": "magia", "Mana Drain": "magia", "Red Elemental Blast": "blu",
            "Blue Elemental Blast": "rosso"}[carta.nome]
    if not bersaglio_legale(p, tipo, rif, carta):
        return None
    mi_colpisce = any(rif_b.startswith("giocatore:" + nome) or
                      (rif_b.startswith("carta:") and (t := p.trova_in_campo(rif_b[6:])) and t[0].nome == nome)
                      for rif_b in cima.bersagli)
    if mana.valore(cima.carta.costo) >= 2 or mi_colpisce or cima.carta.nome in CARTE_MIGLIORI:
        return [rif], 0
    return None


def rimozione(p: Partita, nome: str, carta: Carta):
    tipo = "creatura_non_nera_non_artefatto" if carta.nome == "Terror" else "creatura"
    comb = p.combattimento
    if comb and comb.attaccanti and p.giocatore_attivo.nome != nome and not p.pila:
        in_campo = [p.trova_in_campo(i) for i in comb.attaccanti]
        attaccanti = [t[1] for t in in_campo if t and bersaglio_legale(p, tipo, f"carta:{t[1].id}", carta)]
        if attaccanti:
            return [f"carta:{max(attaccanti, key=lambda c: c.forza_attuale).id}"], 0
    if _mia_principale(p, nome) and (c := _migliore_creatura_avversaria(p, nome, carta, tipo)) and c.forza_attuale >= 2:
        return [f"carta:{c.id}"], 0
    return None


# Terre che un giocatore esperto toglie per prime, a parte i colori (vedi terra_da_distruggere)
TERRE_DI_VALORE = {"Library of Alexandria": 8, "Mishra's Factory": 7, "Strip Mine": 5, "City of Brass": 3}


def _colori_che_usa(p: Partita, chi: str) -> dict[str, int]:
    """Quanto l'avversario usa ogni colore: simboli colorati delle sue carte viste (campo e cimitero)."""
    peso: dict[str, int] = {}
    g = p.giocatore(chi)
    for c in [*g[Zona.CAMPO], *g[Zona.CIMITERO]]:
        if not c.is_terra:
            for colore, n in mana.analizza_costo(c.costo).items():
                if colore in "WUBRG":
                    peso[colore] = peso.get(colore, 0) + n
    return peso


def _fonti_per_colore(p: Partita, chi: str) -> dict[str, list[Carta]]:
    fonti: dict[str, list[Carta]] = {}
    for c in p.giocatore(chi)[Zona.CAMPO]:
        if (f := mana.mana_prodotto(c)) and f.colori != "C":
            for colore in f.colori:
                fonti.setdefault(colore, []).append(c)
    return fonti


def punteggio_terra(p: Partita, nome: str, terra: Carta) -> float:
    """Quanto conviene distruggere questa terra avversaria. Come un giocatore esperto:
    - Maze of Ith prima di tutto, se ho creature con cui attaccare; Library of Alexandria se l'avversario ha 6-7
      carte in mano (con 7 pesca gratis);
    - le fonti di un colore che l'avversario usa ed è rimasto con poche fonti: togliere l'ultima isola o l'ultima
      pianura vuol dire niente Counterspell o Swords to Plowshares sulla mia creatura (contro bianco e blu,
      con creature in campo, quei due colori pesano di più);
    - poi le terre utili (Library of Alexandria, Mishra's Factory, Strip Mine) e le doppie."""
    avv = p.avversario_di(nome).nome
    mie_creature = any(c.is_creatura for c in p.giocatore(nome)[Zona.CAMPO])
    if terra.nome == "Maze of Ith":
        return 40.0 if mie_creature else 4.0
    if terra.nome == "Library of Alexandria" and len(p.giocatore(avv)[Zona.MANO]) >= 6:
        return 35.0  # con 6-7 carte in mano sta per pescare gratis a ogni turno: va tolta subito
    punti = float(TERRE_DI_VALORE.get(terra.nome, 0))
    fonte = mana.mana_prodotto(terra)
    if not fonte or fonte.colori == "C":
        return punti
    usati = _colori_che_usa(p, avv)
    fonti = _fonti_per_colore(p, avv)
    for colore in fonte.colori:
        importanza = 1 + usati.get(colore, 0)
        if mie_creature and colore in "WU":  # Swords, Wrath, Counterspell: le risposte alle mie creature
            importanza += 3
        quante = len(fonti.get(colore, []))
        punti += importanza * (6 if quante == 1 else 3 / quante)  # l'ultima fonte di un colore vale moltissimo
    return punti + 0.5 * (len(fonte.colori) - 1)


def terra_da_distruggere(p: Partita, nome: str, fonte: Carta, minimo: float = 0) -> Carta | None:
    avv = p.avversario_di(nome)
    candidate = [t for t in avv[Zona.CAMPO] if t.is_terra and bersaglio_legale(p, "terra", f"carta:{t.id}", fonte)]
    if not candidate:
        return None
    migliore = max(candidate, key=lambda t: (punteggio_terra(p, nome, t), valore_carta(t)))
    return migliore if punteggio_terra(p, nome, migliore) >= minimo else None


def distruggi_permanente(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    tipo = {"Disenchant": "artefatto_o_incantesimo", "Shatter": "artefatto", "Stone Rain": "terra",
            "Sinkhole": "terra", "Ice Storm": "terra"}[carta.nome]
    if tipo == "terra":
        terra = terra_da_distruggere(p, nome, carta)
        return ([f"carta:{terra.id}"], 0) if terra else None
    avv = p.avversario_di(nome)
    candidate = [c for c in avv[Zona.CAMPO] if bersaglio_legale(p, tipo, f"carta:{c.id}", carta)]
    if not candidate:
        return None
    return [f"carta:{max(candidate, key=valore_carta).id}"], 0


def pescate(p: Partita, nome: str, carta: Carta):
    mano = len(p.giocatore(nome)[Zona.MANO]) - 1
    if carta.nome == "Ancestral Recall" and (_fine_turno_avversario(p, nome) or (_mia_principale(p, nome) and mano <= 2)):
        return [f"giocatore:{nome}"], 0
    if carta.nome == "Braingeyser" and (_fine_turno_avversario(p, nome) or _mia_principale(p, nome)):
        x = _x_massimo(p, nome, carta, [f"giocatore:{nome}"])
        return ([f"giocatore:{nome}"], x) if x >= 3 else None
    if carta.nome in ("Timetwister", "Wheel of Fortune") and _mia_principale(p, nome) and mano <= 1:
        return [], 0
    return None


def tutor_e_turni(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    if carta.nome == "Time Walk" and p.fase == Fase.PRINCIPALE_1:
        return [], 0
    if carta.nome == "Demonic Tutor":
        return [], 0
    if carta.nome == "Regrowth":
        cimitero = [c for c in p.giocatore(nome)[Zona.CIMITERO] if not c.is_terra]
        if cimitero:
            return [f"cimitero:{max(cimitero, key=valore_carta).id}"], 0
    return None


def mind_twist(p: Partita, nome: str, carta: Carta):
    avv = p.avversario_di(nome).nome
    if _mia_principale(p, nome) and len(p.giocatore(avv)[Zona.MANO]) >= 2:
        x = min(_x_massimo(p, nome, carta, [f"giocatore:{avv}"]), len(p.giocatore(avv)[Zona.MANO]))
        if x >= 2:
            return [f"giocatore:{avv}"], x
    return None


def danni_x(p: Partita, nome: str, carta: Carta):
    """Fireball / Disintegrate / Psionic Blast: alla faccia se è letale, altrimenti sulla creatura migliore che muore."""
    avv = p.avversario_di(nome)
    faccia = f"giocatore:{avv.nome}"
    if carta.nome == "Psionic Blast":
        if p.giocatore(nome).vita <= 6:
            return None
        if avv.vita <= 4:
            return [faccia], 0
        if (c := _creatura_che_muore(p, nome, carta, 4)) and _mia_principale(p, nome):
            return [f"carta:{c.id}"], 0
        return None
    x = _x_massimo(p, nome, carta, [faccia])
    if x >= avv.vita:
        return [faccia], x
    if carta.nome == "Fireball" and _mia_principale(p, nome) and (due := _due_creature_che_muoiono(p, nome, carta)):
        return due
    if _mia_principale(p, nome) and (c := _creatura_che_muore(p, nome, carta, x)):
        return [f"carta:{c.id}"], c.costituzione_attuale - c.danni
    return None


def _due_creature_che_muoiono(p: Partita, nome: str, carta: Carta):
    """Fireball divisa: le due creature avversarie migliori che muoiono entrambe con X // 2 danni a testa."""
    candidate = sorted((c for c in p.avversario_di(nome)[Zona.CAMPO] if c.is_creatura and c.forza_attuale >= 2
                        and bersaglio_legale(p, "qualsiasi", f"carta:{c.id}", carta)),
                       key=lambda c: (c.forza_attuale, c.costituzione_attuale), reverse=True)[:2]
    if len(candidate) < 2:
        return None
    bersagli = [f"carta:{c.id}" for c in candidate]
    x = 2 * max(c.costituzione_attuale - c.danni for c in candidate)
    if x <= 0 or puo_lanciare(p, nome, carta, bersagli, x) is not None:
        return None
    return bersagli, x


def _creatura_che_muore(p: Partita, nome: str, fonte: Carta, danni: int) -> Carta | None:
    candidate = [c for c in p.avversario_di(nome)[Zona.CAMPO] if c.is_creatura
                 and bersaglio_legale(p, "qualsiasi", f"carta:{c.id}", fonte)
                 and 0 < c.costituzione_attuale - c.danni <= danni and c.forza_attuale >= 2]
    return max(candidate, key=lambda c: (c.forza_attuale, c.costituzione_attuale)) if candidate else None


def recall(p: Partita, nome: str, carta: Carta):
    """Recall per X=1 se nel cimitero c'è una carta tra le migliori (Ancestral, Time Walk...)."""
    g = p.giocatore(nome)
    if _mia_principale(p, nome) and len(g[Zona.MANO]) >= 2 and any(c.nome in CARTE_MIGLIORI for c in g[Zona.CIMITERO]):
        return [], 1
    return None


def spazza(p: Partita, nome: str, carta: Carta):
    if not _mia_principale(p, nome):
        return None
    avv = p.avversario_di(nome).nome
    mie, sue = _forza_totale(p, nome), _forza_totale(p, avv)
    if carta.nome == "Wrath of God" and sue >= mie + 4 and len([c for c in p.giocatore(avv)[Zona.CAMPO] if c.is_creatura]) >= 2:
        return [], 0
    if carta.nome == "Armageddon" and mie >= 5 and sue == 0:
        return [], 0
    return None


def dark_ritual(p: Partita, nome: str, carta: Carta):
    """Solo se con {B}{B}{B} in più diventa lanciabile una carta della mano che adesso non lo è."""
    if not _mia_principale(p, nome):
        return None
    from app.engine.validazione import fonti_di_mana
    g = p.giocatore(nome)
    fonti = fonti_di_mana(p, nome)
    piano = mana.piano_pagamento(g.riserva, fonti, mana.analizza_costo(carta.costo))
    if piano is None:
        return None
    usate = [f for f, _ in piano]
    restanti = [f for f in fonti if not any(f is u for u in usate)]
    riserva = dict(g.riserva)
    riserva["B"] = riserva.get("B", 0) + 3
    for altra in g[Zona.MANO]:
        if altra is carta or altra.is_terra or puo_lanciare(p, nome, altra) is None:
            continue
        if altra.is_permanente or altra.nome in POLITICHE:
            costo = mana.con_x(mana.analizza_costo(altra.costo), 0)
            if mana.piano_pagamento(riserva, restanti, costo) is not None:
                return [], 0
    return None


def _quanti(p: Partita, chi: str, condizione) -> int:
    return sum(1 for c in p.giocatore(chi)[Zona.CAMPO] if condizione(c))


def vantaggio_balance(p: Partita, nome: str, mie_terre: int | None = None) -> int:
    """Quanto Balance fa perdere all'avversario più che a lei (creature contano doppio). mie_terre: quante terre
    avrebbe lei (per provare la Strip Mine sulla propria terra prima di Balance)."""
    avv = p.avversario_di(nome).nome
    def perdite(mie: int, sue: int) -> tuple[int, int]:
        minimo = min(mie, sue)
        return mie - minimo, sue - minimo
    if mie_terre is None:
        mie_terre = _quanti(p, nome, lambda c: c.is_terra)
    terre = perdite(mie_terre, _quanti(p, avv, lambda c: c.is_terra))
    mano = perdite(len(p.giocatore(nome)[Zona.MANO]) - 1, len(p.giocatore(avv)[Zona.MANO]))
    creature = perdite(_quanti(p, nome, lambda c: c.is_creatura), _quanti(p, avv, lambda c: c.is_creatura))
    return (terre[1] - terre[0]) + (mano[1] - mano[0]) + 2 * (creature[1] - creature[0])


def _mana_senza_terre(p: Partita, chi: str) -> int:
    """Mana dai permanenti che non sono terre (Mox, Sol Ring, Mana Vault...), Black Lotus escluso (si consuma)."""
    totale = 0
    for c in p.giocatore(chi)[Zona.CAMPO]:
        if not c.is_terra and (f := mana.mana_prodotto(c)) and not f.sacrifica:
            totale += f.quantita
    return totale


def strip_per_balance(p: Partita, nome: str):
    """La giocata di Marco contro The Deck: Strip Mine sulla PROPRIA terra, poi Balance. Restando senza terre
    (o quasi), Balance costringe l'avversario a scendere allo stesso numero, e intanto gli svuota mano e campo.
    Solo se Balance si paga ancora senza la Strip Mine e la terra distrutta (Mox, Sol Ring, Lotus...), se
    l'avversario perde almeno 3 terre e se così Balance rende chiaramente di più.
    Ritorna (Strip Mine, abilità, [bersaglio]) oppure None."""
    if not _mia_principale(p, nome):
        return None
    from app.engine.validazione import fonti_di_mana
    g = p.giocatore(nome)
    bilancia = next((c for c in g[Zona.MANO] if c.nome == "Balance"), None)
    if bilancia is None:
        return None
    costo = mana.analizza_costo(bilancia.costo)
    sue_terre = _quanti(p, p.avversario_di(nome).nome, lambda c: c.is_terra)
    mie_terre = _quanti(p, nome, lambda c: c.is_terra)
    for mina in g[Zona.CAMPO]:
        for ab in analizza_abilita(mina):
            if ab.tipo != "distruggi" or ab.bersaglio != "terra" or puo_attivare(p, nome, mina, ab) is not None:
                continue
            dopo = mie_terre - 2  # la Strip Mine si sacrifica e porta via una terra sua
            # dopo, si gioca con il mana degli artefatti: conviene solo se lei ne ha più dell'avversario
            if (sue_terre - dopo < 3 or vantaggio_balance(p, nome, dopo) < 4
                    or _mana_senza_terre(p, nome) <= _mana_senza_terre(p, p.avversario_di(nome).nome)):
                return None
            # prima le terre che non servono a pagare Balance (non bianche), poi le altre
            candidate = sorted((t for t in g[Zona.CAMPO] if t.is_terra and t is not mina),
                               key=lambda t: "W" in ((f := mana.mana_prodotto(t)) and f.colori or ""))
            for terra in candidate:
                fonti = [f for f in fonti_di_mana(p, nome) if f.carta is not mina and f.carta is not terra]
                if (mana.piano_pagamento(g.riserva, fonti, costo) is not None
                        and bersaglio_legale(p, "terra", f"carta:{terra.id}", mina)):
                    return mina, ab, [f"carta:{terra.id}"]
    return None


def balance(p: Partita, nome: str, carta: Carta):
    """Quando fa perdere all'avversario più di quanto fa perdere a lei; ma se conviene prima la Strip Mine
    sulla propria terra (strip_per_balance), aspetta: Balance arriva subito dopo."""
    if not _mia_principale(p, nome) or strip_per_balance(p, nome):
        return None
    return ([], 0) if vantaggio_balance(p, nome) >= 3 else None


def terremoto(p: Partita, nome: str, carta: Carta):
    """Earthquake (creature senza volare) / Hurricane (con volare): X letale per l'avversario e non per lei,
    oppure la X che uccide più creature avversarie che sue."""
    if not _mia_principale(p, nome):
        return None
    g, avv = p.giocatore(nome), p.avversario_di(nome)
    vola = carta.nome == "Hurricane"
    x_max = _x_massimo(p, nome, carta, [])
    if x_max >= avv.vita and g.vita > avv.vita:
        return [], avv.vita
    def valore_colpite(chi, x):
        return sum((c.forza_attuale or 0) + 1 for c in p.giocatore(chi)[Zona.CAMPO]
                   if c.is_creatura and c.ha("flying") == vola and not c.protetta_da(carta)
                   and c.costituzione_attuale - c.danni <= x)
    migliore = None
    for x in range(1, x_max + 1):
        if g.vita - x < 6:
            break
        guadagno = valore_colpite(avv.nome, x) - valore_colpite(nome, x)
        if guadagno >= 5 and (migliore is None or guadagno > migliore[0]):
            migliore = (guadagno, x)
    return ([], migliore[1]) if migliore else None


def rimbalzo(p: Partita, nome: str, carta: Carta):
    """Unsummon / Boomerang: sull'attaccante avversario più grosso, prima dei blocchi."""
    comb = p.combattimento
    if not (comb and comb.attaccanti_dichiarati and not comb.bloccanti_dichiarati and not p.pila
            and p.giocatore_attivo.nome != nome):
        return None
    tipo = "creatura" if carta.nome == "Unsummon" else "permanente"
    attaccanti = [t[1] for i in comb.attaccanti if (t := p.trova_in_campo(i))
                  and bersaglio_legale(p, tipo, f"carta:{t[1].id}", carta)]
    grosso = max(attaccanti, key=lambda c: c.forza_attuale, default=None)
    return ([f"carta:{grosso.id}"], 0) if grosso and grosso.forza_attuale >= 3 else None


POLITICHE = {
    "Dark Ritual": dark_ritual, "Balance": balance, "Earthquake": terremoto, "Hurricane": terremoto,
    "Unsummon": rimbalzo, "Boomerang": rimbalzo,
    "Counterspell": contromagia, "Mana Drain": contromagia, "Red Elemental Blast": contromagia,
    "Blue Elemental Blast": contromagia,
    "Swords to Plowshares": rimozione, "Terror": rimozione,
    "Disenchant": distruggi_permanente, "Shatter": distruggi_permanente, "Stone Rain": distruggi_permanente,
    "Sinkhole": distruggi_permanente, "Ice Storm": distruggi_permanente,
    "Ancestral Recall": pescate, "Braingeyser": pescate, "Timetwister": pescate, "Wheel of Fortune": pescate,
    "Time Walk": tutor_e_turni, "Demonic Tutor": tutor_e_turni, "Regrowth": tutor_e_turni,
    "Recall": recall, "Mind Twist": mind_twist, "Fireball": danni_x, "Disintegrate": danni_x, "Psionic Blast": danni_x,
    "Wrath of God": spazza, "Armageddon": spazza,
}


def scegli_magia(p: Partita, nome: str):
    """La prima magia della mano che una politica vuole lanciare adesso: (carta, bersagli, x) o None."""
    for carta in list(p.giocatore(nome)[Zona.MANO]):
        politica = POLITICHE.get(carta.nome)
        if politica is None or puo_lanciare(p, nome, carta) is not None:
            continue
        scelta = politica(p, nome, carta)
        if scelta and puo_lanciare(p, nome, carta, scelta[0], scelta[1]) is None:
            return carta, scelta[0], scelta[1]
    return None


# Permanenti non creatura che un giocatore esperto toglie di mezzo appena può (vantaggio carte o blocco del gioco)
PERMANENTI_PERICOLOSI = {"Sylvan Library": 9, "Moat": 9, "The Abyss": 9, "Mirror Universe": 8, "Millstone": 8,
                         "Black Vise": 7, "Jayemdae Tome": 7, "Library of Alexandria": 8, "Icy Manipulator": 7,
                         "Disrupting Scepter": 7, "Howling Mine": 5, "Bad Moon": 6, "Crusade": 6, "Sol Ring": 6,
                         "Chaos Orb": 6, "Ivory Tower": 5}


def pericolo(t: Carta) -> int:
    """Quanto è importante distruggere un permanente avversario (0 = non vale la pena)."""
    if t.is_terra:
        return 0
    if t.nome in PERMANENTI_PERICOLOSI:
        return PERMANENTI_PERICOLOSI[t.nome]
    if t.is_creatura:
        punti = 2 * (t.forza_attuale or 0) + (2 if t.ha("flying") else 0)
        if "discards" in t.testo or "draw" in t.testo.lower():  # Hypnotic Specter e simili: rubano carte
            punti += 3
        return punti
    return 4 if t.nome in CARTE_MIGLIORI or t.nome.startswith("Mox") else 0


def _bersaglio_chaos_orb(p: Partita, nome: str, orb: Carta) -> Carta | None:
    """Chaos Orb: in risposta all'Orb avversario lo distrugge (così il suo non cade su niente); altrimenti, nella sua
    fase principale o alla fine del turno avversario, sul permanente avversario più pericoloso."""
    avv = p.avversario_di(nome)
    legale = lambda t: bersaglio_legale(p, "permanente", f"carta:{t.id}", orb)
    if p.pila:
        cima = p.pila[-1]
        if (cima.controllore != nome and cima.abilita and cima.abilita.tipo == "chaos_orb"
                and (t := p.trova_in_campo(cima.carta.id)) and legale(t[1])):
            return t[1]
        return None
    if not (_mia_principale(p, nome) or _fine_turno_avversario(p, nome)):
        return None
    candidati = [t for t in avv[Zona.CAMPO] if legale(t) and pericolo(t) >= 6]
    return max(candidati, key=lambda t: (pericolo(t), valore_carta(t))) if candidati else None


def _cima_rivelata(p: Partita) -> bool:
    """Field of Dreams in campo: la prima carta dei grimori è scoperta e la si può guardare."""
    return any(c.nome == "Field of Dreams" for g in p.giocatori for c in g[Zona.CAMPO])


def _fonti_in_campo(p: Partita, chi: str) -> int:
    """Permanenti che producono mana (terre, Mox, Sol Ring...), tappati o no."""
    return sum(1 for c in p.giocatore(chi)[Zona.CAMPO] if c.is_terra or mana.mana_prodotto(c))


def _mana_value(carta: Carta) -> int:
    return sum(mana.analizza_costo(carta.costo).values()) if carta.costo else 0


def _carta_utile(p: Partita, chi: str, carta: Carta) -> bool:
    """Una terra serve a chi ne ha poche; una magia serve sempre. Ma a chi è rimasto senza mana (niente terre,
    Mox rotti: la partita di Marco con Field of Dreams, Strip Mine e Disenchant) servono solo le fonti di mana:
    una magia che costa qualcosa non la può lanciare, quindi la si lascia in cima e si macinano le terre."""
    if _fonti_in_campo(p, chi) == 0:
        return carta.is_terra or bool(mana.mana_prodotto(carta)) or _mana_value(carta) == 0
    if not carta.is_terra:
        return True
    return sum(1 for c in p.giocatore(chi)[Zona.CAMPO] if c.is_terra) < 5


RISPOSTE_ALLE_CREATURE = {"Swords to Plowshares", "Terror", "Lightning Bolt", "Fireball", "Disintegrate",
                          "Psionic Blast", "Wrath of God", "Balance", "Unsummon", "Chaos Orb", "Earthquake"}


def mossa_disperata(p: Partita, nome: str) -> bool:
    """La «mossa disperata» insegnata da Marco: c'è una creatura avversaria pericolosa, in mano non ho niente per
    toglierla e in cima al grimorio ho rimesso con Sylvan Library carte che non lo fanno: con Millstone macino le
    mie due carte inutili, così al prossimo turno pesco una carta nuova (magari Swords to Plowshares)."""
    io, avv = p.giocatore(nome), p.avversario_di(nome)
    minaccia = any(c.is_creatura and pericolo(c) >= 6 for c in avv[Zona.CAMPO])
    risposta_in_mano = any(c.nome in RISPOSTE_ALLE_CREATURE for c in io[Zona.MANO])
    cima = io[Zona.GRIMORIO][-2:]
    note_inutili = bool(cima) and all(c.nota_in_cima and c.nome not in RISPOSTE_ALLE_CREATURE for c in cima)
    return minaccia and not risposta_in_mano and note_inutili and len(io[Zona.GRIMORIO]) > 10


def bersaglio_millstone(p: Partita, nome: str) -> str | None:
    """Millstone alla fine del turno avversario. Prima la mossa disperata (vedi mossa_disperata); poi come
    «Conceding Dreams» (Wak Wak): con Field of Dreams in campo si
    guarda la cima dei grimori; si macina l'avversario solo se la sua prossima carta gli serve (tenendolo senza
    terre o senza magie buone), altrimenti la si lascia lì e, se la propria cima non serve, si macina sé stessi.
    Senza Field of Dreams si macina sempre l'avversario."""
    avv = p.avversario_di(nome)
    io = p.giocatore(nome)
    if mossa_disperata(p, nome):
        return nome  # macina le carte inutili rimesse in cima con Sylvan Library per pescare una risposta
    if not _cima_rivelata(p):
        return avv.nome
    if avv[Zona.GRIMORIO] and _carta_utile(p, avv.nome, avv[Zona.GRIMORIO][-1]):
        return avv.nome
    if io[Zona.GRIMORIO] and len(io[Zona.GRIMORIO]) > 10 and not _carta_utile(p, nome, io[Zona.GRIMORIO][-1]):
        return nome
    return None


# --- Creature che si sacrificano per distruggere un artefatto (Scavenger Folk) ---------------------------

def abilita_sacrificio_artefatto(c: Carta):
    """«{G}, {T}, Sacrifice Scavenger Folk: Destroy target artifact.» e simili, su una creatura; altrimenti None."""
    if not c.is_creatura:
        return None
    return next((ab for ab in analizza_abilita(c) if ab.tipo == "distruggi" and ab.sacrifica_se
                 and ab.bersaglio in ("artefatto", "artefatto_o_incantesimo")), None)


def artefatto_da_colpire(p: Partita, nome: str, fonte: Carta, tipo: str) -> Carta | None:
    """L'artefatto (o incantesimo) avversario più importante che quell'abilità può distruggere."""
    candidati = [c for c in p.avversario_di(nome)[Zona.CAMPO] if bersaglio_legale(p, tipo, f"carta:{c.id}", fonte)]
    return max(candidati, key=lambda c: (pericolo(c), valore_carta(c))) if candidati else None


def pronta_a_sacrificarsi(p: Partita, nome: str, c: Carta) -> Carta | None:
    """Mentre si dichiarano i bloccanti (senza priorità): la creatura potrà poi sacrificarsi, cioè è stappata,
    non ha debolezza da evocazione se l'abilità la tappa, il mana c'è con le altre fonti e c'è un bersaglio?
    Ritorna il bersaglio."""
    ab = abilita_sacrificio_artefatto(c)
    if ab is None or c.tappata or (ab.tappa and p.ha_debolezza_da_evocazione(c)):
        return None
    g = p.giocatore(nome)
    terre_avv = p.avversario_di(nome)[Zona.CAMPO]
    fonti = [f for x in g[Zona.CAMPO] if x is not c and not x.tappata
             and not (x.is_creatura and p.ha_debolezza_da_evocazione(x))
             and (f := mana.fonte_in_partita(x, terre_avv))]
    if mana.piano_pagamento(g.riserva, fonti, mana.analizza_costo(ab.costo_mana)) is None:
        return None
    return artefatto_da_colpire(p, nome, c, ab.bersaglio)


def _sacrificio_in_combattimento(p: Partita, nome: str):
    """La giocata dei maestri con Scavenger Folk: blocca, poi prima dei danni si sacrifica e distrugge un
    artefatto. L'attaccante resta bloccato (non colpisce il giocatore) e l'artefatto se ne va: due carte per una.
    Lo stesso se attacca ed è stata bloccata. Altrimenti, nella sua fase principale o alla fine del turno
    avversario, solo contro un artefatto pericoloso (pericolo ≥ 6)."""
    comb = p.combattimento
    in_combattimento = set()
    if comb and comb.bloccanti_dichiarati:
        in_combattimento = set(comb.bloccanti()) | {a for a in comb.blocchi if comb.blocchi[a]}
    for c in list(p.giocatore(nome)[Zona.CAMPO]):
        ab = abilita_sacrificio_artefatto(c)
        if ab is None or puo_attivare(p, nome, c, ab) is not None:
            continue
        bersaglio = artefatto_da_colpire(p, nome, c, ab.bersaglio)
        if bersaglio is None:
            continue
        if c.id in in_combattimento and not p.pila:
            return c, ab, [f"carta:{bersaglio.id}"]
        if (_mia_principale(p, nome) or _fine_turno_avversario(p, nome)) and pericolo(bersaglio) >= 6:
            return c, ab, [f"carta:{bersaglio.id}"]
    return None


def scegli_abilita(p: Partita, nome: str):
    """Abilità di utilità: Strip Mine sulla terra che conviene togliere (terra_da_distruggere), Library of Alexandria e Jayemdae Tome a fine turno
    avversario, Icy Manipulator sulla creatura migliore avversaria nel suo mantenimento."""
    avv = p.avversario_di(nome)
    if combinazione := strip_per_balance(p, nome):
        return combinazione
    if sacrificio := _sacrificio_in_combattimento(p, nome):
        return sacrificio
    for c in list(p.giocatore(nome)[Zona.CAMPO]):
        for ab in analizza_abilita(c):
            if puo_attivare(p, nome, c, ab) is not None:
                continue
            if ab.tipo == "distruggi" and ab.bersaglio == "terra" and _mia_principale(p, nome):
                # Strip Mine costa una terra anche a lei: solo per un bersaglio che vale (Maze, ultima fonte, Library)
                if terra := terra_da_distruggere(p, nome, c, minimo=6):
                    return c, ab, [f"carta:{terra.id}"]
            if ab.tipo == "pesca" and _fine_turno_avversario(p, nome):
                return c, ab, []
            if ab.tipo == "macina" and _fine_turno_avversario(p, nome):  # Millstone
                if (chi := bersaglio_millstone(p, nome)) is not None:
                    return c, ab, [f"giocatore:{chi}"]
            if ab.tipo == "scambia_vita" and avv.vita - p.giocatore(nome).vita >= 8:  # Mirror Universe
                return c, ab, [f"giocatore:{avv.nome}"]
            if ab.tipo == "chaos_orb" and (scelta := _bersaglio_chaos_orb(p, nome, c)):
                return c, ab, [f"carta:{scelta.id}"]
            if (ab.tipo == "tappa" and p.giocatore_attivo.nome == avv.nome and p.fase == Fase.MANTENIMENTO
                    and not p.pila):
                creature = [t for t in avv[Zona.CAMPO] if t.is_creatura and not t.tappata
                            and bersaglio_legale(p, ab.bersaglio, f"carta:{t.id}", c)]
                if creature:
                    return c, ab, [f"carta:{max(creature, key=lambda t: t.forza_attuale).id}"]
    return None
