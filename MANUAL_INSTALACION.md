# Manual de Instalacion - CFDI Shield

## 1. Requisitos

Para instalar CFDI Shield en Windows se recomienda:

- Windows 10 u 11
- permisos para ejecutar archivos `.bat`
- acceso local a la carpeta del sistema
- Microsoft Excel o software compatible para abrir exportaciones `.xlsx`

## 2. Archivos principales

- `install.bat`
- `start.bat`
- `stop.bat`
- `.env.example`
- `README_LOCAL.md`

## 3. Instalacion inicial

1. Copia la carpeta del sistema en:

`C:\facturas-app`

2. Abre una consola en esa carpeta.
3. Ejecuta:

```bat
install.bat
```

La instalacion:
- crea `venv` si no existe
- actualiza `pip`
- instala dependencias desde `requirements.txt`
- crea `.env` a partir de `.env.example` si todavia no existe

## 4. Configuracion del archivo .env

Edita `.env` antes de usar el sistema en produccion.

Variables recomendadas:

```env
APP_NAME=CFDI Shield
APP_VERSION=1.0
APP_SECRET_KEY=coloca_una_clave_larga_y_privada
DATABASE_URL=sqlite:///./facturas.db
DEBUG=False
PORT=8000
BASE_URL=http://127.0.0.1:8000
LOCAL_MODE=False
ENABLE_SAT_VALIDATION=True
ENABLE_2FA=True
MAX_UPLOAD_SIZE_BYTES=5242880
MAX_FILES_PER_UPLOAD=20
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

## 5. Iniciar la aplicacion

Para iniciar CFDI Shield en segundo plano:

```bat
start.bat
```

La aplicacion quedara disponible en:

- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/`

El puerto se toma del valor `PORT` en `.env`.

## 6. Detener la aplicacion

```bat
stop.bat
```

## 7. Instalacion como servicio con NSSM

### Configuracion recomendada

- `Path`: `C:\facturas-app\venv\Scripts\python.exe`
- `Arguments`: `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `Startup directory`: `C:\facturas-app`

### Pasos

1. Descarga NSSM.
2. Abre PowerShell como administrador.
3. Ejecuta:

```powershell
nssm install CFDIShield
```

4. Configura los campos indicados arriba.
5. En `Details`, usa:
   - `Display name`: `CFDI Shield`
   - `Startup type`: `Automatic`
6. En `I/O`, define logs si lo deseas:
   - `stdout`: `C:\facturas-app\run\service-stdout.log`
   - `stderr`: `C:\facturas-app\run\service-stderr.log`
7. Guarda y arranca el servicio.

Comandos utiles:

```powershell
nssm start CFDIShield
nssm stop CFDIShield
nssm restart CFDIShield
nssm remove CFDIShield confirm
```

## 8. Solucion de errores comunes

### Error: no se encontro el entorno virtual
Ejecuta:

```bat
install.bat
```

### Error: el puerto ya esta en uso
1. Deten la instancia anterior con `stop.bat`.
2. O cambia `PORT` en `.env`.

### Error: no llegan correos
Verifica:
- `SMTP_HOST`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- acceso de salida SMTP

Para Gmail, usa contrasena de aplicacion.

### Error: no valida SAT
Verifica:
- `LOCAL_MODE=False`
- `ENABLE_SAT_VALIDATION=True`
- conectividad saliente al servicio SAT

### Error: SAT aparece siempre apagado
Revisa:

- `C:\CFDIShield\.env`

Confirma que tenga:

- `LOCAL_MODE=False`
- `ENABLE_SAT_VALIDATION=True`

Si corriges esos valores, reinicia el servicio `CFDIShield`.

### Error: no abre el Excel exportado
1. Vuelve a exportar desde el dashboard.
2. Verifica que la descarga termine correctamente.
3. Revisa espacio en disco y permisos de carpeta de descargas.

### Error: acceso denegado al ejecutar scripts
Ejecuta la consola con permisos suficientes y confirma que la carpeta no este bloqueada por politicas locales o antivirus.

## 9. Recomendaciones operativas

- Usa `LOCAL_MODE=True` si el cliente requiere operacion sin consultas externas.
- Activa `ENABLE_SAT_VALIDATION=True` solo cuando haya conectividad permitida.
- Respalda regularmente:
  - `facturas.db`
  - `.env`
  - `logs\cfdi_shield.log`

## 10. Prueba end-to-end del toggle SAT

Usa esta prueba final para confirmar que el modo SAT responde en tiempo real desde la interfaz y que el dashboard refleja correctamente el resultado.

### Paso 1. Reiniciar el servicio

Abre PowerShell como administrador y ejecuta:

```powershell
C:\nssm\win64\nssm.exe restart CFDIShield
```

### Paso 2. Confirmar servicio activo

Verifica que la app responda:

```powershell
curl http://127.0.0.1:8000/health
```

El resultado esperado es:

- respuesta `OK`

### Paso 3. Entrar al dashboard

Abre en navegador:

- `http://127.0.0.1:8000/dashboard-web`

Inicia sesion si el sistema lo solicita.

### Paso 4. Apagar SAT desde la UI

En el dashboard:

