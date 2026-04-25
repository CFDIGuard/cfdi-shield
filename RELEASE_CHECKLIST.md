# Release Checklist - FiscalGuard

## Objetivo

Usar esta lista para validar la salida de `FiscalGuard v1.0 RC` antes de entrega o instalacion en cliente.

## 1. Prueba final en cliente

- [ ] `install.bat` ejecutado correctamente
- [ ] `.env` configurado con datos del cliente
- [ ] `start.bat` inicia la app sin errores
- [ ] acceso correcto a `http://127.0.0.1:8000/login`
- [ ] acceso correcto a `http://127.0.0.1:8000/` despues de login
- [ ] `stop.bat` detiene la app correctamente

## 2. SAT real

- [ ] `LOCAL_MODE=False`
- [ ] `ENABLE_SAT_VALIDATION=True`
- [ ] salida de red permitida al SAT
- [ ] se valida una factura real con respuesta SAT
- [ ] el cache SAT evita consultas repetidas innecesarias
- [ ] el refresh manual actualiza el estatus cuando se solicita

## 3. Carga multiple

- [ ] carga de 1 XML valida
- [ ] carga de varios XML valida
- [ ] rechazo correcto de archivo no XML
- [ ] rechazo correcto de mas de 20 archivos
- [ ] deteccion correcta de duplicados por UUID
- [ ] no se consulta SAT para duplicados

## 4. Dashboard

- [ ] KPIs visibles
- [ ] tabla de ultimas facturas visible
- [ ] tabla de proveedores visible
- [ ] seccion de riesgos visible
- [ ] boton eliminar visible y funcional

## 5. Exportacion Excel

- [ ] boton `Exportar Excel` visible en dashboard
- [ ] `GET /api/v1/dashboard/export-excel` responde correctamente
- [ ] el archivo `.xlsx` abre en Excel
- [ ] hojas presentes:
  - [ ] `RESUMEN`
  - [ ] `CONTROL`
  - [ ] `PROVEEDORES`
  - [ ] `RIESGOS`
- [ ] los datos coinciden con el dashboard

## 6. Recuperacion de contrasena

- [ ] enlace `Olvidaste tu contrasena` visible
- [ ] `/forgot-password` carga sin error
- [ ] se genera enlace de recuperacion
- [ ] `/reset-password?token=...` abre correctamente
- [ ] la contrasena puede actualizarse
- [ ] el login con nueva contrasena funciona

## 7. 2FA

- [ ] se puede activar desde dashboard
- [ ] se envia codigo al correo configurado
- [ ] `/verify-2fa` carga correctamente
- [ ] el codigo correcto permite acceso
- [ ] codigo incorrecto o expirado muestra error controlado

## 8. NSSM / start.bat

- [ ] `start.bat` usa `C:\facturas-app\venv\Scripts\python.exe`
- [ ] NSSM configurado con:
  - [ ] `Path: C:\facturas-app\venv\Scripts\python.exe`
  - [ ] `Arguments: -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - [ ] `Startup directory: C:\facturas-app`
- [ ] servicio inicia automaticamente si aplica
- [ ] servicio se puede detener y reiniciar

## 9. Backup / restauracion

- [ ] respaldo de `facturas.db`
- [ ] respaldo de `.env`
- [ ] respaldo de logs si el cliente los requiere
- [ ] restauracion probada sobre una copia
- [ ] la app vuelve a iniciar despues de restaurar

## 10. Cierre previo a entrega

- [ ] `.env.example` sin secretos reales
- [ ] `.gitignore` actualizado
- [ ] documentacion comercial y operativa presente
- [ ] `python -m compileall app` completado
- [ ] release notes listos para compartir
