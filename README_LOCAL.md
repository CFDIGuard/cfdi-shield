# FiscalGuard - Modo Local / On-Premise

## Archivos activos

- `C:\facturas-app\app\main.py`
- `C:\facturas-app\app\web\routes_auth.py`
- `C:\facturas-app\app\web\routes_pages.py`
- `C:\facturas-app\app\api\router.py`
- `C:\facturas-app\app\api\routes\invoices.py`
- `C:\facturas-app\app\api\routes\dashboard.py`
- `C:\facturas-app\app\services\xml_parser.py`
- `C:\facturas-app\app\services\sat_validator.py`
- `C:\facturas-app\app\services\risk_engine.py`
- `C:\facturas-app\app\services\supplier_score.py`
- `C:\facturas-app\app\services\duplicate_detector.py`
- `C:\facturas-app\app\services\reports_service.py`
- `C:\facturas-app\templates\index.html`
- `C:\facturas-app\templates\dashboard.html`
- `C:\facturas-app\templates\login.html`
- `C:\facturas-app\templates\register.html`
- `C:\facturas-app\templates\forgot_password.html`
- `C:\facturas-app\templates\reset_password.html`
- `C:\facturas-app\templates\verify_2fa.html`

## Instalacion

1. Abre una consola en `C:\facturas-app`.
2. Ejecuta:

```bat
install.bat
```

3. Revisa el archivo `.env`.

La instalacion hace esto automaticamente:

- crea `C:\facturas-app\venv` si no existe
- actualiza `pip`
- instala `requirements.txt`
- crea `.env` desde `.env.example` si todavia no existe

## Inicio

Para iniciar la app en segundo plano:

```bat
start.bat
```

La aplicacion quedara disponible en:

- `http://127.0.0.1:8000/login`
- `http://127.0.0.1:8000/`

El puerto se toma de `PORT` en `.env`.

## Detener la app

```bat
stop.bat
```

## Inicio manual

Si prefieres arrancar en primer plano:

```bat
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Variables de entorno

Consulta `C:\facturas-app\.env.example`.

Recomendado para local/offline:

```env
DEBUG=False
LOCAL_MODE=False
ENABLE_SAT_VALIDATION=True
ENABLE_2FA=True
APP_SECRET_KEY=tu_clave_larga_y_privada
MASTER_ENCRYPTION_KEY=tu_clave_maestra_larga
```

Recomendado para modo con SAT:

```env
DEBUG=False
LOCAL_MODE=False
ENABLE_SAT_VALIDATION=True
```

## Seguridad

- Cookies HTTP-only.
- Password hashing con PBKDF2.
- 2FA opcional por variable `ENABLE_2FA`.
- Recuperacion de contrasena con token temporal.
- Sin telemetria ni logs remotos.
- Los XML se validan por extension y contenido antes de procesar.
- El sistema no almacena XML crudos en base de datos, por lo que no se exponen archivos fiscales completos.

## Respaldos

### Respaldo rapido

Deten la app y copia estos archivos:

- `C:\facturas-app\facturas.db`
- `C:\facturas-app\logs\cfdi_shield.log`
- `C:\facturas-app\.env`

### Restauracion

1. Deten la app con `stop.bat`.
2. Sustituye `facturas.db` por el respaldo.
3. Inicia la app con `start.bat`.

## NSSM como servicio de Windows

1. Descarga NSSM y extrae `nssm.exe`.
2. Abre PowerShell como administrador.
3. Instala el servicio:

```powershell
nssm install FacturasCFDI
```

4. Configura:

- `Application`: `C:\facturas-app\venv\Scripts\python.exe`
- `Startup directory`: `C:\facturas-app`
- `Arguments`: `-m uvicorn app.main:app --host 0.0.0.0 --port 8000`

5. En la pestaña `Details` usa:

- `Display name`: `FiscalGuard`
- `Startup type`: `Automatic`

6. En la pestaña `I/O` usa:

- `Output (stdout)`: `C:\facturas-app\run\service-stdout.log`
- `Error (stderr)`: `C:\facturas-app\run\service-stderr.log`

7. En la pestaña `Exit actions` configura reinicio automatico.

Comandos utiles:

```powershell
nssm start FiscalGuard
nssm stop FiscalGuard
nssm restart FiscalGuard
nssm remove FiscalGuard confirm
```

## Salud basica

- `GET /ping`
- `GET /health`
- `GET /ready`

## Modo API

La API sigue activa en:

- `POST /api/v1/invoices/upload`
- `GET /api/v1/invoices`
- `GET /api/v1/invoices/{invoice_id}`
- `GET /api/v1/invoices/by-uuid/{uuid}`
- `POST /api/v1/invoices/{invoice_id}/refresh-sat-status`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/dashboard/export-excel`

## Exportacion Excel

La exportacion V3 queda disponible en:

- `GET /api/v1/dashboard/export-excel`

Desde la interfaz web tambien existe el boton `Exportar Excel` en el dashboard.
