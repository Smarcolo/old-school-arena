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
  const testo = await r.text();
  let dati = null;
  try { dati = testo ? JSON.parse(testo) : null; } catch { /* risposta non JSON, es. errore 500 in testo */ }
  if (!r.ok) throw new Error((dati && dati.detail) || testo || r.statusText);
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

async function analizza(dalTesto = false) {
  try {
    const a = await api("/api/mazzi/analizza", { method: "POST", body: JSON.stringify({ testo: $("lista").value }) });
    Object.assign(infoCarte, a.carte || {});
    if (dalTesto) { mazzo = { ...a.mazzo }; side = { ...a.sideboard }; }
    disegnaLista();
    mostraAnalisi(a);
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
  caricaModello(m);
  avvisa(`Aperto «${m.nome}».`);
}

// --- Deck builder: la lista vive in `mazzo`/`side`; il testo è sempre allineato (si salva quello) ---------
let mazzo = {}, side = {}, infoCarte = {};
const GRUPPI = [["Creature", "Creature"], ["Instant", "Istantanei"], ["Sorcery", "Stregonerie"], ["Artifact", "Artefatti"],
  ["Enchantment", "Incantesimi"], ["Land", "Terre"]];

function gruppoDi(nome) {
  const tipo = (infoCarte[nome] || {}).tipo || "";
  const g = GRUPPI.find(([chiave]) => tipo.includes(chiave));
  return g ? g[1] : "Altro";
}

function testoDaLista() {
  const righe = (lista) => Object.entries(lista).filter(([, n]) => n > 0).map(([nome, n]) => `${n} ${nome}`);
  return [...righe(mazzo), ...(Object.keys(side).length ? ["", "Sideboard", ...righe(side)] : [])].join("\n");
}

function cambia(dove, nome, delta) {
  const lista = dove === "side" ? side : mazzo;
  lista[nome] = Math.max(0, (lista[nome] || 0) + delta);
  if (!lista[nome]) delete lista[nome];
  $("lista").value = testoDaLista();
  disegnaLista();
  clearTimeout(ritardoAnalisi);
  ritardoAnalisi = setTimeout(analizza, 300);
}

function sposta(da, a, nome) {
  cambia(da, nome, -1);
  cambia(a, nome, +1);
}

function miniatura(nome) {
  const img = el("img", { src: urlImmagine(nome), alt: "", loading: "lazy" });
  img.onerror = () => img.remove();
  return conCarta(el("span", { className: "miniatura" }, img), nome);
}

function rigaCarta(nome, n, dove) {
  const info = infoCarte[nome] || {};
  return conCarta(el("div", { className: "riga-carta" },
    miniatura(nome),
    el("span", { className: "quante", textContent: n }),
    el("span", { className: "nome-carta", textContent: nome }),
    el("span", { className: "costo-carta", textContent: info.costo || "" }),
    el("button", { type: "button", textContent: "−", title: "Togli una copia", onclick: () => cambia(dove, nome, -1) }),
    el("button", { type: "button", textContent: "+", title: "Aggiungi una copia", onclick: () => cambia(dove, nome, +1) }),
    el("button", { type: "button", className: "secondario", textContent: dove === "side" ? "→ Mazzo" : "→ SB",
      title: dove === "side" ? "Sposta una copia nel mazzo" : "Sposta una copia in sideboard",
      onclick: () => sposta(dove, dove === "side" ? "mazzo" : "side", nome) })), nome);
}

function disegnaLista() {
  const tot = (l) => Object.values(l).reduce((a, b) => a + b, 0);
  $("totali").textContent = `Mazzo ${tot(mazzo)} · Sideboard ${tot(side)}`;
  const blocchi = [];
  const perGruppo = {};
  for (const [nome, n] of Object.entries(mazzo)) (perGruppo[gruppoDi(nome)] ||= []).push([nome, n]);
  for (const [, titolo] of [...GRUPPI, ["", "Altro"]]) {
    const voci = perGruppo[titolo];
    if (!voci) continue;
    blocchi.push(el("h3", { textContent: `${titolo} (${voci.reduce((a, [, n]) => a + n, 0)})` }),
      ...voci.sort((a, b) => a[0].localeCompare(b[0])).map(([nome, n]) => rigaCarta(nome, n, "mazzo")));
  }
  if (!blocchi.length) blocchi.push(el("p", { className: "dettaglio", textContent:
    "Mazzo vuoto: aggiungi carte dalla ricerca a destra, oppure incolla una lista nella scheda «Testo»." }));
  const voci = Object.entries(side).sort((a, b) => a[0].localeCompare(b[0]));
  blocchi.push(el("h3", { className: "titolo-side", textContent: `Sideboard (${tot(side)})` }),
    ...(voci.length ? voci.map(([nome, n]) => rigaCarta(nome, n, "side")) : [el("p", { className: "dettaglio", textContent: "Vuota." })]));
  $("vista-carte").replaceChildren(...blocchi);
}

let ultimaRicerca = 0;  // le risposte arrivate in ritardo (ricerca già cambiata) si scartano

async function cercaCarte() {
  const numero = ++ultimaRicerca;
  const colore = document.querySelector("#filtri-colore .filtro.attivo")?.dataset.colore || "";
  const parametri = new URLSearchParams({ q: $("cerca").value, limite: 60, colore, tipo: $("filtro-tipo").value });
  const carte = await api(`/api/carte?${parametri}`);
  if (numero !== ultimaRicerca) return;
  $("risultati").replaceChildren(...carte.map((c) => {
    infoCarte[c.nome] = c;
    return conCarta(el("div", { className: "tessera", title: `${c.tipo} ${c.costo || ""}\n${c.testo || ""}` },
      el("div", { className: "carta-tessera", onclick: () => { cambia("mazzo", c.nome, +1); avvisa(`+1 ${c.nome} nel mazzo`); } },
        faccia(c)),
      el("div", { className: "bottoni-tessera" },
        el("button", { type: "button", textContent: "+ Mazzo", onclick: () => cambia("mazzo", c.nome, +1) }),
        el("button", { type: "button", className: "secondario", textContent: "SB", onclick: () => cambia("side", c.nome, +1) }))), c.nome);
  }));
}

// faccia della carta: disegnata sotto, immagine sopra quando arriva
function faccia(c) {
  const contenitore = el("div", { className: "faccia" }, el("div", { className: "faccia-testo" },
    el("div", { className: "riga-nome" }, el("b", { textContent: c.nome }), el("span", { textContent: c.costo || "" })),
    el("div", { className: "riga-tipo", textContent: c.tipo || "" }),
    el("div", { className: "riga-testo", textContent: c.testo || "" })));
  const img = el("img", { src: urlImmagine(c.nome), alt: c.nome, loading: "lazy" });
  img.onload = () => img.classList.add("caricata");
  img.onerror = () => img.remove();
  contenitore.append(img);
  return contenitore;
}

let ritardoRicerca = null;
$("cerca").addEventListener("input", () => { clearTimeout(ritardoRicerca); ritardoRicerca = setTimeout(cercaCarte, 250); });
$("filtro-tipo").onchange = cercaCarte;
document.querySelectorAll("#filtri-colore .filtro").forEach((b) => (b.onclick = () => {
  const era = b.classList.contains("attivo");
  document.querySelectorAll("#filtri-colore .filtro").forEach((x) => x.classList.remove("attivo"));
  if (!era) b.classList.add("attivo");
  cercaCarte();
}));
document.querySelectorAll(".scheda").forEach((b) => (b.onclick = () => {
  document.querySelectorAll(".scheda").forEach((x) => x.classList.toggle("attiva", x === b));
  document.querySelectorAll(".vista-scheda").forEach((v) => (v.hidden = v.id !== b.dataset.scheda));
}));

$("salva").onclick = async () => {
  const nome = $("nome").value.trim();
  if (!nome) return avvisa("Dai un nome al mazzo.");
  try {
    const m = await api(`/api/mazzi/${encodeURIComponent(nome)}`, { method: "PUT", body: JSON.stringify({ testo: $("lista").value }) });
    $("lista").value = m.testo;
    caricaModello(m);
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
    mazzo = {}; side = {};
    disegnaLista();
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
  mazzo = {}; side = {};
  disegnaLista();
  $("analisi").replaceChildren();
  $("nome").focus();
};

caricaElenco();
cercaCarte();
disegnaLista();

function caricaModello(m) {
  Object.assign(infoCarte, m.carte || {});
  mazzo = { ...m.mazzo };
  side = { ...m.sideboard };
  disegnaLista();
  mostraAnalisi(m);
}

// Mazzi del PC pubblicati per l'iPad (app/cards/condivisione.py). Nella versione per iPad la sezione non serve.
function mostraCondivisione(c) {
  $("chiave-ipad").hidden = c.chiave && !c.errore;
  $("stato-ipad").textContent = !c.chiave
    ? "Per vedere questi mazzi anche sull'iPad incolla una volta la chiave di GitHub (vedi le istruzioni ricevute)."
    : c.errore ? `Non riesco a mandarli: ${c.errore}.`
    : c.ultimo ? `Collegato: ogni mazzo che salvi arriva anche sull'iPad (ultimo invio ${c.ultimo}; sull'iPad ricarica la pagina dopo un paio di minuti).`
    : "Collegato: ogni mazzo che salvi arriva anche sull'iPad.";
}
if (window.PONTE) $("sezione-ipad").hidden = true;
else api("/api/condivisione").then(mostraCondivisione).catch(() => { $("sezione-ipad").hidden = true; });
$("salva-chiave").onclick = async () => {
  try {
    mostraCondivisione(await api("/api/condivisione", { method: "POST", body: JSON.stringify({ testo: $("chiave-github").value }) }));
    $("chiave-github").value = "";
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
};

$("copia-mazzi").onclick = async () => {
  const { testo } = await api("/api/trasferimento-mazzi");
  $("trasferimento").value = testo;
  try {
    await navigator.clipboard.writeText(testo);
    avvisa("Mazzi copiati: incollali in una mail o un messaggio per l'altro dispositivo.");
  } catch {
    $("trasferimento").select();
    avvisa("Il testo è selezionato nel riquadro: tienilo premuto (o Ctrl+C) e scegli «Copia».");
  }
};

$("importa-mazzi").onclick = async () => {
  try {
    const r = await api("/api/trasferimento-mazzi", { method: "POST", body: JSON.stringify({ testo: $("trasferimento").value }) });
    avvisa(`Importati ${r.importati.length} mazzi.`);
    $("trasferimento").value = "";
    caricaElenco();
  } catch (e) {
    avvisa("Errore: " + e.message);
  }
};

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
