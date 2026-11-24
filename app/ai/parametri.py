"""I numeri che guidano le decisioni dell'avversaria, in un posto solo, così si possono mettere alla prova al banco
(strumenti/banco/allena.py): si prova un valore diverso, si gioca contro la versione attuale con mazzi e posti
scambiati, e si tiene solo se vince chiaramente. Ogni valore ha accanto da dove viene."""

P = {
    # Lightning Bolt in faccia (quando non è letale): sotto questa vita avversaria, o con almeno tante carte in mano
    "bolt_faccia_vita": 10,
    "bolt_faccia_mano": 6,
    # Balance: vantaggio minimo (terre + carte + 2 × creature perse dall'avversario in più)
    "balance_vantaggio": 3,
    # Strip Mine: punteggio minimo della terra avversaria (punteggio_terra)
    "strip_minimo": 6,
    # Chaos Orb e Scavenger Folk fuori dal combattimento: pericolo minimo del bersaglio
    "orb_pericolo": 6,
    # Swords/Terror nella propria fase principale: forza minima della creatura avversaria
    "rimozione_forza": 2,
    # Mulligan: terre massime in una mano da tenere
    "mulligan_terre_max": 5,
    # In attacco, gli scambi alla pari (si muore entrambi): "sempre" o "vantaggio" (solo se vince la corsa)
    "scambi_pari": "sempre",
    # In difesa: si blocca con la creatura più piccola quando i danni in arrivo arrivano a vita - margine
    "blocco_disperato_margine": 0,
    # In difesa: blocchi che scambiano alla pari (bloccante e attaccante muoiono): True/False
    "blocchi_scambio": True,
    # teme_spazzata: pressione già in campo (creature, forza) oltre la quale tiene le altre in mano
    "spazzata_creature": 2,
    "spazzata_forza": 5,
    # Wrath of God: differenza di forza in campo (con almeno 2 creature avversarie), oppure vita sotto cui si spazza
    # appena l'avversario ha più forza (0 = mai; con l'avversario letale si spazza comunque)
    "wrath_differenza": 4,
    "wrath_vita_urgente": 8,
    # Con Counterspell/Mana Drain in mano tiene {U}{U} aperti (non lancia permanenti) solo se l'avversario ha almeno
    # tante carte in mano (99 = non tiene mai, sviluppa sempre)
    "tieni_uu_mano_avversaria": 2,
    # ... e solo se ha già una creatura in campo da proteggere (prima sviluppa)
    "tieni_uu_solo_con_minaccia": True,
    # Disenchant/Shatter: pericolo minimo del bersaglio. 0 = qualsiasi (anche un Mox): con 5 Dreams of the Sea
    # perdeva 8 partite su 150 contro The Deck, togliere i Mox al controllo conta (studio 2026-11-24)
    "disenchant_pericolo": 0,
    # Black Lotus si sacrifica solo per carte da almeno tanti mana (o le migliori, o le contromagie). 0 = sempre:
    # con 4 lo studio di Dreams of the Sea perdeva qualche partita (tempo perso)
    "lotus_costo_min": 0,  # banco 2026-11-24: 51,5% su 8000 partite contro False
}
