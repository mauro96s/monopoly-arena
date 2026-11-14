# ============================================================
# Script de arranque local para Windows PowerShell
# Asegura el uso estricto del entorno virtual (venv)
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvActivate = Join-Path $scriptDir "venv\Scripts\Activate.ps1"
$venvPython = Join-Path $scriptDir "venv\Scripts\python.exe"

if (-not (Test-Path $venvActivate)) {
    Write-Host "[1/3] Creando entorno virtual 'venv'..." -ForegroundColor Cyan
    python -m venv venv
    
    Write-Host "[2/3] Instalando dependencias en venv..." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r (Join-Path $scriptDir "requirements.txt")
} else {
    Write-Host "[1/2] Entorno virtual 'venv' detectado." -ForegroundColor Green
}

Write-Host "[OK] Iniciando Monopoly Arena con Uvicorn..." -ForegroundColor Green
Write-Host "Lobby Web disponible en: http://127.0.0.1:8000" -ForegroundColor Yellow
Write-Host "Swagger Docs en:        http://127.0.0.1:8000/docs" -ForegroundColor Yellow

# Ejecuta Uvicorn garantizando el interprete del venv
& $venvPython -m uvicorn src.presentation.main:app --reload --host 127.0.0.1 --port 8000
