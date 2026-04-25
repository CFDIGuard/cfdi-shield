# Aviso de Privacidad - FiscalGuard

## 1. Naturaleza del sistema

FiscalGuard se ofrece como una solucion local para procesamiento y control de CFDI.

En su version local:
- no opera como servicio en la nube
- no envia informacion a servidores propios del proveedor
- no integra telemetria ni analitica remota por defecto

## 2. Datos tratados

El sistema puede tratar, de forma local, datos contenidos en archivos CFDI y datos de acceso al sistema, incluyendo:

- RFC de emisor y receptor
- razon social
- UUID
- fecha, folio y montos
- IVA, retenciones y total
- estatus SAT cuando la validacion esta habilitada
- usuario de acceso
- correo electronico del usuario

## 3. Finalidad del tratamiento

Los datos se tratan con las siguientes finalidades:

- procesar y organizar CFDI
- detectar duplicados por UUID
- generar tableros y reportes
- exportar reportes en Excel
- habilitar autenticacion, recuperacion de contrasena y 2FA
- apoyar controles administrativos y fiscales internos

## 4. Conservacion y ubicacion de los datos

Los datos se almacenan localmente en el entorno donde el cliente instala FiscalGuard, principalmente en su base de datos y archivos de configuracion.

La permanencia de la informacion depende de:
- politicas internas del cliente
- respaldos realizados por el cliente
- eliminaciones manuales efectuadas por usuarios autorizados

## 5. Transferencias

En modo local, FiscalGuard no transfiere datos a terceros de forma automatica.

Excepciones operativas:
- consulta SAT, solo si el cliente habilita la validacion SAT
- envio de correos, solo si el cliente configura un servidor SMTP

## 6. Medidas generales

FiscalGuard incorpora medidas como:
- autenticacion con usuario y contrasena
- cookies HTTP-only
- hash de contrasenas
- 2FA opcional
- operacion local sin telemetria

## 7. Derechos y control del cliente

El cliente conserva control operativo sobre:
- la instalacion local
- la configuracion del sistema
- los respaldos
- la eliminacion de facturas
- la habilitacion o deshabilitacion de SAT y correo

## 8. Contacto

Para temas de privacidad, soporte o aclaraciones, el responsable comercial u operativo de FiscalGuard debera colocar aqui su medio de contacto oficial.

Ejemplo:

- correo: `soporte@fiscalguard.local`
- telefono: `pendiente de definir`
