@echo off
setlocal

cd /d "%~dp0"

if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"
if exist "installer\Output" rd /s /q "installer\Output"

call "%~dp0build_exe.bat"
if errorlevel 1 exit /b 1

set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
  echo [ERROR] No se encontro Inno Setup Compiler.
  echo Instala Inno Setup 6 y vuelve a ejecutar este script.
  exit /b 1
)

"%ISCC%" "%~dp0installer\CFDIShield.iss"
if errorlevel 1 (
  echo [ERROR] Fallo la compilacion del instalador.
  exit /b 1
)

echo [OK] Instalador generado en installer\Output\CFDIShieldSetup.exe
exit /b 0
