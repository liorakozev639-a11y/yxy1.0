param(
    [string]$DatabasePassword = "yxy050621",
    [int]$DatabasePort = 5433,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$postgresBin = "D:\pgsql18\pgsql\bin"
$postgresData = "D:\pgsql18\data"

Set-Location $repo

& "$postgresBin\pg_isready.exe" -h 127.0.0.1 -p $DatabasePort -d free_time_agent | Out-Null
if ($LASTEXITCODE -ne 0) {
    & "$postgresBin\pg_ctl.exe" start `
        -D $postgresData `
        -l "$env:TEMP\free_time_agent-postgres.log" `
        -o "-p $DatabasePort" `
        -w
}

$env:SESSION_DATABASE_URL = "postgresql://postgres:$DatabasePassword@127.0.0.1:$DatabasePort/free_time_agent"

Write-Host "Starting backend: http://127.0.0.1:$BackendPort"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$repo'; `$env:SESSION_DATABASE_URL='$env:SESSION_DATABASE_URL'; .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port $BackendPort"
) -WindowStyle Hidden

Write-Host "Starting frontend: http://127.0.0.1:$FrontendPort"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$repo'; .\.venv\Scripts\python.exe -m http.server $FrontendPort --bind 127.0.0.1 --directory frontend"
) -WindowStyle Hidden

Write-Host "Open http://127.0.0.1:$FrontendPort"
