# Release Notes - CFDI Shield v1.0

## Version

**CFDI Shield v1.0**

## Resumen

Version final estable para entrega comercial, con instalador Windows generado y flujo principal listo para cliente.

## Estado de entrega

- instalador final generado
- incluye arranque robusto
- incluye templates y static compatibles con PyInstaller
- incluye SAT activo por defecto
- sin endpoints `/debug/*`

## Funcionalidades incluidas

- login y logout
- recuperacion de contrasena
- verificacion en dos pasos
- carga individual y multiple de XML CFDI
- deteccion de duplicados por UUID
- validacion SAT segun configuracion
- cache SAT persistente
- dashboard web con KPIs
- tabla de facturas recientes
- tabla de proveedores principales
- seccion de riesgos destacados
- eliminacion de factura
- reportes internos V3:
  - `RESUMEN`
  - `CONTROL`
  - `PROVEEDORES`
  - `RIESGOS`
- exportacion Excel desde dashboard y API
- scripts de instalacion e inicio para Windows
- documentacion de usuario, instalacion, privacidad, soporte y ventas

## Requisitos

- Windows 10 u 11
- Python local disponible para crear `venv`
- permisos para ejecutar archivos `.bat`
- acceso a SMTP si se usara correo
- acceso de red al SAT si se habilitara validacion SAT real

## Limitaciones conocidas

- la validacion SAT depende de conectividad y permisos de salida del entorno del cliente
- el envio de correo depende de SMTP correctamente configurado
- la version actual exporta reportes a Excel, pero no construye aun un dashboard Excel visual como el script V3 historico
- la fijacion de precio, branding final y datos de contacto comerciales todavia deben definirse por negocio
- la validacion final con `venv\Scripts\python.exe` debe hacerse en el entorno real del cliente si el entorno de pruebas local bloquea ese ejecutable

## Proximos pasos sugeridos

- validacion final en equipo cliente
- prueba SAT real en red permitida
- empaquetado operativo definitivo
- ajuste final de textos comerciales y legales
- corte de version estable despues de piloto
