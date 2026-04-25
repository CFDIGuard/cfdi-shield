# Manual Web Deploy - CFDI Shield

## 1. Objetivo

Desplegar una version web demo de CFDI Shield en Render para compartirla con conocidos sin exponer datos reales del entorno local.

## 2. Antes de subir el repositorio

- usa un repositorio privado en GitHub
- no subas `.env` real
- no subas `facturas.db`
- no subas XML reales
- no subas logs

Archivos sugeridos para el repo:

- codigo fuente
- `requirements.txt`
- `Dockerfile`
- `.env.web.example`

## 3. Crear repositorio privado en GitHub

1. crea un repositorio privado
2. sube el proyecto limpio
3. confirma que no existan:
   - `.env`
   - `facturas.db`
   - `logs/`
   - XML reales

## 4. Crear Blueprint en Render usando render.yaml

1. entra a Render
2. elige `New +`
3. selecciona `Blueprint`
4. conecta el repositorio privado:
   - `https://github.com/CFDIGuard/cfdi-shield`
5. confirma que Render detecte:
   - `render.yaml`
   - servicio web `cfdi-shield-demo`
   - base PostgreSQL `cfdi-shield-db`

## 5. Configurar BETA_ACCESS_CODE

Antes del deploy, define una clave beta privada en:

- `BETA_ACCESS_CODE`
- opcionalmente `BETA_ALLOWED_EMAILS`

Esa clave se usara para controlar el registro de usuarios de prueba.

## 6. Deploy

1. ejecuta el deploy desde el Blueprint
2. espera a que Render termine de construir la imagen y publicar el servicio

## 7. Abrir URL publica

1. abre la URL publica generada por Render
2. entra a `/login`
3. valida que la app cargue correctamente
4. actualiza `BASE_URL` en Render con esa misma URL publica y vuelve a desplegar si usaras recuperacion de contrasena

## 8. Probar registro con codigo beta

1. abre `/register`
2. crea una cuenta de prueba
3. introduce el `BETA_ACCESS_CODE`
4. confirma que el registro solo funcione con codigo valido o correo autorizado

## 9. Crear base PostgreSQL en Render

Si no usas el Blueprint completo, puedes crear manualmente la base:

1. entra a Render
2. crea un servicio PostgreSQL
3. copia la cadena de conexion

Usa esa cadena en la variable:

- `DATABASE_URL`

## 10. Crear Web Service en Render manualmente

1. crea un nuevo `Web Service`
2. conecta el repositorio privado
3. elige Docker como metodo de despliegue o usa el `Start Command`

Start command recomendado:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## 11. Variables de entorno recomendadas

Configura al menos:

```env
APP_NAME=CFDI Shield
APP_VERSION=1.0
DEBUG=False
BASE_URL=https://tu-servicio.onrender.com
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB
LOCAL_MODE=False
ENABLE_SAT_VALIDATION=True
ENABLE_REGISTRATION=True
ENABLE_BETA_MODE=True
ENABLE_2FA=False
BETA_ACCESS_CODE=tu-codigo-beta
BETA_ALLOWED_EMAILS=correo1@dominio.com,correo2@dominio.com
APP_SECRET_KEY=una-clave-larga-y-privada
```

Opcionales:

```env
ENABLE_2FA=False
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=True
SMTP_USE_SSL=False
```

Para demo publica sin correo:

```env
ENABLE_2FA=False
```

Si quieres 2FA real por correo, configura:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

## 12. Como funciona el modo beta

Si:

- `ENABLE_REGISTRATION=True`
- `ENABLE_BETA_MODE=True`

entonces el registro solo se permite si:

- el usuario conoce `BETA_ACCESS_CODE`, o
- el correo esta en `BETA_ALLOWED_EMAILS`

Si quieres cerrar totalmente el registro:

```env
ENABLE_REGISTRATION=False
```

## 13. Verificaciones despues del deploy

1. abre la URL publica de Render
2. entra a `/login`
3. prueba `/register` segun tu configuracion beta
4. valida carga de XML de prueba
5. valida dashboard
6. valida exportacion Excel

## 14. Notas operativas

- para demo publica, usa una base PostgreSQL separada de produccion
- no reutilices secretos del entorno local
- no subas `.env` real
- no subas `facturas.db`
- no subas XML reales
- no subas logs
- si 2FA aparece apagado o no permite activarse, revisa que:
  - `ENABLE_2FA=True`
  - SMTP este configurado completamente
- si SAT real no debe consultarse durante demo, ajusta:

```env
ENABLE_SAT_VALIDATION=False
```

- si quieres demo privada y controlada, deja:
  - `ENABLE_BETA_MODE=True`
  - `ENABLE_REGISTRATION=True`
  - `BETA_ACCESS_CODE` configurado
