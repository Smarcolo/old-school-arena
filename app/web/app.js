let partita = null;
let magiaInAttesa = null; // nome di una magia che aspetta il clic sul bersaglio
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
  invia(`gioca ${magia} su ${rif}`);
}

function cartaEl(c, azione) {
  const classi = ["carta", c.tappata && "tappata", c.appena_entrata && "appena-entrata", c.danni && "ferita"];
  const e = el("span", { className: classi.filter(Boolean).join(" ") }, c.nome);
  if (c.forza != null) e.append(el("span", { className: "pt", textContent: `${c.forza}/${c.costituzione - c.danni}` }));
  e.title = [c.tipo, c.costo, c.danni ? `${c.danni} danni` : "", c.appena_entrata ? "appena entrata" : ""]
    .filter(Boolean).join(" · ");
  e.onclick = () => azione(c);
  return e;
}

function suCampo(c, mio) {
  if (magiaInAttesa) return scegliBersaglio(c.id);
  if (mio) invia(`tappa ${c.id}`);
}

function suMano(c) {
  if (c.bersaglio) {
    magiaInAttesa = c.nome;
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
  $("eventi").replaceChildren(...partita.eventi.slice().reverse().map((t) => el("li", { textContent: t })));
}

async function invia(testo) {
  try {
    const r = await api(`/api/partite/${partita.id}/comando`, { method: "POST", body: JSON.stringify({ testo }) });
    partita = r.partita;
    avvisa(r.messaggio);
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}

$("nuova").onclick = async () => {
  partita = await api("/api/partite", { method: "POST" });
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
