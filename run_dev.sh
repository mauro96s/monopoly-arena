#!/usr/bin/env bash
# ============================================================
# Script de arranque local para Linux / macOS (bash / zsh)
# Asegura el uso estricto del entorno virtual (venv)
# ============================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ ! -f "venv/bin/activate" ]; then
    echo "[1/3] Creando entorno virtual 'venv'..."
    python3 -m venv venv
    echo "[2/3] Instalando dependencias en venv..."
    source venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    echo "[1/2] Activando entorno virtual 'venv'..."
    source venv/bin/activate
fi

echo "[OK] Iniciando Monopoly Arena con Uvicorn..."
echo "Lobby Web disponible en: http://127.0.0.1:8000"
echo "Swagger Docs en:        http://127.0.0.1:8000/docs"

python -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