- ubica la tarjeta `Modo SAT`
- cambia el estado a `Desactivado`

Debes ver un mensaje indicando que las nuevas cargas usaran estado local sin consultar SAT.

### Paso 5. Subir XML nuevos

Desde `Cargar`:

- selecciona uno o varios XML nuevos
- completa la carga normal

### Paso 6. Validar resultado esperado con SAT apagado

Despues de la carga, en el dashboard:

- `Facturas` debe aumentar
- `Sin validacion SAT` debe aumentar
- `Vigentes` no debe aumentar por esos CFDI
- `Canceladas` no debe aumentar por esos CFDI

El comportamiento esperado es:

- no se consulta SAT
- no se usa cache SAT
- las nuevas facturas quedan con `estatus_sat = SIN_VALIDACION`

### Paso 7. Encender SAT nuevamente

En el dashboard:

- vuelve a activar `Modo SAT`

Debes ver un mensaje indicando que las nuevas cargas consultaran SAT cuando aplique.

### Paso 8. Subir o revalidar otro XML

Haz una de estas dos acciones:

- subir un XML nuevo, o
- revalidar una factura desde el flujo disponible

### Resultado esperado con SAT encendido

El sistema debe volver al flujo normal:

- puede consultar SAT
- puede usar cache SAT
- el CFDI nuevo ya no debe caer automaticamente en `Sin validacion SAT`
- si SAT responde `VIGENTE`, debe reflejarse en `Vigentes`
- si SAT responde `CANCELADO`, debe reflejarse en `Canceladas`

### Nota operativa

Si `LOCAL_MODE=True` o `ENABLE_SAT_VALIDATION=False` en `.env`, el sistema seguira mostrando SAT desactivado aunque el usuario intente activarlo desde la UI. En ese caso, primero corrige la configuracion y reinicia el servicio.

## 11. Empaquetado final como instalador Windows

CFDI Shield puede empaquetarse como instalador `.exe` sin incluir `.env` real ni `facturas.db` con datos productivos.

### Archivos de build

- `run_cfdi_shield.py`
- `build_exe.bat`
- `installer\CFDIShield.iss`
- `build_installer.bat`

### Regla de empaquetado

- no incluir `.env` real
- no incluir `facturas.db` con datos reales
- incluir solo `.env.example`
- la base de datos se crea vacia al primer arranque si no existe

### Paso 1. Generar ejecutable

Desde `C:\facturas-app`:

```bat
build_exe.bat
```

Resultado esperado:

- `dist\CFDIShield\CFDIShield.exe`

### Paso 2. Generar instalador

Con Inno Setup instalado:

```bat
build_installer.bat
```

Si Inno Setup quedo instalado en ruta de usuario, el script tambien detecta:

- `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`

Resultado esperado:

- `installer\Output\CFDIShieldSetup.exe`

### Paso 3. Instalar en otra PC

1. Copia `CFDIShieldSetup.exe` al equipo destino.
2. Ejecuta el instalador como administrador.
3. El instalador debe:
   - instalar en `C:\CFDIShield`
   - copiar `nssm.exe`
   - crear el servicio `CFDIShield`
   - iniciar el servicio automaticamente
   - crear acceso directo de escritorio a `http://127.0.0.1:8000`
   - crear `C:\CFDIShield\.env` a partir de `C:\CFDIShield\_internal\.env.example` si no existe

### Paso 4. Validar instalacion

Despues de instalar, abre:

- `http://127.0.0.1:8000/health`

El resultado esperado es:

- respuesta `OK`

### Paso 5. Desinstalar

La desinstalacion desde Windows debe:

- detener el servicio `CFDIShield`
- eliminar el servicio `CFDIShield`
- quitar la carpeta instalada segun el flujo normal de desinstalacion

## 12. Validacion post-instalacion (cliente final)

### Paso 1. Abrir navegador

Abre:

- `http://127.0.0.1:8000`

### Paso 2. Validar acceso

Confirma que:

- `Login` funciona
- `Registro` funciona

### Paso 3. Validar carga

Prueba:

- subir `1 XML`
- subir multiples XML

Confirma que:

- la carga termina sin errores visibles
- los mensajes de resultado aparecen correctamente

### Paso 4. Validar dashboard

Confirma que:

- los KPIs cargan
- los conteos son correctos
- las tablas muestran informacion

### Paso 5. Validar toggle SAT

1. Apaga SAT desde la interfaz.
2. Sube un XML nuevo.
3. Confirma que aparece en `Sin validacion SAT`.
4. Enciende SAT nuevamente.
5. Sube otro XML nuevo.
6. Confirma que aparece con estatus `VIGENTE` o `CANCELADO` segun respuesta SAT.

### Paso 6. Validar exportacion

1. Descarga el archivo Excel desde el dashboard.
2. Abre el archivo.
3. Confirma que los datos coinciden con lo mostrado en pantalla.

### Paso 7. Validar servicio

1. Cierra el navegador.
2. Vuelve a abrirlo.
3. Entra otra vez a:

- `http://127.0.0.1:8000`

Confirma que el sistema sigue funcionando sin tener que reinstalar ni iniciar manualmente la app.
