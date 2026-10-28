// Versione per il browser (iPad): il programma Python gira nella pagina con Pyodide, senza il PC.
// Le pagine restano quelle di app/web: qui si intercettano le richieste a /api/... e si passano ad app/browser.py.
// I dati (mazzi, salvataggi, carte) stanno nel browser (IndexedDB, cartella /dati di Pyodide).
"use strict";

const PYODIDE = "pyodide/";
window.PONTE = true;  // app.js: l'avviso «sta pensando» lo mostra il ponte
let py = null;
let indirizzi = {};  // nome carta in minuscolo -> immagine Scryfall (cornice 1993), dal database delle carte
const fetchVero = window.fetch.bind(window);

// --- Schermata di attesa -------------------------------------------------------------------------------
const attesa = document.createElement("div");
attesa.id = "attesa-ponte";
attesa.innerHTML = `<div><h2>Old School Arena</h2><p id="attesa-testo">Preparo il tavolo…</p>
  <p class="attesa-nota">La prima volta ci vuole qualche secondo in più.</p></div>`;
const stileAttesa = document.createElement("style");
stileAttesa.textContent = `#attesa-ponte{position:fixed;inset:0;z-index:9999;display:grid;place-items:center;
  background:#1d1a16;color:#f2e8d5;font:16px/1.5 Georgia,serif;text-align:center;padding:24px}
  #attesa-ponte h2{margin:0 0 12px;font-size:28px}#attesa-ponte .attesa-nota{opacity:.7;font-size:14px}`;
document.head.appendChild(stileAttesa);
const mostraAttesa = () => document.body && !attesa.isConnected && document.body.appendChild(attesa);
const scriviAttesa = (testo) => { document.getElementById("attesa-testo")?.replaceChildren(testo); };
if (document.body) mostraAttesa(); else document.addEventListener("DOMContentLoaded", mostraAttesa);

// --- Avviso mentre l'avversaria pensa --------------------------------------------------------------------
const avvisoPensiero = document.createElement("div");
avvisoPensiero.id = "pensiero-ponte";
avvisoPensiero.textContent = "L'avversaria sta pensando…";
function mostraPensiero(si) {
  if (si && !avvisoPensiero.isConnected) document.body.appendChild(avvisoPensiero);
  else if (!si) avvisoPensiero.remove();
}

// --- Salvataggio dei dati nel browser -----------------------------------------------------------------
let coda = Promise.resolve();
function salvaDati() {
  coda = coda.then(() => new Promise((ok) => py.FS.syncfs(false, (err) => { if (err) console.warn("salvataggio", err); ok(); })));
  return coda;
}

// --- Carte da Scryfall (dal browser Scryfall si raggiunge; dal Python no) -------------------------------
async function importaCarte() {
  const set = JSON.parse(py.globals.get("browser").set_ammessi());
  let url = "https://api.scryfall.com/cards/search?" + new URLSearchParams(
    { q: `(${set.map((s) => `e:${s}`).join(" or ")})`, unique: "prints", order: "name" });
  const carte = [];
  while (url) {
    scriviAttesa(`Scarico le carte da Scryfall (una volta sola)… ${carte.length}`);
    const r = await fetchVero(url);
    if (!r.ok) throw new Error(`Scryfall ha risposto ${r.status}`);
    const pagina = await r.json();
    for (const c of pagina.data) {
      carte.push({ name: c.name, set: c.set, type_line: c.type_line, mana_cost: c.mana_cost, power: c.power,
        toughness: c.toughness, oracle_text: c.oracle_text, image_uris: c.image_uris && { normal: c.image_uris.normal },
        ...(c.card_faces ? { card_faces: true } : {}) });
    }
    url = pagina.has_more ? pagina.next_page : null;
    await new Promise((ok) => setTimeout(ok, 120));  // Scryfall chiede di non superare ~10 richieste al secondo
  }
  const n = py.globals.get("browser").importa_carte_da_json(JSON.stringify(carte));
  indirizzi = JSON.parse(py.globals.get("browser").indirizzi_immagini());
  await salvaDati();
  return n;
}

