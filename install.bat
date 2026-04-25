@echo off
setlocal

cd /d "%~dp0"

if not exist "venv" (
    if exist ".venv" (
        move ".venv" "venv" >nul
    ) else (
        py -3 -m venv venv
    )
)

call "venv\Scripts\activate.bat"
"venv\Scripts\python.exe" -m pip install --upgrade pip
"venv\Scripts\python.exe" -m pip install -r requirements.txt

if not exist ".env" (
    copy ".env.example" ".env" >nul
)

if not exist "run" (
    mkdir "run"
)

echo Instalacion completada.
echo Edita el archivo .env antes de usar el sistema en produccion.
endlocal
