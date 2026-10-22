let partita = null;
let magiaInAttesa = null; // comando ("gioca X" o "attiva X") che aspetta il clic sul bersaglio
let attaccantiScelti = new Set(); // id delle tue creature scelte per attaccare
let bloccanteScelto = null; // id della tua creatura che sta per bloccare
let blocchiScelti = []; // coppie [id attaccante, id bloccante]
let inFondoScelte = new Set(); // id delle carte da mettere in fondo dopo il mulligan
const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...figli) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...figli);
  return e;
};

async function api(percorso, opzioni = {}) {
  const r = await fetch(percorso, { headers: { "Content-Type": "application/json" }, ...opzioni });
  const testo = await r.text();
  let dati = null;
  try { dati = testo ? JSON.parse(testo) : null; } catch { /* risposta non JSON, es. errore 500 in testo */ }
  if (!r.ok) throw new Error((dati && dati.detail) || testo || r.statusText);
  return dati;
}

// I messaggi compaiono in basso e spariscono da soli, così non rubano spazio al tavolo.
let timerAvviso = null;
function avvisa(testo) {
  const m = $("messaggio");
  m.textContent = testo;
  m.classList.toggle("visibile", Boolean(testo));
  clearTimeout(timerAvviso);
  timerAvviso = setTimeout(() => m.classList.remove("visibile"), Math.max(4000, testo.length * 60));
}

function scegliBersaglio(rif) {
  const magia = magiaInAttesa;
  magiaInAttesa = null;
  document.body.classList.remove("mirino");
  invia(`${magia} su ${rif}`);
}

function azzeraScelteCombattimento() {
  inFondoScelte = new Set();
  attaccantiScelti = new Set();
  bloccanteScelto = null;
  blocchiScelti = [];
}

function nomeCarta(id) {
  for (const g of partita.giocatori) {
    const c = g.campo.find((x) => x.id === id);
    if (c) return c.nome;
  }
  return id;
}

// Le carte si mostrano con la loro immagine (cornice 1993, dal server). Se l'immagine non c'è (niente rete),
// resta una carta disegnata con nome, costo, tipo e testo.
const immaginiNonDisponibili = new Set();

function facciaTestuale(c) {
  return el("div", { className: "faccia-testo" },
    el("div", { className: "riga-nome" }, el("b", { textContent: c.nome }), el("span", { textContent: c.costo || "" })),
    el("div", { className: "riga-tipo", textContent: c.tipo || "" }),
    el("div", { className: "riga-testo", textContent: c.testo || "" }));
}

function faccia(c) {
  // sotto c'è sempre la carta disegnata: si vede mentre l'immagine arriva o se non arriva affatto
  const contenitore = el("div", { className: "faccia" }, facciaTestuale(c));
  if (immaginiNonDisponibili.has(c.nome)) return contenitore;
  const img = el("img", { src: urlImmagine(c.nome), alt: c.nome, draggable: false });
  img.onload = () => img.classList.add("caricata");
  img.onerror = () => { immaginiNonDisponibili.add(c.nome); img.remove(); };
  if (img.complete && img.naturalWidth) img.classList.add("caricata");
  contenitore.append(img);
  return contenitore;
}

function cartaEl(c, azione) {
  const comb = partita.combattimento;
  const inBanda = comb && comb.bande && comb.bande.some((b) => b.includes(c.id));
  const classi = ["carta", c.giocabile && "giocabile", inBanda && "in-banda", c.tappata && "tappata", c.appena_entrata && "appena-entrata", c.danni && "ferita",
    comb && comb.attaccanti.includes(c.id) && "attaccante", comb && comb.bloccanti.includes(c.id) && "bloccante",
    (attaccantiScelti.has(c.id) || inFondoScelte.has(c.id) || bloccanteScelto === c.id || blocchiScelti.some(([, b]) => b === c.id)) && "selezionata"];
  const e = el("div", { className: classi.filter(Boolean).join(" ") }, faccia(c));
  e.dataset.carta = c.nome;
  e.dataset.id = c.id;
  if (c.forza != null) e.append(el("span", { className: "pt", textContent: `${c.forza}/${c.costituzione - c.danni}` }));
  const note = [c.incanta && `incanta ${c.incanta}`, c.scudi && (c.scudi > 1 ? `scudo ×${c.scudi}` : "scudo"),
    comb && comb.attaccanti.includes(c.id) && "attacca", comb && comb.bloccanti.includes(c.id) && "blocca"].filter(Boolean);
  if (note.length) e.append(el("span", { className: "nota", textContent: note.join(" · ") }));
  e.title = [c.nome, c.tipo, c.costo, (c.abilita || []).join(", "), ...(c.attivabili || []).map((a) => "clic: " + a.testo),
    c.danni ? `${c.danni} danni` : "", c.appena_entrata ? "appena entrata" : "", c.tappata ? "tappata" : ""]
    .filter(Boolean).join(" · ");
  e.onclick = () => azione(c);
  return e;
}

