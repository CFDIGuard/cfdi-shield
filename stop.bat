@echo off
setlocal

cd /d "%~dp0"

if not exist "run\uvicorn.pid" (
    echo No hay PID registrado. Si el proceso sigue activo, detenlo manualmente.
    exit /b 1
)

set /p UVICORN_PID=<"run\uvicorn.pid"
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Process -Id %UVICORN_PID% -ErrorAction SilentlyContinue) { Stop-Process -Id %UVICORN_PID% -Force; Write-Output 'Servidor detenido.' } else { Write-Output 'El proceso ya no estaba activo.' }"
del /q "run\uvicorn.pid"

endlocal
