@echo off
setlocal

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] No se encontro el entorno virtual en C:\facturas-app\venv
  exit /b 1
)

if not exist ".env.example" (
  echo [ERROR] Falta .env.example en la raiz del proyecto.
  exit /b 1
)

if not exist "templates" (
  echo [ERROR] Falta la carpeta templates.
  exit /b 1
)

if not exist "static" (
  mkdir "static"
)

venv\Scripts\python.exe -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PyInstaller no esta instalado en el entorno virtual.
  echo Ejecuta: venv\Scripts\python.exe -m pip install pyinstaller
  exit /b 1
)

venv\Scripts\python.exe -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --name CFDIShield ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data ".env.example;." ^
  --collect-all pydantic ^
  --collect-all pydantic_core ^
  --collect-all sqlalchemy ^
  --collect-all greenlet ^
  --hidden-import uvicorn ^
  --hidden-import app.main ^
  run_cfdi_shield.py

if errorlevel 1 (
  echo [ERROR] Fallo la generacion del ejecutable.
  exit /b 1
)

echo [OK] Ejecutable generado en dist\CFDIShield\CFDIShield.exe
exit /b 0