function suCampo(c, mio) {
  if (magiaInAttesa) return scegliBersaglio(c.id);
  if (partita.richiesta === "attaccanti" && mio && c.forza != null) {
    attaccantiScelti.has(c.id) ? attaccantiScelti.delete(c.id) : attaccantiScelti.add(c.id);
    return disegna();
  }
  if (partita.richiesta === "bloccanti") {
    if (mio && c.forza != null && !c.tappata) {
      bloccanteScelto = c.id;
      blocchiScelti = blocchiScelti.filter(([, b]) => b !== c.id);
      avvisa(`Ora clicca la creatura attaccante che ${c.nome} deve bloccare.`);
    } else if (!mio && bloccanteScelto && partita.combattimento.attaccanti.includes(c.id)) {
      blocchiScelti.push([c.id, bloccanteScelto]);
      bloccanteScelto = null;
      avvisa("Blocco aggiunto. Conferma quando hai finito.");
    }
    return disegna();
  }
  if (!mio) return;
  const opzioni = [];
  if (c.puo_attaccare) opzioni.push([attaccantiScelti.has(c.id) ? "Non attaccare" : "⚔ Attacca", () => scegliAttaccante(c)]);
  (c.attivabili || []).forEach((a, i) => {
    if (a.ora) opzioni.push([`Attiva: ${a.testo}`, () => attivaAbilita(c, a, i)]);
  });
  // mana a mano: tappi tu le terre (scegliendo il colore) e poi lanci; la magia usa prima il mana in riserva
  if (c.mana_ora) for (const col of c.mana) opzioni.push([`Tappa per {${col}} ${NOMI_MANA[col] || ""}`.trim(), () => invia(`tappa ${c.id} per ${col.toLowerCase()}`)]);
  if (!opzioni.length) {
    return avvisa(c.tappata ? `${c.nome} è già tappata.` : `${c.nome} ora non può attaccare, usare abilità o dare mana.`);
  }
  if (opzioni.length === 1) return opzioni[0][1]();
  apriMenu(c, opzioni);
}

function scegliAttaccante(c) {
  attaccantiScelti.has(c.id) ? attaccantiScelti.delete(c.id) : attaccantiScelti.add(c.id);
  avvisa(attaccantiScelti.size ? `Attaccanti scelti: ${attaccantiScelti.size}. Premi «⚔ Attacca» in alto.` : "Nessun attaccante scelto.");
  disegna();
}

function attivaAbilita(c, a, i) {
  const cmd = `attiva ${c.id} ${i + 1}`;
  if (a.bersaglio === "avversario" || (a.bersaglio && BERSAGLIO_OVVIO[c.nome])) return invia(`${cmd} su avversaria`);
  if (a.bersaglio) {
    magiaInAttesa = cmd;
    document.body.classList.add("mirino");
    avvisa(`Scegli il bersaglio dell'abilità di ${c.nome}.`);
    return disegna();
  }
  invia(cmd);
}

// Menu sopra la carta quando un clic può voler dire più cose (attaccare o usare un'abilità).
function apriMenu(c, opzioni) {
  const menu = $("menu-carta");
  menu.replaceChildren(el("div", { className: "titolo-menu", textContent: c.nome }),
    ...opzioni.map(([testo, fai]) => bottone(testo, () => { chiudiMenu(); fai(); })));
  const carta = document.querySelector(`.carta[data-id="${c.id}"]`);
  const r = carta ? carta.getBoundingClientRect() : { left: 20, top: 20, bottom: 20 };
  menu.hidden = false;
  menu.style.left = `${Math.max(8, Math.min(r.left + scrollX, innerWidth - menu.offsetWidth - 8))}px`;
  menu.style.top = `${r.top + scrollY - menu.offsetHeight - 6 < scrollY ? r.bottom + scrollY + 6 : r.top + scrollY - menu.offsetHeight - 6}px`;
}

function chiudiMenu() {
  $("menu-carta").hidden = true;
}

async function attaccaConScelte() {
  const ids = [...attaccantiScelti];
  if (partita.richiesta !== "attaccanti") await invia("passa");  // dalla principale 1 si va al combattimento
  if (partita.richiesta === "attaccanti") await invia(`attacca con ${ids.join(", ")}`);
  else avvisa("Non si è arrivati alla dichiarazione degli attaccanti: " + ($("messaggio").textContent || ""));
}

function bottone(testo, azione) {
  return el("button", { type: "button", textContent: testo, onclick: azione });
}

let cambi = { entra: {}, esce: {} };
const conCarta = (e, nome) => { e.dataset.carta = nome; return e; };

function apriSideboard() {
  cambi = { entra: {}, esce: {} };
  disegnaSideboard();
}

function sposta(dove, nome, delta, massimo) {
  const attuale = (cambi[dove][nome] || 0) + delta;
  cambi[dove][nome] = Math.max(0, Math.min(massimo, attuale));
  disegnaSideboard();
}

function disegnaSideboard() {
  const pannello = $("pannello-sideboard");
  const liste = partita.incontro && partita.incontro.liste;
  if (!liste) { pannello.hidden = true; return; }
  pannello.hidden = false;
  const tot = (d) => Object.values(d).reduce((a, b) => a + b, 0);
  const colonna = (titolo, lista, dove, testo) => el("div", { className: "colonna" },
    el("h3", { textContent: titolo }),
    ...Object.entries(lista).sort().map(([nome, q]) => el("div", { className: "riga-side" },
      conCarta(el("span", { textContent: `${q} ${nome}` }), nome),
      el("span", { className: "cambio", textContent: cambi[dove][nome] ? `${testo} ${cambi[dove][nome]}` : "" }),
      bottone("−", () => sposta(dove, nome, -1, q)), bottone("+", () => sposta(dove, nome, 1, q)))));
  const pari = tot(cambi.entra) === tot(cambi.esce);
  pannello.replaceChildren(
    el("h2", { textContent: `Sideboard prima della partita ${partita.incontro.numero + 1}` }),
    el("div", { className: "colonne" },
      colonna("Mazzo (togli)", liste.mazzo, "esce", "esce"),
      colonna("Sideboard (metti)", liste.sideboard, "entra", "entra")),
    el("p", { textContent: pari ? `Scambi: ${tot(cambi.entra)}` : `Togli ${tot(cambi.entra)} carte dal mazzo per metterne ${tot(cambi.entra)} dalla sideboard (ora: ${tot(cambi.esce)}).` }),
    bottone("Conferma", confermaSideboard), bottone("Chiudi", () => { $("pannello-sideboard").hidden = true; }));
}

