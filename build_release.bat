@echo off
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "VERSION=%APP_VERSION%"
if not defined VERSION set "VERSION=1.0"
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$value = '%VERSION%'; if ($value -match '^[0-9A-Za-z._-]+$') { $value } else { '1.0' }"`) do set "VERSION=%%V"
set "BUILD_DATE=%BUILD_DATE%"
if not defined BUILD_DATE (
  for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"`) do set "BUILD_DATE=%%D"
)
if not defined BUILD_DATE set "BUILD_DATE=2026-04-25"

set "RELEASE_BASE=%ROOT%\release\CFDI_Shield_v%VERSION%"
set "APP_DIR=%RELEASE_BASE%\app"
set "DOCS_DIR=%RELEASE_BASE%\docs"
set "OPS_DIR=%RELEASE_BASE%\operacion"
set "INSTALLER=%ROOT%\installer\Output\CFDIShieldSetup.exe"
set "RELEASE_INSTALLER=%APP_DIR%\CFDIShieldSetup.exe"
set "ZIP_PATH=%ROOT%\release\CFDI_Shield_v%VERSION%.zip"
set "SHA_FILE=%ROOT%\release\SHA256.txt"

echo [INFO] Preparando carpeta release...
if exist "%RELEASE_BASE%" rmdir /s /q "%RELEASE_BASE%"

mkdir "%APP_DIR%"
mkdir "%DOCS_DIR%"
mkdir "%OPS_DIR%"

echo [INFO] Copiando documentacion cliente...
copy /y "%ROOT%\docs_cliente\MANUAL_USUARIO.md" "%DOCS_DIR%\MANUAL_USUARIO.md" >nul
copy /y "%ROOT%\docs_cliente\AVISO_PRIVACIDAD.md" "%DOCS_DIR%\AVISO_PRIVACIDAD.md" >nul
copy /y "%ROOT%\docs_cliente\TERMINOS_USO.md" "%DOCS_DIR%\TERMINOS_USO.md" >nul
copy /y "%ROOT%\docs_cliente\PRECIOS.md" "%DOCS_DIR%\PRECIOS.md" >nul

echo [INFO] Copiando documentacion operativa...
copy /y "%ROOT%\docs_operacion\MANUAL_INSTALACION.md" "%OPS_DIR%\MANUAL_INSTALACION.md" >nul
copy /y "%ROOT%\docs_cliente\CHECKLIST_ENTREGA_CFDI_SHIELD.md" "%OPS_DIR%\CHECKLIST_ENTREGA_CFDI_SHIELD.md" >nul

echo [INFO] Escribiendo README del paquete...
(
  echo CFDI Shield
  echo Analisis inteligente de CFDI y riesgo fiscal por proveedor
  echo.
  echo Version: %VERSION%
  echo Fecha: %BUILD_DATE%
  echo.
  echo Descripcion:
  echo CFDI Shield es una solucion local para control, revision y analisis de CFDI con enfoque operativo y de riesgo.
  echo.
  echo Firma visual de seguridad:
  echo Este software no envia informacion a servidores externos sin configuracion explicita.
  echo Los CFDI se procesan localmente o bajo control del usuario.
  echo.
  echo Instrucciones rapidas:
  echo 1. Ejecuta el instalador CFDIShieldSetup.exe ubicado en la carpeta app.
  echo 2. Abre la aplicacion en http://127.0.0.1:8000 cuando termine la instalacion.
  echo 3. Inicia sesion y carga tus CFDI para comenzar a trabajar.
  echo.
  echo Soporte:
  echo soporte@cfdi-shield.local
) > "%RELEASE_BASE%\README.txt"

if exist "%INSTALLER%" (
  echo [INFO] Copiando instalador...
  copy /y "%INSTALLER%" "%RELEASE_INSTALLER%" >nul
) else (
  echo [WARN] No se encontro el instalador en: %INSTALLER%
)

echo [INFO] Generando ZIP del release...
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"
powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE_BASE%\*' -DestinationPath '%ZIP_PATH%' -Force" >nul
if errorlevel 1 (
  echo [WARN] No se pudo generar el ZIP automatico.
) else (
  echo [OK] ZIP generado en:
  echo %ZIP_PATH%
)

echo [INFO] Generando SHA256...
(
  echo CFDI Shield v%VERSION%
  echo Fecha: %BUILD_DATE%
  echo.
) > "%SHA_FILE%"

if exist "%RELEASE_INSTALLER%" (
  >> "%SHA_FILE%" echo CFDIShieldSetup.exe
  set "INSTALLER_HASH="
  for /f "delims=" %%H in ('powershell -NoProfile -Command "$text = certutil -hashfile '%RELEASE_INSTALLER%' SHA256 | Out-String; [regex]::Match($text, '(?im)\b[a-f0-9]{64}\b').Value"') do if not defined INSTALLER_HASH set "INSTALLER_HASH=%%H"
  if defined INSTALLER_HASH (
    >> "%SHA_FILE%" echo SHA256: !INSTALLER_HASH!
  ) else (
    >> "%SHA_FILE%" echo SHA256: NO_DISPONIBLE
  )
  >> "%SHA_FILE%" echo.
) else (
  >> "%SHA_FILE%" echo CFDIShieldSetup.exe
  >> "%SHA_FILE%" echo SHA256: NO_DISPONIBLE
  >> "%SHA_FILE%" echo.
)

if exist "%ZIP_PATH%" (
  >> "%SHA_FILE%" echo CFDI_Shield_v%VERSION%.zip
  set "ZIP_HASH="
  for /f "delims=" %%H in ('powershell -NoProfile -Command "$text = certutil -hashfile '%ZIP_PATH%' SHA256 | Out-String; [regex]::Match($text, '(?im)\b[a-f0-9]{64}\b').Value"') do if not defined ZIP_HASH set "ZIP_HASH=%%H"
  if defined ZIP_HASH (
    >> "%SHA_FILE%" echo SHA256: !ZIP_HASH!
  ) else (
    >> "%SHA_FILE%" echo SHA256: NO_DISPONIBLE
  )
  >> "%SHA_FILE%" echo.
) else (
  >> "%SHA_FILE%" echo CFDI_Shield_v%VERSION%.zip
  >> "%SHA_FILE%" echo SHA256: NO_DISPONIBLE
  >> "%SHA_FILE%" echo.
)

echo [OK] SHA256 generado en:
echo %SHA_FILE%

echo [OK] Release listo en:
echo %RELEASE_BASE%
endlocal
