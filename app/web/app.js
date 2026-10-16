let partita = null;
let magiaInAttesa = null; // comando ("gioca X" o "attiva X") che aspetta il clic sul bersaglio
let attaccantiScelti = new Set(); // id delle tue creature scelte per attaccare
let bloccanteScelto = null; // id della tua creatura che sta per bloccare
let blocchiScelti = []; // coppie [id attaccante, id bloccante]
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
  const classi = ["carta", c.tappata && "tappata", c.appena_entrata && "appena-entrata", c.danni && "ferita",
    comb && comb.attaccanti.includes(c.id) && "attaccante", comb && comb.bloccanti.includes(c.id) && "bloccante",
    (attaccantiScelti.has(c.id) || bloccanteScelto === c.id || blocchiScelti.some(([, b]) => b === c.id)) && "selezionata"];
  const e = el("span", { className: classi.filter(Boolean).join(" ") }, c.nome);
  if (c.forza != null) e.append(el("span", { className: "pt", textContent: `${c.forza}/${c.costituzione - c.danni}` }));
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

function disegnaBarraCombattimento() {
  const barra = $("barra-combattimento");
  barra.hidden = !partita.richiesta;
  if (partita.richiesta === "attaccanti") {
    barra.replaceChildren(
      el("span", { textContent: "Combattimento: clicca le creature che attaccano." }),
      bottone(`Attacca con le scelte (${attaccantiScelti.size})`, () => invia(`attacca con ${[...attaccantiScelti].join(", ")}`)),
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

function suMano(c) {
  if (c.bersaglio) {
    magiaInAttesa = `gioca ${c.nome}`;
    document.body.classList.add("mirino");
    avvisa(`Scegli il bersaglio di ${c.nome}: clicca una creatura o il nome di un giocatore (Esc per annullare).`);
    return;
  }
  invia(`gioca ${c.nome}`);
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
}

function disegna() {
  $("info").textContent = partita.vincitore
    ? `Partita finita: vince ${partita.vincitore}`
    : `Turno ${partita.turno} · ${partita.fase} · tocca a ${partita.attivo}`;
  disegnaGiocatore($("avversaria"), partita.giocatori[1], false);
  disegnaGiocatore($("tu"), partita.giocatori[0], true);
  $("pila").replaceChildren(...(partita.pila.length
    ? partita.pila.slice().reverse().map((o) => el("span", { className: "carta",
        textContent: `${o.nome}${o.bersaglio ? " → " + o.bersaglio : ""} (${o.controllore})` }))
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
  for (const [id, predefinito] of [["mazzo", "Verde (prova)"], ["mazzo-avversaria", "Rosso (prova)"]]) {
    $(id).replaceChildren(...mazzi.map((m) => el("option", { value: m.nome, textContent: `${m.nome} (${m.totale})`, selected: m.nome === predefinito })));
  }
}
caricaMazzi();

$("nuova").onclick = async () => {
  try {
    partita = await api("/api/partite", { method: "POST",
      body: JSON.stringify({ mazzo: $("mazzo").value, mazzo_avversaria: $("mazzo-avversaria").value }) });
  } catch (e) {
    return avvisa("Errore: " + e.message);
  }
  $("testo").disabled = false;
  $("comando").querySelectorAll("button").forEach((b) => (b.disabled = false));
  avvisa("Partita iniziata. Scrivi «aiuto» per i comandi.");
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