async function confermaSideboard() {
  try {
    partita = await api(`/api/partite/${partita.id}/sideboard`, { method: "POST", body: JSON.stringify(cambi) });
    cambi = { entra: {}, esce: {} };
    avvisa("Sideboard aggiornata.");
    disegna();
    disegnaSideboard();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}

async function prossimaPartita() {
  if (inAttesa) return;
  inAttesa = true;
  $("pannello-sideboard").hidden = true;
  try {
    partita = await api(`/api/partite/${partita.id}/prossima`, { method: "POST" });
    azzeraScelteCombattimento();
    avvisa(partita.richiesta === "mulligan" ? "Nuova partita: tieni la mano o fai mulligan." : "Nuova partita.");
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message);
  } finally {
    inAttesa = false;
  }
}

function disegnaBarraCombattimento() {
  const barra = $("barra-combattimento");
  const inc = partita.incontro;
  if (inc && partita.vincitore) {
    barra.hidden = false;
    const fine = inc.vincitore
      ? `Incontro finito: vince ${inc.vincitore} (${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]}).`
      : partita.vincitore === "Pareggio"
        ? `Partita ${inc.numero} finita pari (non conta). Incontro ${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]}.`
        : `Partita ${inc.numero} vinta da ${partita.vincitore}. Incontro ${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]}.`;
    barra.replaceChildren(el("span", { textContent: fine }),
      ...(inc.prossima_possibile ? [bottone("Consiglio sideboard", mostraConsiglio), bottone("Sideboard", apriSideboard),
        bottone(`Partita ${inc.numero + 1}`, prossimaPartita)] : []),
      ...(inc.torneo && inc.vincitore ? [bottone("Torna al torneo", () => { location.href = `torneo.html?id=${inc.torneo}`; })] : []));
    return;
  }
  barra.hidden = !partita.richiesta;
  if (partita.richiesta === "mulligan") {
    const m = partita.mulligan;
    barra.replaceChildren(...(m.tenuta
      ? [el("span", { textContent: `Clicca ${m.da_mettere_in_fondo} ${m.da_mettere_in_fondo === 1 ? "carta" : "carte"} della mano da mettere in fondo al mazzo.` }),
         bottone(`Metti in fondo (${inFondoScelte.size}/${m.da_mettere_in_fondo})`, () => invia(`in fondo ${[...inFondoScelte].join(", ")}`))]
      : [el("span", { textContent: m.fatti ? `Mano iniziale (mulligan fatti: ${m.fatti}).` : "Mano iniziale: la tieni?" }),
         bottone("Tengo", () => invia("tengo")),
         bottone("Mulligan", () => invia("mulligan"))]));
  } else if (partita.richiesta === "scelta" && partita.scelta.tipo === "cerca") {
    const sc = partita.scelta;
    const scelta = el("select", {}, ...sc.carte.map((c) => el("option", { value: c.id, textContent: c.nome })));
    barra.replaceChildren(el("span", { textContent: sc.testo ? sc.testo.charAt(0).toUpperCase() + sc.testo.slice(1) + "." : `${sc.fonte}: scegli una carta.` }), scelta,
      bottone("Scegli", () => invia(`scelgo ${scelta.value}`)));
  } else if (partita.richiesta === "scelta" && partita.scelta.tipo === "danni") {
    const sc = partita.scelta;
    barra.replaceChildren(
      el("span", { textContent: `Banding: dividi i ${sc.danni} danni di ${sc.fonte}. Tutti su una creatura, oppure scrivi «danni 2 su …, 1 su …».` }),
      ...sc.candidate.map((c) => bottone(`Tutti su ${c.nome}`, () => invia(`danni su ${c.id}`))));
  } else if (partita.richiesta === "scelta") {
    barra.replaceChildren(
      el("span", { textContent: `${partita.scelta.carta}: ${partita.scelta.testo}` }),
      bottone(`Paga ${partita.scelta.costo}`, () => invia("paga")),
      bottone("Non pago", () => invia("non pago")));
  } else if (partita.richiesta === "attaccanti") {
    barra.replaceChildren(
      el("span", { textContent: "Combattimento: clicca le creature che attaccano." }),
      bottone(`Attacca con le scelte (${attaccantiScelti.size})`, () => attaccantiScelti.size
        ? invia(`attacca con ${[...attaccantiScelti].join(", ")}`)
        : avvisa("Clicca prima le creature che attaccano (o «Non attacco»).")),
      ...(attaccantiScelti.size > 1 ? [bottone("Attacca in banda", () => invia(`attacca con ${[...attaccantiScelti].join(" + ")}`))] : []),
      bottone("Attacca con tutto", () => invia("attacca con tutto")),
      bottone("Nessun attacco", () => invia("non attacco")));
  } else if (partita.richiesta === "bloccanti") {
    const descrizione = blocchiScelti.map(([a, b]) => `${nomeCarta(b)} blocca ${nomeCarta(a)}`).join("; ");
    barra.replaceChildren(
      el("span", { textContent: descrizione || "Ti attaccano: clicca una tua creatura, poi l'attaccante da bloccare." }),
      bottone("Conferma blocchi", () => invia(blocchiScelti.length
        ? "blocca " + blocchiScelti.map(([a, b]) => `${a} con ${b}`).join("; ") : "nessun blocco")),
      bottone("Nessun blocco", () => invia("nessun blocco")),
      bottone("Ricomincia", () => { azzeraScelteCombattimento(); disegna(); }));
  }
}

