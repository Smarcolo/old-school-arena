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
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

function avvisa(testo) {
  $("messaggio").textContent = testo;
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

function cartaEl(c, azione) {
  const comb = partita.combattimento;
  const inBanda = comb && comb.bande && comb.bande.some((b) => b.includes(c.id));
  const classi = ["carta", inBanda && "in-banda", c.tappata && "tappata", c.appena_entrata && "appena-entrata", c.danni && "ferita",
    comb && comb.attaccanti.includes(c.id) && "attaccante", comb && comb.bloccanti.includes(c.id) && "bloccante",
    (attaccantiScelti.has(c.id) || inFondoScelte.has(c.id) || bloccanteScelto === c.id || blocchiScelti.some(([, b]) => b === c.id)) && "selezionata"];
  const e = el("span", { className: classi.filter(Boolean).join(" ") }, c.nome);
  e.dataset.carta = c.nome;
  if (c.forza != null) e.append(el("span", { className: "pt", textContent: `${c.forza}/${c.costituzione - c.danni}` }));
  if (c.incanta) e.append(el("span", { className: "abilita", textContent: `incanta ${c.incanta}` }));
  if (c.scudi) e.append(el("span", { className: "abilita scudo", textContent: c.scudi > 1 ? `scudo ×${c.scudi}` : "scudo" }));
  if (c.abilita && c.abilita.length) e.append(el("span", { className: "abilita", textContent: c.abilita.join(", ") }));
  e.title = [c.tipo, c.costo, ...(c.attivabili || []).map((a) => "clic: " + a.testo), c.danni ? `${c.danni} danni` : "", c.appena_entrata ? "appena entrata" : ""]
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
  if (mio && c.attivabili && c.attivabili.length) {
    const ab = c.attivabili[0];
    if (ab.bersaglio) {
      magiaInAttesa = `attiva ${c.id}`;
      document.body.classList.add("mirino");
      return avvisa(`Scegli il bersaglio dell'abilità di ${c.nome} (Esc per annullare).`);
    }
    return invia(`attiva ${c.id}`);
  }
  if (mio) invia(`tappa ${c.id}`);
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
  $("pannello-sideboard").hidden = true;
  try {
    partita = await api(`/api/partite/${partita.id}/prossima`, { method: "POST" });
    azzeraScelteCombattimento();
    avvisa(partita.richiesta === "mulligan" ? "Nuova partita: tieni la mano o fai mulligan." : "Nuova partita.");
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}

function disegnaBarraCombattimento() {
  const barra = $("barra-combattimento");
  const inc = partita.incontro;
  if (inc && partita.vincitore) {
    barra.hidden = false;
    const fine = inc.vincitore
      ? `Incontro finito: vince ${inc.vincitore} (${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]}).`
      : `Partita ${inc.numero} vinta da ${partita.vincitore}. Incontro ${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]}.`;
    barra.replaceChildren(el("span", { textContent: fine }),
      ...(inc.prossima_possibile ? [bottone("Sideboard", apriSideboard), bottone(`Partita ${inc.numero + 1}`, prossimaPartita)] : []),
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
      bottone(`Attacca con le scelte (${attaccantiScelti.size})`, () => invia(`attacca con ${[...attaccantiScelti].join(", ")}`)),
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

function chiediX(c) {
  if (!c.x) return "";
  const x = prompt(`${c.nome}: quanto vale X?`, "1");
  return x === null ? null : ` x=${parseInt(x, 10) || 0}`;
}

function suMano(c) {
  if (partita.richiesta === "mulligan") {
    if (!partita.mulligan.tenuta) return;
    inFondoScelte.has(c.id) ? inFondoScelte.delete(c.id) : inFondoScelte.add(c.id);
    return disegna();
  }
  const x = chiediX(c);
  if (x === null) return;
  if (c.bersaglio) {
    magiaInAttesa = `gioca ${c.nome}${x}`;
    document.body.classList.add("mirino");
    avvisa(`Scegli il bersaglio di ${c.nome}: clicca una creatura o il nome di un giocatore (Esc per annullare).`);
    return;
  }
  invia(`gioca ${c.nome}${x}`);
}

function disegnaGiocatore(sezione, g, umano) {
  const titolo = el("h2", {
    className: "nome-giocatore",
    textContent: `${g.nome} — ${g.vita} vita · grimorio ${g.grimorio} · mana ${g.riserva}` + (umano ? "" : ` · mano ${g.mano}`),
    onclick: () => magiaInAttesa && scegliBersaglio(umano ? "me" : "avversaria"),
  });
  if (partita.priorita === g.nome && !partita.vincitore) titolo.append(el("span", { className: "priorita", textContent: " · ha la priorità" }));
  const etichetta = (t) => el("div", { className: "etichetta", textContent: t });
  const fila = (carte, azione) => el("div", { className: "fila" }, ...carte.map((c) => cartaEl(c, azione)));
  sezione.replaceChildren(titolo, etichetta("Campo"), fila(g.campo, (c) => suCampo(c, umano)));
  if (umano) sezione.append(etichetta("Mano"), fila(g.mano, suMano));
  if (g.cimitero.length) {
    const cim = fila(g.cimitero, (c) => magiaInAttesa && scegliBersaglio(c.id));
    cim.classList.add("cimitero");
    sezione.append(etichetta(`Cimitero (${g.cimitero.length})`), cim);
  }
}

function disegna() {
  const inc = partita.incontro;
  const punteggio = inc ? `Incontro ${inc.vittorie["Tu"]}-${inc.vittorie["Avversaria"]} · partita ${inc.numero} · ` : "";
  $("info").textContent = punteggio + (partita.vincitore
    ? `Partita finita: vince ${partita.vincitore}`
    : `Turno ${partita.turno} · ${partita.fase} · tocca a ${partita.attivo}`);
  disegnaGiocatore($("avversaria"), partita.giocatori[1], false);
  disegnaGiocatore($("tu"), partita.giocatori[0], true);
  $("pila").replaceChildren(...(partita.pila.length
    ? partita.pila.slice().reverse().map((o) => el("span", { className: "carta",
        textContent: `${o.nome}${o.x ? " X=" + o.x : ""}${o.bersaglio ? " → " + o.bersaglio : ""} (${o.controllore})`,
        onclick: () => magiaInAttesa && scegliBersaglio(o.id) }))
    : [el("span", { textContent: "vuota" })]));
  disegnaBarraCombattimento();
  $("eventi").replaceChildren(...partita.eventi.slice().reverse().map((t) => el("li", { textContent: t })));
}

async function invia(testo) {
  try {
    const r = await api(`/api/partite/${partita.id}/comando`, { method: "POST", body: JSON.stringify({ testo }) });
    if (r.partita.richiesta !== partita.richiesta || !r.messaggio.startsWith("Mossa non valida")) azzeraScelteCombattimento();
    partita = r.partita;
    avvisa(r.messaggio);
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message);
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

function attivaComandi() {
  $("testo").disabled = false;
  $("comando").querySelectorAll("button").forEach((b) => (b.disabled = false));
}

// Apertura di un incontro esistente (es. dal torneo): index.html?incontro=<id>
(async () => {
  const id = new URLSearchParams(location.search).get("incontro");
  if (!id) return;
  try {
    partita = await api(`/api/partite/${id}`);
    attivaComandi();
    avvisa(partita.richiesta === "mulligan" ? `Incontro del torneo contro ${partita.incontro.mazzo_avversaria}: tieni la mano o fai mulligan.` : "Incontro ripreso.");
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
  $("testo").disabled = false;
  $("comando").querySelectorAll("button").forEach((b) => (b.disabled = false));
  avvisa(partita.richiesta === "mulligan" ? "Partita iniziata: tieni la mano o fai mulligan." : "Partita iniziata. Scrivi «aiuto» per i comandi.");
  disegna();
  $("testo").focus();
};

$("comando").onsubmit = (e) => {
  e.preventDefault();
  const testo = $("testo").value.trim();
  if (testo) invia(testo);
  $("testo").value = "";
};

document.querySelectorAll(".rapido").forEach((b) => (b.onclick = () => invia(b.dataset.comando)));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && magiaInAttesa) {
    magiaInAttesa = null;
    document.body.classList.remove("mirino");
    avvisa("Annullato.");
  }
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
