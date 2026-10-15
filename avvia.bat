@echo off
REM Avvia Old School Arena su Windows: crea l'ambiente la prima volta, poi apre il browser.
cd /d "%~dp0"
if not exist .venv (
    echo Creo l'ambiente Python...
    python -m venv .venv || goto errore
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt || goto errore
) else (
    call .venv\Scripts\activate.bat
)
start "" http://127.0.0.1:8000
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
goto :eof
:errore
echo Qualcosa e' andato storto. Serve Python 3.11 o superiore installato e nel PATH.
pause