const NOMI_MANA = { W: "bianco", U: "blu", B: "nero", R: "rosso", G: "verde", C: "incolore" };

// Bersagli ovvi: non serve cliccarli (Mind Twist si gioca sempre sull'avversaria).
const BERSAGLIO_OVVIO = { "Mind Twist": "avversaria", "Millstone": "avversaria", "Mirror Universe": "avversaria" };

function chiediX(c) {
  if (!c.x) return "";
  const x = prompt(`${c.nome}: quanto vale X?`, "1");
  return x === null ? null : ` x=${parseInt(x, 10) || 0}`;
}

function suMano(c) {
  // scelte tra le carte della mano (scarto a fine turno, Recall...): basta cliccare la carta
  const sc = partita.scelta;
  if (partita.richiesta === "scelta" && sc && sc.carte && sc.carte.some((x) => x.id === c.id)) return invia(`scelgo ${c.id}`);
  if (partita.richiesta === "mulligan") {
    if (!partita.mulligan.tenuta) return;
    inFondoScelte.has(c.id) ? inFondoScelte.delete(c.id) : inFondoScelte.add(c.id);
    return disegna();
  }
  const x = chiediX(c);
  if (x === null) return;
  if (c.bersaglio && BERSAGLIO_OVVIO[c.nome]) return invia(`gioca ${c.nome}${x} su ${BERSAGLIO_OVVIO[c.nome]}`);
  if (c.bersaglio) {
    if (c.bersaglio === "carta_tuo_cimitero") cimiteroAperto = "tu";  // Regrowth: si sceglie nel cimitero
    magiaInAttesa = `gioca ${c.nome}${x}`;
    document.body.classList.add("mirino");
    avvisa(`Scegli il bersaglio di ${c.nome}: clicca una creatura o il nome di un giocatore (Esc per annullare).`);
    return;
  }
  invia(`gioca ${c.nome}${x}`);
}

const FASI = ["stap", "mantenimento", "pescata", "principale 1", "combattimento", "principale 2", "finale"];
const NOMI_FASI = { "stap": "Stap", "mantenimento": "Mantenimento", "pescata": "Pescata", "principale 1": "Principale 1",
  "combattimento": "Combattimento", "principale 2": "Principale 2", "finale": "Finale" };

// Spiegazione a parole di dove siamo nel turno, per chi non conosce le fasi.
function fase() {
  const p = partita, comb = p.combattimento, mio = p.attivo === "Tu";
  switch (p.fase) {
    case "stap": return "Stap: si stappano le carte di chi è di turno.";
    case "mantenimento": return "Mantenimento: scattano gli effetti di inizio turno.";
    case "pescata": return mio ? "Pescata: peschi una carta." : "Pescata: l'avversaria pesca.";
    case "principale 1": return mio
      ? "Fase principale 1: gioca una terra (una per turno), creature, artefatti, incantesimi e stregonerie."
      : "Fase principale 1 dell'avversaria: sta giocando le sue carte.";
    case "combattimento":
      if (!comb || !comb.attaccanti_dichiarati) return mio ? "Combattimento: scegli chi attacca." : "Combattimento: l'avversaria sceglie chi attacca.";
      if (!comb.attaccanti.length) return "Combattimento: nessun attacco.";
      if (!comb.bloccanti_dichiarati) return mio ? "Combattimento: l'avversaria sceglie i bloccanti."
        : partita.richiesta === "bloccanti" ? "Combattimento: ti attaccano, scegli i bloccanti."
        : "Ti attaccano! Prima dei blocchi puoi usare abilità (es. animare Mishra's Factory) o istantanei.";
      if (!comb.danni_inflitti) return (comb.primo_passo_fatto ? "Danni di «attacca per primo» fatti. " : "Blocchi fatti. ")
        + "Ultima occasione per gli istantanei (es. Giant Growth) prima dei danni.";
      return "Danni del combattimento fatti.";
    case "principale 2": return mio ? "Fase principale 2: dopo il combattimento puoi ancora giocare carte." : "Fase principale 2 dell'avversaria.";
    case "finale": return mio ? "Fase finale: il turno sta per finire (con più di 7 carte in mano scarti)."
      : "Fase finale dell'avversaria: ultimo momento per i tuoi istantanei (es. Ancestral Recall) prima del tuo turno.";
  }
  return "";
}

function giocabiliInMano() {
  return partita.giocatori[0].mano.filter((c) => c.giocabile && !/\bLand\b/.test(c.tipo)).map((c) => c.nome);
}

function cosaFare() {
  const p = partita;
  if (p.richiesta === "mulligan") return "Guarda la tua mano: «Tengo» o «Mulligan».";
  if (p.richiesta === "attaccanti") return "Clicca le tue creature che attaccano, poi «Attacca con le scelte» (o «Nessun attacco»).";
  if (p.richiesta === "bloccanti") return "Clicca una tua creatura e poi l'attaccante che deve bloccare, poi «Conferma blocchi».";
  if (p.richiesta === "scelta") return "Rispondi alla scelta qui sotto (se riguarda la tua mano puoi cliccare la carta).";
  if (p.priorita !== "Tu") return "L'avversaria sta giocando…";
  const carte = [...new Set(giocabiliInMano())];
  const puoi = carte.length ? ` Ora puoi usare: ${carte.join(", ")} (illuminate in verde).` : "";
  if (p.pila.length) return `In pila c'è ${p.pila[p.pila.length - 1].nome}.` + puoi + " Altrimenti «Lascia risolvere».";
  if (p.attivo === "Tu" && p.fase === "principale 1")
    return ("Clicca una carta della mano per giocarla; clicca una tua creatura per attaccare o usare un'abilità." + puoi).trim();
  return (puoi || "Non hai carte da giocare in questo momento.").trim();
}

