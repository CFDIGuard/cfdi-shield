# Checkpoint Estable

## Estado actual

La aplicacion conserva la logica fiscal validada y el flujo web principal ya quedo endurecido.

- FastAPI activo como backend
- autenticacion web con login, logout y registro
- recuperacion de contrasena con token temporal
- 2FA opcional por usuario
- carga de XML CFDI
- deteccion de duplicados por UUID
- eliminacion de facturas desde dashboard
- modo local sin dependencia obligatoria del SAT
- documentacion y rutas de debug ocultables por `DEBUG`

## Rutas activas

### Web

- `GET /login`
- `POST /login`
- `GET /register`
- `POST /register`
- `POST /logout`
- `GET /`
- `POST /upload`
- `GET /dashboard-web`
- `POST /invoices/{invoice_id}/delete`
- `GET /forgot-password`
- `POST /forgot-password`
- `GET /reset-password`
- `POST /reset-password`
- `GET /verify-2fa`
- `POST /verify-2fa`
- `POST /two-factor/toggle`

### API

- `POST /api/v1/invoices/upload`
- `GET /api/v1/invoices`
- `GET /api/v1/invoices/by-uuid/{uuid}`
- `GET /api/v1/invoices/{invoice_id}`
- `POST /api/v1/invoices/{invoice_id}/refresh-sat-status`
- `GET /api/v1/dashboard/summary`

### Salud

- `GET /ping`
- `GET /health`
- `GET /ready`

### Solo en debug

- `GET /docs`
- `GET /redoc`
- `GET /openapi.json`
- `GET /debug/routes`

## Variables .env necesarias

Minimas para entorno funcional:

```env
APP_NAME=Facturas API
DEBUG=False
PORT=8000
APP_SECRET_KEY=tu_clave_larga_y_privada
DATABASE_URL=sqlite:///./facturas.db
LOCAL_MODE=True
ENABLE_SAT_VALIDATION=False
ENABLE_2FA=True
MAX_UPLOAD_SIZE_BYTES=5242880
```

Para correo real:

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=usuario@example.com
SMTP_PASSWORD=tu_password
SMTP_FROM_EMAIL=no-reply@example.com
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

## Como correr en modo debug

```powershell
$env:DEBUG='true'
$env:LOCAL_MODE='true'
$env:ENABLE_SAT_VALIDATION='false'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Notas:

- en debug se habilitan `/docs`, `/redoc`, `/openapi.json` y `/debug/routes`
- si no hay SMTP configurado, el token de recuperacion y el codigo 2FA se dejan en logs como fallback de desarrollo

## Como correr en modo produccion

```powershell
$env:DEBUG='false'
$env:LOCAL_MODE='true'
$env:ENABLE_SAT_VALIDATION='false'
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Notas:

- en produccion quedan ocultos `/docs`, `/redoc`, `/openapi.json` y `/debug/routes`
- si no hay SMTP configurado, no se muestran tokens ni codigos en logs
- si 2FA esta activa y no hay correo disponible, el login con 2FA se bloquea con mensaje claro

## Que ya esta validado

Validado funcionalmente en entorno aislado:

- registro
- login
- forgot-password
- reset-password
- activacion de 2FA
- verify-2fa
- carga XML
- duplicado UUID
- eliminacion de factura
- dashboard actualizado despues de alta y despues de eliminacion

Validado de configuracion:

- `DEBUG=False` oculta docs y rutas debug
- `LOCAL_MODE=True` evita dependencia operativa del SAT
- `ENABLE_SAT_VALIDATION=False` evita consultas SAT
- `compileall app` ejecuta correctamente

## Carpetas ignorables

Estas carpetas son artefactos de validacion local y no forman parte del producto:

- `run-flow-debug`
- `run-flow-prod`
- `run-flow-test`

Quedaron agregadas a `.gitignore`.
