let partita = null;
const $ = (id) => document.getElementById(id);

async function api(percorso, opzioni = {}) {
  const r = await fetch(percorso, { headers: { "Content-Type": "application/json" }, ...opzioni });
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

function carte(lista, cliccabile) {
  const fila = document.createElement("div");
  fila.className = "fila";
  for (const c of lista) {
    const el = document.createElement("span");
    el.className = "carta" + (c.tappata ? " tappata" : "");
    el.textContent = c.nome;
    el.title = c.tipo;
    if (cliccabile) el.onclick = () => invia(cliccabile + " " + c.nome);
    fila.append(el);
  }
  return fila;
}

function disegnaGiocatore(sezione, g, umano) {
  sezione.replaceChildren();
  const h = document.createElement("h2");
  h.textContent = `${g.nome} — ${g.vita} vita · grimorio ${g.grimorio}` + (umano ? "" : ` · mano ${g.mano}`);
  sezione.append(h);
  const etichetta = (t) => Object.assign(document.createElement("div"), { className: "etichetta", textContent: t });
  sezione.append(etichetta("Campo"), carte(g.campo, umano ? "tappa" : null));
  if (umano) sezione.append(etichetta("Mano"), carte(g.mano, "gioca"));
}

function disegna() {
  $("info").textContent = partita.vincitore
    ? `Partita finita: vince ${partita.vincitore}`
    : `Turno ${partita.turno} · ${partita.fase} · tocca a ${partita.attivo}`;
  disegnaGiocatore($("avversaria"), partita.giocatori[1], false);
  disegnaGiocatore($("tu"), partita.giocatori[0], true);
  $("eventi").replaceChildren(...partita.eventi.slice().reverse().map((t) => Object.assign(document.createElement("li"), { textContent: t })));
}

async function invia(testo) {
  try {
    const r = await api(`/api/partite/${partita.id}/comando`, { method: "POST", body: JSON.stringify({ testo }) });
    partita = r.partita;
    $("messaggio").textContent = r.messaggio;
    disegna();
  } catch (e) {
    $("messaggio").textContent = "Errore: " + e.message;
  }
}

$("nuova").onclick = async () => {
  partita = await api("/api/partite", { method: "POST" });
  $("testo").disabled = false;
  $("comando").querySelector("button").disabled = false;
  $("messaggio").textContent = "Partita iniziata. Scrivi «aiuto» per i comandi.";
  disegna();
  $("testo").focus();
};

$("comando").onsubmit = (e) => {
  e.preventDefault();
  const testo = $("testo").value.trim();
  if (testo) invia(testo);
  $("testo").value = "";
};