// I pulsanti dicono cosa succede davvero passando la priorità in quel momento.
function azioniTurno() {
  const p = partita, comb = p.combattimento, mio = p.attivo === "Tu";
  if (magiaInAttesa) return [bottone("Annulla", annullaBersaglio)];
  if (attaccantiScelti.size && (p.fase === "principale 1" || p.richiesta === "attaccanti"))
    return [bottone(`⚔ Attacca con ${attaccantiScelti.size}`, attaccaConScelte), bottone("Annulla attacco", () => { attaccantiScelti = new Set(); disegna(); })];
  if (p.vincitore || p.richiesta || p.priorita !== "Tu") return [];
  if (p.pila.length) return [bottone("Lascia risolvere", () => invia("passa"))];
  if (mio && p.fase === "principale 1") return [bottone("⚔ Vai al combattimento", () => invia("passa")), bottone("Fine turno", () => invia("fine turno"))];
  if (mio && p.fase === "principale 2") return [bottone("Fine turno", () => invia("fine turno"))];
  if (mio && p.fase === "combattimento" && comb && comb.bloccanti_dichiarati && !comb.danni_inflitti && comb.attaccanti.length)
    return [bottone("Vai ai danni", () => invia("passa"))];
  if (mio) return [bottone("Avanti", () => invia("passa")), bottone("Fine turno", () => invia("fine turno"))];
  if (comb && comb.bloccanti_dichiarati && !comb.danni_inflitti && comb.attaccanti.length) return [bottone("Vai ai danni", () => invia("passa"))];
  if (comb && comb.attaccanti_dichiarati && !comb.bloccanti_dichiarati && comb.attaccanti.length) return [bottone("Vai ai blocchi", () => invia("passa"))];
  if (p.fase === "finale") return [bottone("Passa al mio turno", () => invia("passa"))];
  return [bottone("Continua", () => invia("passa"))];
}

function disegnaTurno() {
  const banner = $("turno");
  banner.hidden = false;
  if (partita.vincitore) {
    banner.className = "finito";
    banner.replaceChildren(el("strong", { textContent: partita.vincitore === "Pareggio" ? "PARTITA PARI"
      : partita.vincitore === "Tu" ? "HAI VINTO LA PARTITA" : "HA VINTO L'AVVERSARIA" }));
    return;
  }
  const mio = partita.attivo === "Tu";
  const tocca = partita.priorita === "Tu" || ["attaccanti", "bloccanti", "scelta", "mulligan"].includes(partita.richiesta);
  banner.className = mio ? "mio" : "suo";
  banner.replaceChildren(
    el("div", { className: "chi" },
      el("strong", { textContent: mio ? `IL TUO TURNO (${partita.turno})` : `TURNO DELL'AVVERSARIA (${partita.turno})` }),
      el("span", { className: "tocca" + (tocca ? " a-te" : ""), textContent: tocca ? "● tocca a te" : "○ aspetta" })),
    el("ol", { className: "fasi" }, ...FASI.map((f) => el("li", {
      className: f === partita.fase ? "corrente" : "", textContent: NOMI_FASI[f] }))),
    el("div", { className: "spiegazione" },
      el("div", { className: "fase-ora", textContent: fase() }),
      el("div", { className: "cosa-fare", textContent: cosaFare() })),
    el("div", { className: "azioni-turno" }, ...azioniTurno()));
}

const vitaPrima = {};  // per far lampeggiare i punti vita quando cambiano

function vitaEl(g, umano) {
  const prima = vitaPrima[g.nome];
  vitaPrima[g.nome] = g.vita;
  const classe = prima === undefined || prima === g.vita ? "" : g.vita < prima ? " scende" : " sale";
  const e = el("span", { className: "vita" + (umano ? " mia" : "") + classe + (g.vita <= 5 ? " bassa" : ""),
    title: "Punti vita" }, el("span", { className: "cuore", textContent: "♥" }), el("b", { textContent: g.vita }));
  if (prima !== undefined && prima !== g.vita)
    e.append(el("span", { className: "delta", textContent: (g.vita > prima ? "+" : "") + (g.vita - prima) }));
  return e;
}

let cimiteroAperto = null;  // "tu" / "avversaria" / null

