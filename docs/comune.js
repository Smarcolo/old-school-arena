// Anteprima dell'immagine della carta al passaggio del mouse (se il server riesce a ottenerla).
const anteprima = Object.assign(document.createElement("img"), { id: "anteprima", alt: "" });
document.body.append(anteprima);
const immaginiMancanti = new Set();

// «v=1993»: le immagini con la cornice old school hanno un indirizzo nuovo, così il browser non mostra più quelle
// moderne che aveva in memoria dalle versioni precedenti.
function urlImmagine(nome) {
  return `/api/immagini/${encodeURIComponent(nome)}?v=1993`;
}

function mostraAnteprima(nome, evento) {
  if (!nome || immaginiMancanti.has(nome) || matchMedia("(hover: none)").matches) return;
  const src = urlImmagine(nome);
  if (anteprima.getAttribute("src") !== src) anteprima.src = src;
  anteprima.onerror = () => { immaginiMancanti.add(nome); anteprima.classList.remove("visibile"); };
  anteprima.onload = () => anteprima.classList.add("visibile");
  if (anteprima.complete && anteprima.naturalWidth) anteprima.classList.add("visibile");
  posizionaAnteprima(evento);
}

function posizionaAnteprima(evento) {
  const larghezza = 280, altezza = 390;
  const x = evento.clientX + 20 + larghezza > innerWidth ? evento.clientX - larghezza - 20 : evento.clientX + 20;
  const y = Math.min(evento.clientY - 40, innerHeight - altezza - 10);
  anteprima.style.left = `${Math.max(10, x)}px`;
  anteprima.style.top = `${Math.max(10, y)}px`;
}

function nascondiAnteprima() {
  anteprima.classList.remove("visibile");
}

// Delegato: qualunque elemento con data-carta mostra l'anteprima.
document.addEventListener("mouseover", (e) => {
  const t = e.target.closest("[data-carta]");
  if (t) mostraAnteprima(t.dataset.carta, e);
});
document.addEventListener("mousemove", (e) => {
  if (anteprima.classList.contains("visibile") && e.target.closest("[data-carta]")) posizionaAnteprima(e);
});
document.addEventListener("mouseout", (e) => {
  if (e.target.closest("[data-carta]")) nascondiAnteprima();
});

// iPad e telefoni: niente passaggio del mouse. Tenendo premuta una carta compare grande al centro finché non si
// alza il dito; il tocco normale resta un clic (gioca, attacca...). Dopo una pressione lunga il clic si annulla.
let pressioneLunga = null;
let mostrataColTocco = false;

document.addEventListener("touchstart", (e) => {
  const t = e.target.closest("[data-carta]");
  if (!t) return;
  clearTimeout(pressioneLunga);
  pressioneLunga = setTimeout(() => {
    const nome = t.dataset.carta;
    if (immaginiMancanti.has(nome)) return;
    anteprima.src = urlImmagine(nome);
    anteprima.onload = () => anteprima.classList.add("visibile");
    if (anteprima.complete && anteprima.naturalWidth) anteprima.classList.add("visibile");
    const larghezza = Math.min(320, innerWidth - 40);
    anteprima.style.width = `${larghezza}px`;
    anteprima.style.left = `${(innerWidth - larghezza) / 2}px`;
    anteprima.style.top = `${Math.max(10, (innerHeight - larghezza * 1.394) / 2)}px`;
    mostrataColTocco = true;
  }, 450);
}, { passive: true });

function fineTocco() {
  clearTimeout(pressioneLunga);
  if (!mostrataColTocco) return;
  nascondiAnteprima();
  setTimeout(() => { mostrataColTocco = false; }, 500);  // il clic che segue l'alzata del dito arriva prima
}
document.addEventListener("touchend", fineTocco);
document.addEventListener("touchcancel", fineTocco);
document.addEventListener("touchmove", () => clearTimeout(pressioneLunga), { passive: true });
document.addEventListener("click", (e) => {
  if (mostrataColTocco) {  // il dito si è alzato dopo una pressione lunga: non è un clic sulla carta
    mostrataColTocco = false;
    e.stopPropagation();
    e.preventDefault();
  }
}, true);