// --- Avvio ---------------------------------------------------------------------------------------------
async function avvia() {
  const script = document.createElement("script");
  script.src = PYODIDE + "pyodide.js";
  await new Promise((ok, ko) => { script.onload = ok; script.onerror = () => ko(new Error("pyodide.js non trovato")); document.head.appendChild(script); });
  py = await loadPyodide({ indexURL: new URL(PYODIDE, location.href).href });
  scriviAttesa("Preparo il tavolo… (2/3)");
  await py.loadPackage("sqlite3");
  const codice = await (await fetchVero("app.zip", { cache: "no-cache" })).arrayBuffer();
  py.unpackArchive(codice, "zip", { extractDir: "/progetto" });
  py.FS.mkdirTree("/dati");
  py.FS.mount(py.FS.filesystems.IDBFS, {}, "/dati");
  await new Promise((ok) => py.FS.syncfs(true, (err) => { if (err) console.warn("lettura dati", err); ok(); }));
  try {  // ultimi tornei TCDecks preparati su GitHub (dal browser TCDecks non si raggiunge): li legge app/cards/tcdecks.py
    const r = await fetchVero("tornei_tcdecks.json", { cache: "no-cache" });
    if (r.ok) py.FS.writeFile("/dati/tornei_tcdecks.json", await r.text());
  } catch (e) { console.warn("elenco tornei non disponibile", e); }
  try {  // mazzi salvati sul PC (app/cards/condivisione.py): li importa browser.avvia
    const r = await fetchVero("mazzi_pc.json", { cache: "no-cache" });
    if (r.ok) py.FS.writeFile("/dati/mazzi_pc.json", await r.text());
  } catch (e) { console.warn("mazzi del PC non disponibili", e); }
  scriviAttesa("Preparo il tavolo… (3/3)");
  await py.runPythonAsync(`
import os, sys
sys.path.insert(0, "/progetto")
os.environ["OSA_DATI"] = "/dati"
from app import browser
browser.avvia()`);
  await salvaDati();
  const browser = py.globals.get("browser");
  indirizzi = JSON.parse(browser.indirizzi_immagini());
  if (browser.serve_import()) {
    try { await importaCarte(); } catch (e) { console.warn("import Scryfall non riuscito", e); }
  }
  attesa.remove();
}
const pronto = avvia().catch((e) => {
  scriviAttesa(`Non sono riuscito ad avviare il programma: ${e.message}. Ricarica la pagina.`);
  throw e;
});

// --- Le richieste della pagina --------------------------------------------------------------------------
window.fetch = async function (risorsa, opzioni = {}) {
  const url = new URL(typeof risorsa === "string" ? risorsa : risorsa.url, location.href);
  const i = url.pathname.indexOf("/api/");
  if (url.origin !== location.origin || i < 0) return fetchVero(risorsa, opzioni);
  await pronto;
  const metodo = (opzioni.method || "GET").toUpperCase();
  const percorso = url.pathname.slice(i) + url.search;
  let risposta;
  if (percorso.startsWith("/api/carte/importa")) {
    try { risposta = { stato: 200, dati: { importate: await importaCarte() } }; }
    catch (e) { risposta = { stato: 502, dati: { detail: `Scryfall non raggiungibile: ${e.message}` } }; }
  } else {
    // Python blocca la pagina finché lavora: prima si mostra l'avviso e si lascia al browser il tempo di disegnarlo
    const pensa = metodo !== "GET" && percorso.startsWith("/api/partite");
    if (pensa) { mostraPensiero(true); await new Promise((ok) => requestAnimationFrame(() => setTimeout(ok, 0))); }
    try { risposta = JSON.parse(py.globals.get("browser").chiama(metodo, percorso, opzioni.body ?? null)); }
    finally { if (pensa) mostraPensiero(false); }
  }
  if (metodo !== "GET") salvaDati();
  return new Response(JSON.stringify(risposta.dati), { status: risposta.stato, headers: { "Content-Type": "application/json" } });
};

// Immagini: direttamente da Scryfall, la stampa con la cornice del 1993 salvata nel database delle carte.
window.urlImmagine = function (nome) {
  return indirizzi[nome.toLowerCase()]
    || `https://api.scryfall.com/cards/named?format=image&version=normal&exact=${encodeURIComponent(nome)}`;
};
