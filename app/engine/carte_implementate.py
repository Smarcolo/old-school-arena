"""Effetti delle carte implementate. Importato da azioni.py così il registro è sempre pieno."""
from app.engine.effetti import effetto


@effetto("Lightning Bolt", bersaglio="qualsiasi")
def lightning_bolt(partita, oggetto):
    from app.engine.azioni import infliggi_danno
    infliggi_danno(partita, oggetto.carta, oggetto.bersagli[0], 3)


@effetto("Giant Growth", bersaglio="creatura")
def giant_growth(partita, oggetto):
    creatura = partita.risolvi_bersaglio(oggetto.bersagli[0])
    creatura.bonus_forza += 3
    creatura.bonus_costituzione += 3
