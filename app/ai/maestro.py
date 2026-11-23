"""Il Maestro: cosa farebbe l'avversaria al posto dell'umano, con il suo mazzo, e perché.

Gioca una sola mossa per l'umano su una copia della partita (le carte che l'umano non può conoscere sono
rimescolate come nella previsione, quindi il Maestro non bara), legge dal registro cosa è successo e la spiega con
le regole da esperta che l'avversaria ha imparato (report dei tornei, wiki, giocate di Marco).
"""
from app.ai import avversaria, politiche, previsione
from app.engine import combattimento, mulligan
from app.engine.eventi import RegistroEventi
from app.engine.stato import Fase, Partita
from app.engine.zone import Zona

# Eventi che non sono la mossa (conseguenze automatiche o rumore)
_RUMORE = {"pesca", "mana", "tappa", "fase", "priorita"}


def _copia(partita: Partita, umano: str) -> Partita:
    """Come la previsione: la mano e il grimorio dell'avversaria sono sconosciuti, quindi rimescolati."""
    # un seme suo, senza toccare il generatore della partita (chiedere al Maestro non cambia i mescolamenti)
    c = previsione._copia(partita, umano, partita.turno * 1009 + len(partita.registro.eventi))
    c.registro = RegistroEventi()
    return c


def _una_mossa(c: Partita, umano: str) -> None:
    if mulligan.in_corso(c):
        avversaria.decidi_mulligan(c, umano)
    elif c.scelta and c.scelta.giocatore == umano:
        avversaria.decidi_scelta(c, umano)
    else:
        avversaria.agisci(c, umano)


def _perche(prima: Partita, umano: str, eventi: list, passa: bool) -> str:
    """Il motivo, preso dalle regole dell'avversaria che hanno deciso la mossa."""
    avv = prima.avversario_di(umano).nome
    testi = " ".join(e.descrizione for e in eventi)
    mano = [c.nome for c in prima.giocatore(umano)[Zona.MANO]]
    if mulligan.in_corso(prima):
        if "mulligan" in testi.lower() and "tiene" not in testi.lower():
            if avversaria.senza_colori(prima.giocatore(umano)[Zona.MANO]):
                return "Le tue fonti non lanciano nessuna delle tue magie: meglio sei carte giocabili di sette ferme."
            return "Troppe o troppo poche terre: con meno di 2 o più di 5 terre su 7 la mano non gira."
        return "Da 2 a 5 terre e i colori giusti: è una mano da tenere."
    if passa:
        if avversaria.dopo_il_combattimento(prima, umano) and any(
                c.is_creatura for c in prima.giocatore(umano)[Zona.MANO]):
            return ("Prima attacca: le creature nuove non attaccherebbero comunque, giocale nella seconda fase "
                    "principale, così l'avversaria blocca senza sapere cosa hai.")
        if any(n in avversaria.CONTROMAGIE for n in mano):
            return "Tieni il mana aperto per la contromagia: usala solo su una carta decisiva."
        return "Adesso non c'è niente che convenga fare: conserva carte e mana per il momento giusto."
    if "Lightning Bolt" in testi and f"{avv}" in testi and "carta:" not in testi:
        return "In faccia solo quando i danni che puoi lanciare adesso bastano a chiudere, o contro chi non ha creature."
    if "Strip Mine" in testi:
        return ("Strip Mine sulla terra che conta: Maze of Ith se hai creature, Library of Alexandria se l'avversaria "
                "ha la mano piena, oppure l'ultima fonte di un colore che usa.")
    if "Balance" in testi:
        return "Balance quando le fa perdere più terre, carte e creature di quante ne perdi tu."
    if "Millstone" in testi or "macina" in testi.lower():
        if politiche._cima_rivelata(prima):
            return ("Con Field of Dreams vedi le cime: si macina la carta che all'avversaria serve, o la tua che non "
                    "ti serve. Se è rimasta senza mana, le servono solo terre e Mox.")
        return "Millstone alla fine del turno avversario: due carte in meno nel suo grimorio a ogni giro."
    if "Swords to Plowshares" in testi or "Terror" in testi:
        return "La rimozione va sulla creatura più pericolosa: prima chi ruba carte, chi ha un'aura, chi vola."
    if "Counterspell" in testi or "Mana Drain" in testi:
        return "È una carta decisiva: la contromagia si spende per questo, non per le carte piccole."
    if "Chaos Orb" in testi:
        return "Chaos Orb sul permanente più pericoloso dell'avversaria (Sylvan Library, Moat, creature grosse)."
    if "attacc" in testi.lower():
        return ("Attacca chi non viene bloccato male: occhio alle Mishra's Factory pronte a bloccare e a cosa succede "
                "nel contrattacco.")
    if "blocc" in testi.lower():
        return "Blocca quando uccidi l'attaccante e sopravvivi, o quando il danno in arrivo ti metterebbe in pericolo."
    if any(e.tipo == "terra" or "gioca" in e.descrizione and "terra" in e.descrizione for e in eventi):
        return "Prima la terra: più mana per tutto il resto del turno."
    return "È la giocata che l'avversaria farebbe con le sue regole da esperta."


def consiglio(partita: Partita, umano: str) -> dict:
    """{"mossa": cosa fare, "perche": il motivo}. Non cambia la partita vera."""
    if partita.vincitore:
        return {"mossa": "La partita è finita.", "perche": ""}
    c = _copia(partita, umano)
    turno, fase = c.turno, c.fase
    comb_prima = combattimento.deve_dichiarare_attaccanti(c, umano) or combattimento.deve_dichiarare_bloccanti(c, umano)
    if not (mulligan.in_corso(c) or (c.scelta and c.scelta.giocatore == umano) or comb_prima
            or c.giocatore_con_priorita.nome == umano):
        return {"mossa": "Adesso tocca all'avversaria.", "perche": ""}
    try:
        _una_mossa(c, umano)
    except Exception as e:  # il Maestro non deve mai rompere la partita
        return {"mossa": "Il Maestro non sa consigliarti in questa situazione.", "perche": str(e)}
    eventi = [e for e in c.registro.eventi if e.giocatore == umano and e.tipo not in _RUMORE]
    passa = not eventi or all(e.tipo == "passa" for e in eventi) or (c.turno, c.fase) != (turno, fase) and not eventi
    if passa:
        mossa = "Passa." if fase not in (Fase.PRINCIPALE_1, Fase.PRINCIPALE_2) else "Non giocare niente adesso: passa."
    else:
        mossa = "; ".join(dict.fromkeys(e.descrizione for e in eventi))
    return {"mossa": mossa, "perche": _perche(partita, umano, eventi, passa)}