function disegnaGiocatore(sezione, g, umano) {
  const mioTurno = partita.attivo === g.nome && !partita.vincitore;
  sezione.classList.toggle("di-turno", mioTurno);
  const titolo = el("h2", {
    className: "nome-giocatore",
    onclick: () => magiaInAttesa && scegliBersaglio(umano ? "me" : "avversaria"),
  },
    el("span", { className: "nome", textContent: umano ? "Tu" : "Avversaria" }),
    vitaEl(g, umano),
    ...(umano ? [] : [el("span", { className: "dato", textContent: `mano ${g.mano}` }),
      el("span", { className: "dorsi" }, ...Array.from({ length: Math.min(g.mano, 12) }, () => el("span", { className: "dorso" })))]),
    ...(g.riserva && g.riserva !== "vuota" ? [el("span", { className: "dato", textContent: `mana ${g.riserva}` })] : []),
    ...(mioTurno ? [el("span", { className: "badge-turno", textContent: umano ? "tuo turno" : "suo turno" })] : []));
  const etichetta = (t) => el("div", { className: "etichetta", textContent: t });
  const fila = (carte, azione, classe = "") => el("div", { className: "fila " + classe }, ...carte.map((c) => cartaEl(c, azione)));
  const terre = g.campo.filter((c) => /\bLand\b/.test(c.tipo) && c.forza == null);
  const altri = g.campo.filter((c) => !terre.includes(c));
  const suQuesto = (c) => suCampo(c, umano);
  const righe = umano
    ? [fila(altri, suQuesto, "permanenti"), fila(terre, suQuesto, "terre")]
    : [fila(terre, suQuesto, "terre"), fila(altri, suQuesto, "permanenti")];
  const campo = el("div", { className: "campo" }, ...righe);
  if (!g.campo.length) campo.append(el("div", { className: "vuoto", textContent: "Nessun permanente in campo" }));
  sezione.replaceChildren(titolo, el("div", { className: "area-giocatore" }, campo, mucchi(g, umano)));
}

// Grimorio e cimitero come sul tavolo vero: il grimorio è coperto (si vede quante carte ha; con Field of Dreams
// la prima è scoperta), il cimitero mostra l'ultima carta finita lì e si apre con un clic.
function mucchi(g, umano) {
  const chiave = umano ? "tu" : "avversaria";
  const grimorio = el("div", { className: "mucchio grimorio", title: g.cima
      ? `Grimorio: ${g.grimorio} carte. In cima, scoperta per Field of Dreams: ${g.cima}` : `Grimorio: ${g.grimorio} carte (coperte)` },
    g.cima ? conCarta(el("div", { className: "carta mucchio-carta" }, faccia({ nome: g.cima, tipo: "", costo: "", testo: "" })), g.cima)
      : el("div", { className: "carta mucchio-carta dorso-grande" }),
    el("span", { className: "conta", textContent: g.grimorio }),
    el("span", { className: "nome-mucchio", textContent: g.cima ? "Grimorio · cima scoperta" : "Grimorio" }));
  const ultima = g.cimitero[g.cimitero.length - 1];
  const cimitero = el("div", { className: "mucchio cimitero" + (g.cimitero.length ? " pieno" : ""),
    title: g.cimitero.length ? `Cimitero: ${g.cimitero.length} carte — clic per vederle tutte` : "Cimitero vuoto",
    onclick: (e) => { e.stopPropagation(); if (!g.cimitero.length) return; cimiteroAperto = cimiteroAperto === chiave ? null : chiave; disegna(); } },
    ultima ? conCarta(el("div", { className: "carta mucchio-carta" }, faccia(ultima)), ultima.nome)
      : el("div", { className: "carta mucchio-carta vuoto-mucchio" }),
    el("span", { className: "conta", textContent: g.cimitero.length }),
    el("span", { className: "nome-mucchio", textContent: "Cimitero" }));
  return el("div", { className: "mucchi" }, grimorio, cimitero);
}

// Il cimitero si apre in un riquadro con le immagini delle carte (l'ultima entrata per prima).
// Durante la scelta di un bersaglio (Regrowth) si clicca la carta lì dentro.
function disegnaCimitero() {
  const box = $("vista-cimitero");
  const g = cimiteroAperto === "tu" ? partita.giocatori[0] : cimiteroAperto === "avversaria" ? partita.giocatori[1] : null;
  box.hidden = !g || !g.cimitero.length;
  if (box.hidden) return;
  box.replaceChildren(el("div", { className: "riquadro" },
    el("div", { className: "testata" },
      el("h2", { textContent: `Cimitero ${cimiteroAperto === "tu" ? "tuo" : "dell'avversaria"} (${g.cimitero.length})` }),
      bottone("✕", () => { cimiteroAperto = null; disegna(); })),
    el("div", { className: "griglia-cimitero" }, ...g.cimitero.slice().reverse().map((c) => cartaEl(c, () => {
      if (magiaInAttesa) { cimiteroAperto = null; scegliBersaglio(c.id); }
    })))));
}

function disegnaMano() {
  const g = partita.giocatori[0];
  $("mano").replaceChildren(el("div", { className: "etichetta", textContent: `La tua mano (${g.mano.length})` }),
    el("div", { className: "fila mano-carte" }, ...g.mano.map((c) => cartaEl(c, suMano))));
}

function disegna() {
  const inc = partita.incontro;
  const punteggio = inc ? `Incontro ${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]} · partita ${inc.numero}` : "";
  $("info").textContent = punteggio + (inc && inc.mazzo_avversaria ? ` · contro ${inc.mazzo_avversaria}` : "");
  disegnaTurno();
  disegnaGiocatore($("avversaria"), partita.giocatori[1], false);
  disegnaGiocatore($("tu"), partita.giocatori[0], true);
  disegnaMano();
  $("sezione-pila").hidden = !partita.pila.length;
  $("pila").replaceChildren(...(partita.pila.length
    ? partita.pila.slice().reverse().map((o) => el("span", { className: "oggetto-pila",
        textContent: `${o.nome}${o.x ? " X=" + o.x : ""}${o.bersaglio ? " → " + o.bersaglio : ""} (${o.controllore === "Tu" ? "tua" : "avversaria"})`,
        onclick: () => magiaInAttesa && scegliBersaglio(o.id) }))
    : [el("span", { className: "dettaglio", textContent: "vuota" })]));
  disegnaBarraCombattimento();
  disegnaGiocataAvversaria();
  if (inc && inc.prossima_possibile && consiglioMostratoPer !== `${partita.id}:${inc.numero}`) {
    consiglioMostratoPer = `${partita.id}:${inc.numero}`;  // a fine partita il consiglio compare da solo, una volta
    mostraConsiglio();
  }
  disegnaCimitero();
  $("eventi").replaceChildren(...partita.eventi.slice().reverse().map((t) => el("li", { textContent: t })));
}

