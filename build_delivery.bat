@echo off
setlocal

cd /d "%~dp0"

call "%~dp0build_installer.bat"
if errorlevel 1 exit /b 1

call "%~dp0build_release.bat"
if errorlevel 1 exit /b 1

echo [OK] Flujo completo terminado.
echo [OK] Instalador: installer\Output\CFDIShieldSetup.exe
echo [OK] Release: release\CFDI_Shield_v1.0.zip
exit /b 0
