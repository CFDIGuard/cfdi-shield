# Manual de Usuario - FiscalGuard

## 1. Acceso al sistema

### Iniciar sesion
1. Abre FiscalGuard en tu navegador.
2. Ingresa tu usuario y contrasena.
3. Haz clic en `Entrar`.

Si la verificacion en dos pasos esta activa:
1. Revisa tu correo.
2. Ingresa el codigo de 6 digitos en la pantalla de verificacion.
3. Continua al dashboard.

### Cerrar sesion
1. Ubica el boton `Salir` en la parte superior.
2. Haz clic para cerrar la sesion actual.

## 2. Carga de XML CFDI

### Carga individual
1. Entra a la pantalla `Cargar`.
2. Selecciona un archivo XML.
3. Haz clic en `Procesar carga`.

### Carga multiple
FiscalGuard permite cargar hasta 20 XML por envio.

1. En la pantalla `Cargar`, selecciona varios archivos XML.
2. Verifica que la lista muestre los archivos elegidos.
3. Haz clic en `Procesar carga`.

### Resultado de la carga
Al finalizar, el sistema redirige al dashboard con un resumen como:

`Carga completada: X nuevas, Y duplicadas, Z invalidas, W errores.`

Interpretacion:
- `nuevas`: facturas agregadas correctamente.
- `duplicadas`: XML con UUID ya existente.
- `invalidas`: archivos no XML o CFDI con errores de estructura o validacion.
- `errores`: incidencias no esperadas durante el procesamiento.

## 3. Dashboard

El dashboard muestra la operacion actual del sistema:

- Total facturado
- Numero de facturas
- Vigentes
- Canceladas
- Proveedores unicos
- Riesgos altos

Tambien incluye:
- tabla de ultimas facturas
- tabla de proveedores principales
- seccion de riesgos destacados
- resumen por periodo

## 4. Exportar Excel

FiscalGuard puede exportar reportes V3 a Excel.

1. Entra al dashboard.
2. Haz clic en `Exportar Excel`.
3. Se descargara un archivo `.xlsx`.

El archivo contiene las hojas:
- `RESUMEN`
- `CONTROL`
- `PROVEEDORES`
- `RIESGOS`

## 5. Eliminar factura

1. En el dashboard, ubica la factura en la tabla de ultimas facturas.
2. Haz clic en `Eliminar`.
3. Confirma la accion.

La factura se elimina de la base local y el dashboard se actualiza al volver a cargar la pagina.

## 6. Recuperacion de contrasena

1. En la pantalla de login, haz clic en `Olvidaste tu contrasena`.
2. Ingresa tu correo o usuario registrado.
3. Revisa tu correo electronico.
4. Abre el enlace recibido.
5. Captura la nueva contrasena y confirmala.

Por seguridad, el sistema siempre mostrara un mensaje generico, exista o no la cuenta.

## 7. Verificacion en dos pasos (2FA)

### Activar o desactivar
1. Inicia sesion.
2. En el dashboard, localiza la tarjeta de `Verificacion en dos pasos`.
3. Haz clic en `Activar 2FA` o `Desactivar 2FA`.

### Uso diario
Cuando 2FA esta activa:
1. Ingresa usuario y contrasena.
2. Espera el codigo enviado por correo.
3. Capturalo en la pantalla de verificacion.

## 8. Errores controlados que puedes ver

- `Ya existe una factura con ese UUID.`
- `El archivo debe ser un XML.`
- `El archivo excede el tamano maximo permitido.`
- `Solo puedes subir hasta 20 archivos por carga.`
- `Usuario o contrasena incorrectos.`
- `Codigo invalido o expirado.`
- `El enlace de recuperacion es invalido o expiro.`

## 9. Recomendaciones de uso

- Usa solo XML CFDI validos.
- Revisa el dashboard despues de cada carga.
- Exporta Excel cuando necesites compartir o revisar reportes.
- Manten actualizada la configuracion de correo si usas recuperacion de contrasena y 2FA.
