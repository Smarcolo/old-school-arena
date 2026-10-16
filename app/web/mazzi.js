const $ = (id) => document.getElementById(id);
const el = (tag, props = {}, ...figli) => {
  const e = Object.assign(document.createElement(tag), props);
  e.append(...figli);
  return e;
};
let ritardoAnalisi = null;
const conCarta = (e, nome) => { e.dataset.carta = nome; return e; };

async function api(percorso, opzioni = {}) {
  const r = await fetch(percorso, { headers: { "Content-Type": "application/json" }, ...opzioni });
  const dati = await r.json();
  if (!r.ok) throw new Error(dati.detail || r.statusText);
  return dati;
}

function avvisa(testo) {
  $("messaggio").textContent = testo;
}

function mostraAnalisi(a) {
  const blocchi = [];
  const stato = a.legale ? "Legale per le regole Swedish caricate" : "Non legale";
  blocchi.push(el("p", { className: a.legale ? "ok" : "ko", textContent:
    `${stato} · ${a.totale} carte + ${a.totale_sideboard} in sideboard · ${a.giocabile ? "si può usare in partita" : "non ancora usabile in partita"}` }));
  const curva = Object.entries(a.curva).map(([costo, n]) => `${costo === "6" ? "6+" : costo}: ${n}`).join(" · ");
  blocchi.push(el("p", { textContent: "Curva di mana: " + curva }));
  const lista = (titolo, voci, classe) => voci.length &&
    blocchi.push(el("h3", { textContent: titolo }), el("ul", { className: classe }, ...voci.map((v) => el("li", { textContent: v }))));
  lista("Problemi", a.problemi, "ko");
  lista("Righe non capite", a.righe_non_capite || [], "ko");
  lista("Avvisi", a.avvisi, "avviso");
  $("analisi").replaceChildren(...blocchi);
}

async function analizza() {
  try {
    mostraAnalisi(await api("/api/mazzi/analizza", { method: "POST", body: JSON.stringify({ testo: $("lista").value }) }));
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
}

async function caricaElenco() {
  const mazzi = await api("/api/mazzi");
  const voce = (m) => el("li", {}, el("button", { type: "button", className: "link", onclick: () => apri(m.nome),
    textContent: m.origine === "tcdecks" ? `${m.info.posizione}° ${m.nome.split(" · ")[0].replace(/^TC \d+° /, "")} — ${m.info.torneo}` : `${m.nome} (${m.totale})` }));
  $("elenco").replaceChildren(...mazzi.filter((m) => m.origine !== "tcdecks").map(voce));
  $("elenco-tc").replaceChildren(...mazzi.filter((m) => m.origine === "tcdecks").map(voce));
}

async function operazioneLunga(bottone, url, testo, resoconto) {
  bottone.disabled = true;
  avvisa(testo);
  try {
    avvisa(resoconto(await api(url, { method: "POST" })));
    caricaElenco();
  } catch (e) {
    avvisa("Errore: " + e.message);
  } finally {
    bottone.disabled = false;
  }
}

$("importa-carte").onclick = () => operazioneLunga($("importa-carte"), "/api/carte/importa",
  "Scarico le carte da Scryfall…", (r) => `Importate ${r.importate} carte dai set ammessi.`);
$("aggiorna-tc").onclick = () => operazioneLunga($("aggiorna-tc"), "/api/tcdecks/aggiorna",
  "Scarico la top 8 degli ultimi tornei da TCDecks (circa un minuto)…", (r) =>
    `Salvati ${r.salvati.length} mazzi.` +
    (r.carte_sconosciute.length ? ` ${r.carte_sconosciute.length} carte non sono nel database: premi «Importa carte da Scryfall» e poi aggiorna di nuovo.` : "") +
    (r.errori.length ? ` Problemi: ${r.errori.slice(0, 3).join("; ")}` : ""));

async function apri(nome) {
  const m = await api(`/api/mazzi/${encodeURIComponent(nome)}`);
  $("nome").value = m.nome;
  $("lista").value = m.testo;
  mostraAnalisi(m);
  avvisa(`Aperto «${m.nome}».`);
}

function aggiungi(nome) {
  const righe = $("lista").value.split("\n");
  const i = righe.findIndex((r) => r.replace(/^\d+\s*x?\s+/i, "").trim().toLowerCase() === nome.toLowerCase());
  if (i >= 0) {
    const n = parseInt(righe[i], 10) || 1;
    righe[i] = `${n + 1} ${nome}`;
  } else {
    const sb = righe.findIndex((r) => /^(sideboard|sb):?$/i.test(r.trim()));
    righe.splice(sb >= 0 ? sb : righe.length, 0, `1 ${nome}`);
  }
  $("lista").value = righe.join("\n").replace(/^\n+/, "");
  analizza();
}

$("lista").addEventListener("input", () => {
  clearTimeout(ritardoAnalisi);
  ritardoAnalisi = setTimeout(analizza, 400);
});

$("cerca").addEventListener("input", async () => {
  const carte = await api(`/api/carte?q=${encodeURIComponent($("cerca").value)}`);
  $("risultati").replaceChildren(...carte.map((c) => conCarta(el("li", {},
    el("button", { type: "button", className: "link", textContent: `+ ${c.nome}`,
      title: `${c.tipo} ${c.costo || ""}\n${c.testo || ""}`, onclick: () => aggiungi(c.nome) }),
    el("span", { className: "dettaglio", textContent: ` ${c.costo || ""} ${c.forza != null ? c.forza + "/" + c.costituzione : ""}` })), c.nome)));
});

$("salva").onclick = async () => {
  const nome = $("nome").value.trim();
  if (!nome) return avvisa("Dai un nome al mazzo.");
  try {
    const m = await api(`/api/mazzi/${encodeURIComponent(nome)}`, { method: "PUT", body: JSON.stringify({ testo: $("lista").value }) });
    $("lista").value = m.testo;
    mostraAnalisi(m);
    avvisa(`Salvato «${nome}».`);
    caricaElenco();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
};

$("elimina").onclick = async () => {
  const nome = $("nome").value.trim();
  if (!nome || !confirm(`Eliminare il mazzo «${nome}»?`)) return;
  try {
    await api(`/api/mazzi/${encodeURIComponent(nome)}`, { method: "DELETE" });
    $("nome").value = "";
    $("lista").value = "";
    $("analisi").replaceChildren();
    avvisa(`Eliminato «${nome}».`);
    caricaElenco();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
};

$("nuovo").onclick = () => {
  $("nome").value = "";
  $("lista").value = "";
  $("analisi").replaceChildren();
  $("nome").focus();
};

caricaElenco();
$("cerca").dispatchEvent(new Event("input"));

$("url-tc").addEventListener("keydown", async (e) => {
  if (e.key !== "Enter" || !$("url-tc").value.trim()) return;
  try {
    const r = await api("/api/tcdecks/mazzo", { method: "POST", body: JSON.stringify({ url: $("url-tc").value.trim() }) });
    avvisa(r.salvati.length ? `Salvato «${r.salvati[0]}».` + (r.carte_sconosciute.length ? ` Carte mancanti: ${r.carte_sconosciute.join(", ")}.` : "")
      : `Non importato: ${r.errori.join("; ")}`);
    $("url-tc").value = "";
    caricaElenco();
  } catch (err) {
    avvisa("Errore: " + err.message);
  }
});
