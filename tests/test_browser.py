"""Versione per il browser: app/browser.py con i sostituti di FastAPI/pydantic/httpx, in un processo a parte
(i sostituti entrano in sys.modules e non devono toccare gli altri test)."""
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

PROVA = r"""
import json, sys
from app import browser
browser.avvia()
def c(m, u, b=None):
    return json.loads(browser.chiama(m, u, json.dumps(b) if b is not None else None))
assert c("GET", "/api/versione")["stato"] == 200
p = c("POST", "/api/partite")
assert p["stato"] == 200, p
assert c("POST", f"/api/partite/{p['dati']['id']}/comando", {"testo": "tengo"})["stato"] == 200
assert c("GET", "/api/partite/inesistente")["stato"] == 404
assert c("GET", "/api/mazzi/" + "Millstone%20Dreams%20(Mr.%20Pox)")["stato"] == 200
assert c("GET", "/api/carte?q=bolt&limite=2")["dati"]
t = c("POST", "/api/tcdecks/aggiorna?tornei=3")
assert t["stato"] == 200 and "rete non disponibile" in t["dati"]["errori"][0], t
assert c("POST", "/api/mazzi/analizza", {})["stato"] == 422
assert c("GET", "/api/nulla")["stato"] == 404
print("ok")
"""


def test_api_senza_server(tmp_path):
    env = {**os.environ, "OSA_DATI": str(tmp_path)}
    r = subprocess.run([sys.executable, "-c", PROVA], cwd=RADICE, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("ok")
