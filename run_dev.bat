@echo off
REM ============================================================
REM Script de arranque local para Windows (Command Prompt / CMD)
REM Asegura el uso estricto del entorno virtual (venv)
REM ============================================================

cd /d "%~dp0"

IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [1/3] Creando entorno virtual 'venv'...
    python -m venv venv
    IF ERRORLEVEL 1 (
        echo Error: No se pudo crear el entorno virtual. Asegurate de tener Python instalado.
        pause
        exit /b 1
    )
    echo [2/3] Instalando dependencias en venv...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) ELSE (
    echo [1/2] Activando entorno virtual 'venv'...
    call venv\Scripts\activate.bat
)

echo [OK] Iniciando Monopoly Arena con Uvicorn...
python -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
pause
