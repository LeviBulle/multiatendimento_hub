@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:8000/agent"

if not exist "%PYTHON_EXE%" (
    echo Ambiente virtual nao encontrado em .venv.
    echo.
    echo Rode estes comandos uma vez:
    echo python -m venv .venv
    echo .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
    )
)

echo Abrindo Ellub Chat...
echo Acesse: %APP_URL%
echo.
echo Uma janela do servidor sera aberta. Para encerrar o programa, feche essa janela ou pressione Ctrl+C nela.
echo.

start "Ellub Chat - Servidor" cmd /k ""%PYTHON_EXE%" -m alembic upgrade head && "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
timeout /t 4 /nobreak >nul
start "" "%APP_URL%"
