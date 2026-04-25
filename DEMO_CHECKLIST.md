# Demo Checklist - FiscalGuard

## 1. Preparacion antes de la demo

Antes de iniciar, confirma:

- la app abre correctamente
- puedes entrar con un usuario de demo
- tienes 3 a 5 XML de prueba listos
- el dashboard tiene datos o puedes cargarlos durante la demo
- la exportacion Excel funciona
- el correo de demo esta listo si vas a mostrar 2FA o recuperacion de contrasena

Ten a la mano:

- usuario y contrasena de demo
- XML normales
- un XML duplicado
- un archivo invalido o no XML
- una narrativa simple del problema del cliente
- precio de lanzamiento vigente:
  - $1,800 MXN pago unico
  - instalacion local incluida
  - soporte anual opcional de $2,000 MXN

## 2. Flujo paso a paso

### Paso 1. Contexto breve
Explica en 20 a 30 segundos:

- que FiscalGuard ayuda a controlar CFDI
- que trabaja en local
- que evita subir informacion a la nube

### Paso 2. Login
Muestra:

- pantalla de acceso
- entrada limpia al sistema
- si aplica, 2FA

### Paso 3. Carga XML
Muestra:

- pantalla de carga
- seleccion multiple
- mensaje de hasta 20 XML
- carga de varios archivos

### Paso 4. Resultado de la carga
Muestra el mensaje:

- nuevas
- duplicadas
- invalidas
- errores

### Paso 5. Dashboard
Muestra primero:

- total facturado
- facturas
- vigentes
- canceladas
- proveedores unicos
- riesgos altos

Luego:

- ultimas facturas
- proveedores principales
- riesgos destacados
- resumen por periodo

### Paso 6. Eliminar factura
Muestra:

- boton eliminar
- confirmacion
- actualizacion del dashboard

### Paso 7. Exportar Excel
Muestra:

- boton `Exportar Excel`
- archivo descargado
- hojas:
  - RESUMEN
  - CONTROL
  - PROVEEDORES
  - RIESGOS

### Paso 8. Seguridad
Si el tiempo lo permite, muestra:

- recuperacion de contrasena
- 2FA

## 3. Que mostrar primero

Orden recomendado:

1. problema que resuelve
2. carga XML
3. dashboard
4. exportacion Excel
5. seguridad

La regla practica es: primero valor operativo, despues detalle tecnico.

## 4. Que evitar

Durante la demo evita:

- entrar a demasiados detalles tecnicos al inicio
- abrir configuracion interna si el cliente no la pidio
- mostrar errores no controlados
- cargar demasiados archivos sin contexto
- hablar primero de tecnologia en lugar de beneficios

No empieces por:

- base de datos
- scripts
- configuraciones internas
- rutas API

## 5. Como cerrar la demo

Cierrala con una idea simple:

- FiscalGuard te da control sobre CFDI
- reduce trabajo manual
- ayuda a detectar problemas antes de que crezcan
- opera localmente

Luego haz una invitacion clara:

- siguiente paso: demo guiada con sus propios XML de prueba
- o instalacion piloto local
- si pregunta precio:
  - lanzamiento de $1,800 MXN pago unico
  - soporte anual opcional de $2,000 MXN

## 6. Troubleshooting rapido

### No inicia sesion
- verifica usuario y contrasena
- revisa si 2FA esta activa

### No carga XML
- confirma que el archivo sea `.xml`
- revisa que no exceda el limite

### Marca duplicado
- explica que el sistema detecta UUID repetido para evitar registros dobles

### No llega correo
- omite esa parte de la demo o explica que depende de SMTP configurado

### No valida SAT
- explica si el entorno de demo esta en modo local

### No exporta Excel
- vuelve a intentar desde dashboard
- confirma que haya datos para exportar

## 7. Cierre sugerido

Frase final:

`Lo importante de FiscalGuard es que no solo guarda CFDI: te da control, contexto y trazabilidad para operar con menos riesgo y menos trabajo manual.`
