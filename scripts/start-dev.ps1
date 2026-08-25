# Start the full local stack (API + Vite dev server).
# Usage: .\scripts\start-dev.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting API on http://127.0.0.1:8000 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root'; .\.venv\Scripts\uvicorn.exe api.main:app --reload --host 127.0.0.1 --port 8000"
)

Write-Host "Starting web dev server on http://127.0.0.1:5173 ..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Root\web'; npm run dev"
)

Write-Host ""
Write-Host "Dashboard URLs:"
Write-Host "  Integrated (API + built UI): http://127.0.0.1:8000"
Write-Host "  Dev (hot reload):            http://127.0.0.1:5173"
Write-Host ""
Write-Host "If port 5173 fails, use http://127.0.0.1:8000 after running: cd web; npm run build"