let inAttesa = false;  // una richiesta di gioco alla volta: un doppio clic non manda due comandi

async function invia(testo) {
  if (inAttesa) return;
  inAttesa = true;
  try {
    const r = await api(`/api/partite/${partita.id}/comando`, { method: "POST", body: JSON.stringify({ testo }) });
    if (r.partita.richiesta !== partita.richiesta || !r.messaggio.startsWith("Mossa non valida")) azzeraScelteCombattimento();
    partita = r.partita;
    avvisa(r.messaggio);
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message);
  } finally {
    inAttesa = false;
  }
}

async function caricaMazzi() {
  const mazzi = await api("/api/mazzi");
  const opzioni = (predefinito) => mazzi.map((m) => el("option", { value: m.nome, textContent: `${m.nome} (${m.totale})`, selected: m.nome === predefinito }));
  $("mazzo").replaceChildren(...opzioni("Verde (prova)"));
  const tc = mazzi.filter((m) => m.origine === "tcdecks").length;
  $("mazzo-avversaria").replaceChildren(
    el("option", { value: "auto", textContent: tc ? `Automatico (top 8 TCDecks: ${tc})` : "Automatico (nessun mazzo TCDecks: prova)", selected: true }),
    ...opzioni(""));
}
caricaMazzi();

// Incontri e tornei salvati (il server li salva dopo ogni mossa e li ricarica all'avvio)
async function caricaSalvati() {
  const salvati = await api("/api/salvataggi");
  $("riquadro-salvati").hidden = !salvati.length;
  $("salvati").replaceChildren(...salvati.map((s) => {
    const o = el("option", { value: s.id,
      textContent: `${s.tipo === "torneo" ? "🏆 " : ""}${s.descrizione} · ${s.aggiornato.replace("T", " ").slice(0, 16)}` });
    o.dataset.tipo = s.tipo;
    return o;
  }));
}
caricaSalvati();

$("riprendi").onclick = () => {
  const scelta = $("salvati").selectedOptions[0];
  if (!scelta) return;
  location.href = scelta.dataset.tipo === "torneo" ? `torneo.html?id=${scelta.value}` : `index.html?incontro=${scelta.value}`;
};

$("elimina-salvato").onclick = async () => {
  const scelta = $("salvati").selectedOptions[0];
  if (!scelta || !confirm(`Eliminare «${scelta.textContent}»?`)) return;
  try {
    await api(`/api/salvataggi/${scelta.value}`, { method: "DELETE" });
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
  caricaSalvati();
};

// Apertura di un incontro esistente (es. dal torneo): index.html?incontro=<id>
(async () => {
  const id = new URLSearchParams(location.search).get("incontro");
  if (!id) return;
  try {
    partita = await api(`/api/partite/${id}`);
    const contro = `${partita.incontro.torneo ? "Incontro del torneo" : "Incontro"} contro ${partita.incontro.mazzo_avversaria}`;
    avvisa(partita.richiesta === "mulligan" ? `${contro}: tieni la mano o fai mulligan.` : `${contro} ripreso.`);
    disegna();
  } catch (e) {
    avvisa("Incontro non trovato: " + e.message);
  }
})();

$("nuova").onclick = async () => {
  try {
    partita = await api("/api/partite", { method: "POST",
      body: JSON.stringify({ mazzo: $("mazzo").value, mazzo_avversaria: $("mazzo-avversaria").value }) });
  } catch (e) {
    return avvisa("Errore: " + e.message);
  }
  avvisa(partita.richiesta === "mulligan" ? "Partita iniziata: tieni la mano o fai mulligan." : "Partita iniziata.");
  disegna();
};

function annullaBersaglio() {
  magiaInAttesa = null;
  document.body.classList.remove("mirino");
  avvisa("Annullato.");
  disegna();
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    chiudiMenu();
    if (cimiteroAperto) { cimiteroAperto = null; disegna(); }
    if (magiaInAttesa) annullaBersaglio();
  }
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#menu-carta") && !e.target.closest(".carta")) chiudiMenu();
});

$("giudice").onsubmit = async (e) => {
  e.preventDefault();
  const q = $("domanda").value.trim();
  if (!q) return;
  try {
    const r = await api(`/api/giudice?q=${encodeURIComponent(q)}`);
    $("risposta-giudice").textContent = r.risposta;
  } catch (err) {
    $("risposta-giudice").textContent = "Errore: " + err.message;
  }
};

// Giudice e registro in pannelli che si aprono solo quando servono
function apriPannello(id) {
  for (const altro of ["pannello-giudice", "pannello-registro"]) if (altro !== id) $(altro).hidden = true;
  $(id).hidden = !$(id).hidden;
  if (id === "pannello-giudice" && !$(id).hidden) $("domanda").focus();
}
$("apri-giudice").onclick = () => apriPannello("pannello-giudice");
$("apri-registro").onclick = () => apriPannello("pannello-registro");
document.querySelectorAll("[data-chiudi]").forEach((b) => (b.onclick = () => { $(b.dataset.chiudi).hidden = true; }));

// Quando l'avversaria mette qualcosa in pila la carta compare in primo piano: «Lascia risolvere» oppure
// «Rispondi» (si chiude il riquadro e si gioca un istantaneo, illuminato in verde).
let rispostaPer = null;  // id dell'oggetto in pila a cui si sta rispondendo (riquadro chiuso)

