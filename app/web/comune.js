// Anteprima dell'immagine della carta al passaggio del mouse (se il server riesce a ottenerla).
const anteprima = Object.assign(document.createElement("img"), { id: "anteprima", alt: "" });
document.body.append(anteprima);
const immaginiMancanti = new Set();

function mostraAnteprima(nome, evento) {
  if (!nome || immaginiMancanti.has(nome) || matchMedia("(hover: none)").matches) return;
  const src = `/api/immagini/${encodeURIComponent(nome)}`;
  if (anteprima.getAttribute("src") !== src) anteprima.src = src;
  anteprima.onerror = () => { immaginiMancanti.add(nome); anteprima.classList.remove("visibile"); };
  anteprima.onload = () => anteprima.classList.add("visibile");
  if (anteprima.complete && anteprima.naturalWidth) anteprima.classList.add("visibile");
  posizionaAnteprima(evento);
}

function posizionaAnteprima(evento) {
  const larghezza = 244, altezza = 340;
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
