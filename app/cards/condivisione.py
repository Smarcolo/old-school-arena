"""Mazzi del PC anche sull'iPad (versione nel browser), senza copiare niente a mano.

- PC: ogni volta che si salva o si elimina un mazzo (e all'avvio) `pubblica` scrive i mazzi dell'utente (non quelli
  dei tornei TCDecks, che l'iPad ha già) in docs/mazzi_pc.json sulla repo GitHub del sito, con l'API di GitHub e la
  chiave personale in data/github_token.txt (creata da Marco: solo «Contents» in lettura e scrittura, solo questa
  repo). Senza chiave non fa niente. L'invio va in un thread: il gioco non aspetta la rete.
- iPad: ponte.js scarica mazzi_pc.json dal sito in /dati prima di avviare il programma e `importa_dal_pc` (chiamata
  da browser.avvia) salva i mazzi nuovi o cambiati. Un mazzo con lo stesso nome viene sostituito da quello del PC.
"""
import base64
import json
import threading
from datetime import datetime, timezone

import httpx

from app.cards import mazzi
from app.config import DATI

REPO = "Smarcolo/old-school-arena"
RAMO = "claude/old-school-arena-setup-o0x9qi"
PERCORSO = "docs/mazzi_pc.json"
FILE_CHIAVE = DATI / "github_token.txt"
FILE_DAL_PC = DATI / "mazzi_pc.json"  # sull'iPad: l'ultimo file arrivato dal sito
FILE_IMPORTATO = DATI / "mazzi_pc_importati.txt"  # sull'iPad: data dell'ultimo file già importato
stato = {"ultimo": "", "errore": ""}  # per la pagina Mazzi: quando è riuscito l'ultimo invio, o perché no


def chiave() -> str:
    try:
        return FILE_CHIAVE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def contenuto(conn) -> dict:
    voci = []
    for v in mazzi.elenco(conn):
        if v["origine"] == "tcdecks":
            continue
        mazzo, side = mazzi.leggi(conn, v["nome"])
        voci.append({"nome": v["nome"], "mazzo": mazzo, "sideboard": side, "origine": v["origine"], "info": v["info"]})
    return {"aggiornato": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mazzi": voci}


def _invia(dati: dict, token: str, client=httpx) -> None:
    url = f"https://api.github.com/repos/{REPO}/contents/{PERCORSO}"
    intestazioni = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        esistente = client.get(url, params={"ref": RAMO}, headers=intestazioni, timeout=15)
        sha = esistente.json().get("sha") if esistente.status_code == 200 else None
        testo = json.dumps(dati, ensure_ascii=False, indent=1).encode("utf-8")
        corpo = {"message": f"Mazzi dal PC ({len(dati['mazzi'])})", "branch": RAMO,
                 "content": base64.b64encode(testo).decode("ascii"), **({"sha": sha} if sha else {})}
        risposta = client.put(url, json=corpo, headers=intestazioni, timeout=20)
        if risposta.status_code in (200, 201):
            stato.update(ultimo=datetime.now().strftime("%d/%m %H:%M"), errore="")
        elif risposta.status_code in (401, 403, 404):
            stato["errore"] = (f"GitHub ha rifiutato la chiave (codice {risposta.status_code}): controlla che sia giusta, "
                               "non scaduta e con «Contents: Read and write» sulla repo old-school-arena")
        else:
            stato["errore"] = f"GitHub ha risposto con il codice {risposta.status_code}"
    except Exception as e:
        stato["errore"] = f"invio non riuscito: {e}"


def pubblica(conn, attendi: bool = False, client=httpx) -> bool:
    """Manda i mazzi su GitHub (in un thread, salvo attendi=True). False se manca la chiave."""
    token = chiave()
    if not token:
        stato["errore"] = "manca la chiave di GitHub (data/github_token.txt)"
        return False
    dati = contenuto(conn)  # letti subito, con la connessione del chiamante
    if attendi:
        _invia(dati, token, client)
    else:
        threading.Thread(target=_invia, args=(dati, token, client), daemon=True).start()
    return True


def importa_dal_pc(conn) -> int:
    """Sull'iPad: salva i mazzi del file arrivato dal PC, se non l'ha già fatto. Ritorna quanti."""
    try:
        dati = json.loads(FILE_DAL_PC.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    try:
        gia = FILE_IMPORTATO.read_text(encoding="utf-8").strip()
    except OSError:
        gia = ""
    if dati.get("aggiornato", "") <= gia:
        return 0
    for m in dati.get("mazzi", []):
        mazzi.salva(conn, m["nome"], m["mazzo"], m.get("sideboard", {}), m.get("origine", ""), m.get("info"))
    FILE_IMPORTATO.write_text(dati.get("aggiornato", ""), encoding="utf-8")
    return len(dati.get("mazzi", []))
