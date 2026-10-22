from collections import Counter

from app.ai.consigli import consiglia
from app.engine.stato import Carta


def c(nome, tipo, costo, testo="", f=None, k=None):
    return Carta(nome, tipo, costo, f, k, testo)


INFO = {x.nome: x for x in [
    c("Counterspell", "Instant", "{U}{U}", "Counter target spell."),
    c("Ancestral Recall", "Instant", "{U}", "Target player draws three cards."),
    c("Serra Angel", "Creature — Angel", "{3}{W}{W}", "Flying, vigilance", 4, 4),
    c("Red Elemental Blast", "Instant", "{R}", "Choose one —\n• Counter target blue spell.\n• Destroy target blue permanent."),
    c("Blue Elemental Blast", "Instant", "{U}", "Choose one —\n• Counter target red spell.\n• Destroy target red permanent."),
    c("Shatter", "Instant", "{1}{R}", "Destroy target artifact."),
    c("Terror", "Instant", "{1}{B}", "Destroy target nonartifact, nonblack creature. It can't be regenerated."),
    c("Lightning Bolt", "Instant", "{R}", "Lightning Bolt deals 3 damage to any target."),
    c("Gray Ogre", "Creature — Ogre", "{2}{R}", "", 2, 2),
    c("Mountain", "Basic Land — Mountain", ""),
    c("Mox Sapphire", "Artifact", "{0}", "{T}: Add {U}."),
    c("Sol Ring", "Artifact", "{1}", "{T}: Add {C}{C}."),
    c("Black Knight", "Creature — Human Knight", "{B}{B}", "First strike\nProtection from white", 2, 2),
]}


def test_contro_il_blu_entra_red_elemental_blast_ed_esce_blue_elemental_blast():
    mazzo = {"Lightning Bolt": 4, "Gray Ogre": 4, "Blue Elemental Blast": 2, "Mountain": 20}
    side = {"Red Elemental Blast": 3, "Shatter": 2}
    viste = Counter({"Counterspell": 3, "Ancestral Recall": 1, "Serra Angel": 1, "Mox Sapphire": 1, "Sol Ring": 1})
    r = consiglia(side, mazzo, viste, INFO)
    assert r["entra"].get("Red Elemental Blast") == 3 and r["esce"].get("Blue Elemental Blast") == 2
    assert "blu" in r["motivi_entra"]["Red Elemental Blast"] and "Counterspell" in r["motivi_entra"]["Red Elemental Blast"]
    assert "non gioca rosso" in r["motivi_esce"]["Blue Elemental Blast"]
    assert sum(r["entra"].values()) == sum(r["esce"].values())


def test_terror_fuori_contro_creature_nere():
    mazzo = {"Terror": 3, "Gray Ogre": 4, "Mountain": 20}
    viste = Counter({"Black Knight": 4})
    r = consiglia({"Shatter": 1}, mazzo, viste, INFO)
    assert r["entra"] == {}  # Shatter non serve: nessun artefatto visto
    assert consiglia({"Lightning Bolt": 2}, mazzo, viste, INFO)["esce"].get("Terror") == 2


def test_niente_da_cambiare_se_non_serve():
    r = consiglia({"Shatter": 2}, {"Lightning Bolt": 4, "Mountain": 20}, Counter({"Gray Ogre": 2}), INFO)
    assert r["entra"] == {} and r["esce"] == {}
