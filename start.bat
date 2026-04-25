@echo off
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual. Ejecuta install.bat primero.
    exit /b 1
)

if not exist "run" (
    mkdir "run"
)
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$envFile = Join-Path '%CD%' '.env'; $port = 8000; if (Test-Path $envFile) { $line = Get-Content $envFile | Where-Object { $_ -match '^PORT=' } | Select-Object -First 1; if ($line) { $port = $line.Split('=')[1].Trim() } }; Write-Output $port"`) do set APP_PORT=%%P

if exist "run\uvicorn.pid" (
    echo El servidor parece estar iniciado. Usa stop.bat si necesitas reiniciarlo.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$python = Join-Path '%CD%' 'venv\Scripts\python.exe'; $args = '-m uvicorn app.main:app --host 0.0.0.0 --port %APP_PORT%'; $proc = Start-Process -FilePath $python -ArgumentList $args -WorkingDirectory '%CD%' -WindowStyle Hidden -PassThru; Set-Content -Path (Join-Path '%CD%' 'run\uvicorn.pid') -Value $proc.Id; Write-Output ('Servidor iniciado en segundo plano. PID=' + $proc.Id + ' PORT=%APP_PORT%')"

endlocal