function disegnaGiocataAvversaria() {
  const box = $("giocata-avversaria");
  const cima = partita.pila[partita.pila.length - 1];
  const mostra = cima && cima.controllore !== "Tu" && partita.priorita === "Tu" && !partita.richiesta
    && !partita.vincitore && rispostaPer !== cima.id && !magiaInAttesa;
  box.hidden = !mostra;
  if (!mostra) return;
  const titolo = cima.tipo === "abilita" ? `L'avversaria attiva un'abilità di ${cima.carta}`
    : cima.tipo === "innesco" ? `Si innesca ${cima.carta} dell'avversaria` : `L'avversaria lancia ${cima.carta}`;
  // le carte con cui puoi rispondere, direttamente nel riquadro: un clic e la usi
  const io = partita.giocatori[0];
  const risposte = [
    ...io.mano.filter((c) => c.giocabile && !/\bLand\b/.test(c.tipo)).map((c) => [c, () =>
      // contromagie e Blast su una magia in pila: il bersaglio è la magia appena lanciata
      cima.tipo === "magia" && (c.bersaglio === "magia" || (c.bersaglio === "blu" && cima.colori.includes("U"))
        || (c.bersaglio === "rosso" && cima.colori.includes("R"))) ? invia(`gioca ${c.nome} su ${cima.id}`) : suMano(c)]),
    ...io.campo.filter((c) => c.giocabile).map((c) => [c, () => suCampo(c, true)]),
  ];
  const sceltaRisposta = risposte.length ? el("div", { className: "risposte" },
    el("div", { className: "etichetta", textContent: "Rispondi con:" }),
    el("div", { className: "fila" }, ...risposte.map(([c, usa]) => cartaEl(c, () => { rispostaPer = cima.id; usa(); disegna(); })))) : null;
  const carta = el("div", { className: "carta grande" }, faccia({ nome: cima.carta, tipo: "", costo: "", testo: cima.testo }));
  carta.dataset.carta = cima.carta;
  box.replaceChildren(el("div", { className: "riquadro" },
    el("div", { className: "titolo-giocata", textContent: titolo }),
    carta,
    el("div", { className: "dettaglio-giocata", textContent: cima.nome
      + (cima.x ? ` (X=${cima.x})` : "") + (cima.bersaglio ? ` → ${cima.bersaglio}` : "") }),
    ...(sceltaRisposta ? [sceltaRisposta] : []),
    el("div", { className: "azioni-giocata" },
      bottone("Lascia risolvere", () => invia("passa")),
      ...(risposte.length ? [bottone("Guarda il tavolo", () => { rispostaPer = cima.id; disegna();
        avvisa("Clicca la carta con cui rispondi (illuminata in verde), oppure «Lascia risolvere» in alto."); })] : []))));
}

$("vista-cimitero").addEventListener("click", (e) => {
  if (e.target.id === "vista-cimitero") { cimiteroAperto = null; disegna(); }  // clic fuori dal riquadro
});

// Consiglio di sideboard tra una partita e l'altra (dalle carte dell'avversaria viste finora)
let consiglioMostratoPer = null;

async function mostraConsiglio() {
  let c;
  try {
    c = await api(`/api/partite/${partita.id}/consiglio-sideboard`);
  } catch (e) {
    return avvisa("Errore: " + e.message);
  }
  const box = $("consiglio-sideboard");
  const riga = (nome, n, motivo, segno) => el("li", {},
    conCarta(el("b", { textContent: `${segno} ${n} ${nome}` }), nome), el("span", { className: "dettaglio", textContent: ` — ${motivo}` }));
  const prossima = partita.incontro.numero + 1;
  const vuoto = !Object.keys(c.entra).length;
  box.replaceChildren(el("div", { className: "riquadro" },
    el("h2", { textContent: `Sideboard per la partita ${prossima}` }),
    el("p", { className: "dettaglio", textContent: c.carte_viste
      ? `Hai visto ${c.carte_viste} carte dell'avversaria (${c.visto}).` : "Non hai ancora visto carte dell'avversaria." }),
    ...(vuoto ? [el("p", { textContent: "Consiglio: nessun cambio. Le carte della tua sideboard non servono più di quelle che hai nel mazzo contro quello che hai visto." })]
      : [el("h3", { textContent: "Metti dentro" }),
         el("ul", {}, ...Object.entries(c.entra).map(([n, q]) => riga(n, q, c.motivi_entra[n], "+"))),
         el("h3", { textContent: "Togli" }),
         el("ul", {}, ...Object.entries(c.esce).map(([n, q]) => riga(n, q, c.motivi_esce[n], "−")))]),
    el("div", { className: "riga-bottoni" },
      ...(vuoto ? [] : [
        bottone(`Applica e gioca la partita ${prossima}`, async () => { box.hidden = true; await applicaConsiglio(c); prossimaPartita(); }),
        bottone("Applica e ritocca", async () => { box.hidden = true; cambi = { entra: { ...c.entra }, esce: { ...c.esce } }; disegnaSideboard(); })]),
      bottone(vuoto ? "Ok" : "Lo faccio io", () => { box.hidden = true; }))));
  box.hidden = false;
}

async function applicaConsiglio(c) {
  try {
    partita = await api(`/api/partite/${partita.id}/sideboard`, { method: "POST", body: JSON.stringify({ entra: c.entra, esce: c.esce }) });
    avvisa("Sideboard fatta come consigliato.");
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}
