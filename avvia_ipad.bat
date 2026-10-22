@echo off
REM Avvia Old School Arena aperta alla rete di casa (per giocare dall'iPad), con password.
cd /d "%~dp0"
if not exist .venv (
    echo Creo l'ambiente Python...
    python -m venv .venv || goto errore
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt || goto errore
) else (
    call .venv\Scripts\activate.bat
)
python -m app.avvio --rete
pause
goto :eof
:errore
echo Qualcosa e' andato storto. Serve Python 3.11 o superiore installato e nel PATH.
pause
