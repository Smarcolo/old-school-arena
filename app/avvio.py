"""Avvio del server. `python -m app.avvio` = solo su questo PC (avvia.bat); `python -m app.avvio --rete` = anche
dagli altri dispositivi della rete di casa, per esempio l'iPad (avvia_ipad.bat), con una password.

La password si crea la prima volta in data/password.txt: si può cambiare scrivendone un'altra nel file."""
import os
import secrets
import socket
import sys
import webbrowser

from app.config import DATI

PORTA = 8000
FILE_PASSWORD = DATI / "password.txt"


def password() -> str:
    if FILE_PASSWORD.exists() and (scritta := FILE_PASSWORD.read_text(encoding="utf-8").strip()):
        return scritta
    nuova = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
    FILE_PASSWORD.parent.mkdir(parents=True, exist_ok=True)
    FILE_PASSWORD.write_text(nuova + "\n", encoding="utf-8")
    return nuova


def ip_di_casa() -> str:
    """L'indirizzo di questo PC nella rete di casa (non manda niente: serve solo a sapere quale scheda di rete esce)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.168.1.1", 80))
            return s.getsockname()[0]
        except OSError:
            return socket.gethostbyname(socket.gethostname())


def main() -> None:
    import uvicorn
    rete = "--rete" in sys.argv
    if rete:
        os.environ["OSA_PASSWORD"] = password()
        print("=" * 64)
        print("  OLD SCHOOL ARENA - aperta alla rete di casa")
        print(f"  Sull'iPad (stesso Wi-Fi) apri in Safari:  http://{ip_di_casa()}:{PORTA}")
        print(f"  Password: {os.environ['OSA_PASSWORD']}   (nome utente: quello che vuoi)")
        print(f"  La password si cambia nel file {FILE_PASSWORD}")
        print("  Se Windows chiede il permesso per Python sulle reti private: Consenti.")
        print("  Per fermare il gioco chiudi questa finestra.")
        print("=" * 64)
    if "--senza-browser" not in sys.argv:
        webbrowser.open(f"http://127.0.0.1:{PORTA}")
    uvicorn.run("app.api.main:app", host="0.0.0.0" if rete else "127.0.0.1", port=PORTA)


if __name__ == "__main__":
    main()
