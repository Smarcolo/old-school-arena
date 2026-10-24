const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...figli) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...figli);
  return e;
};
let torneo = null;

async function api(percorso, opzioni = {}) {
  const r = await fetch(percorso, { headers: { "Content-Type": "application/json" }, ...opzioni });
  const testo = await r.text();
  let dati = null;
  try { dati = testo ? JSON.parse(testo) : null; } catch { /* risposta non JSON, es. errore 500 in testo */ }
  if (!r.ok) throw new Error((dati && dati.detail) || testo || r.statusText);
  return dati;
}

function avvisa(testo) {
  $("messaggio").textContent = testo;
}

function disegna() {
  const t = $("tabellone");
  t.hidden = false;
  $("info").textContent = `${torneo.nome} · ${torneo.fase}`;
  const turni = torneo.turni.map((turno) => el("div", { className: "turno" },
    el("h3", { textContent: turno.fase }),
    ...turno.sfide.map((s) => el("div", { className: "sfida" + (s.con_umano ? " tua" : "") },
      ...[[s.a, s.posti[0]], [s.b, s.posti[1]]].map(([nome]) => el("div", {
        className: "concorrente" + (s.vincitore === nome ? " vince" : s.vincitore ? " perde" : ""), textContent: nome })),
      el("div", { className: "punteggio", textContent: s.punteggio || (s.con_umano ? "da giocare" : "") })))));
  const azioni = [];
  if (torneo.da_giocare) azioni.push(el("button", { type: "button", textContent: "Gioca il tuo incontro", onclick: gioca }));
  if (torneo.campione) azioni.push(el("p", { className: "campione", textContent: `Vince il torneo: ${torneo.campione}` }));
  t.replaceChildren(el("h2", { textContent: torneo.nome }), el("div", { className: "turni" }, ...turni), ...azioni);
}

async function gioca() {
  try {
    const inc = await api(`/api/tornei/${torneo.id}/gioca`, { method: "POST" });
    location.href = `index.html?incontro=${inc.id}`;
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}

$("crea").onclick = async () => {
  $("crea").disabled = true;
  avvisa("Carico la top 8 da TCDecks e simulo i quarti che non giochi tu…");
  try {
    torneo = await api("/api/tornei", { method: "POST", body: JSON.stringify({
      torneo: $("nome-torneo").value.trim(), mazzo: $("mio-mazzo").value, posto: parseInt($("posto").value, 10) }) });
    history.replaceState(null, "", `torneo.html?id=${torneo.id}`);
    avvisa(torneo.avvisi && torneo.avvisi.length ? "Attenzione: " + torneo.avvisi.join("; ") : "Top 8 pronta.");
    disegna();
  } catch (e) {
    avvisa("Errore: " + e.message + " — Se non si risolve, le pagine ricevute da TCDecks sono nella cartella " +
      "data\\tcdecks_diagnosi del gioco: mandale a chi sistema il programma. Puoi anche incollare qui l'indirizzo " +
      "della pagina del torneo su tcdecks.net.");
  } finally {
    $("crea").disabled = false;
  }
};

(async () => {
  const mazzi = await api("/api/mazzi");
  $("mio-mazzo").replaceChildren(...mazzi.filter((m) => m.origine !== "tcdecks")
    .map((m) => el("option", { value: m.nome, textContent: `${m.nome} (${m.totale})` })));
  $("posto").replaceChildren(...[1, 2, 3, 4, 5, 6, 7, 8].map((n) => el("option", { value: n, textContent: `${n}° classificato`, selected: n === 8 })));
  const id = new URLSearchParams(location.search).get("id");
  if (id) {
    try {
      torneo = await api(`/api/tornei/${id}`);
      disegna();
    } catch (e) {
      avvisa("Torneo non trovato (forse è stato eliminato): creane uno nuovo.");
    }
  }
})();
