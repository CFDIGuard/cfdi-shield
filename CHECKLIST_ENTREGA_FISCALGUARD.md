# CFDI Shield - Checklist de Aceptacion Cliente (v1.0 RC)

## 1. Estado del sistema
[ ] Servicio Windows CFDIShield corriendo correctamente
[ ] Puerto 8000 accesible
[ ] /health responde OK
[ ] /debug/routes NO expuesto en produccion

## 2. Acceso y seguridad
[ ] Login funcional
[ ] Registro funcional
[ ] Recuperacion de contrasena funcional
[ ] 2FA activable y verificable
[ ] Logout correcto

## 3. Carga de CFDI
[ ] Carga individual XML
[ ] Carga multiple XML
[ ] Manejo de errores (XML invalido)
[ ] Deteccion de duplicados funcional

## 4. Validacion SAT
Modo SAT ACTIVADO:
[ ] Consulta SAT ejecuta correctamente
[ ] Estatus reflejado como VIGENTE/CANCELADO

Modo SAT DESACTIVADO:
[ ] No se consulta SAT
[ ] No se usa cache
[ ] Facturas quedan como SIN_VALIDACION
[ ] Dashboard refleja correctamente "Sin validacion SAT"

## 5. Dashboard
[ ] Conteo total correcto
[ ] Vigentes correctos
[ ] Canceladas correctas
[ ] Sin validacion SAT correcto
[ ] KPIs cargan sin errores

## 6. Exportacion
[ ] Exportacion Excel funciona
[ ] Datos coinciden con dashboard
[ ] Columnas SAT coherentes con modo activo/desactivado

## 7. Operacion
[ ] Eliminacion de facturas funciona
[ ] Revalidacion SAT funciona
[ ] Sistema responde sin errores visibles

## 8. Configuracion
[ ] LOCAL_MODE funciona correctamente
[ ] ENABLE_SAT_VALIDATION respeta configuracion
[ ] Toggle SAT por usuario funcional

## 9. Performance
[ ] Carga de multiples XML fluida
[ ] Dashboard carga en < 3 segundos
[ ] Exportacion en tiempo razonable

## 10. Entorno
[ ] .env configurado correctamente
[ ] Base de datos lista (demo o limpia)
[ ] Logs funcionando
[ ] Servicio NSSM estable

## 11. Entrega
[ ] Manual de instalacion incluido
[ ] Manual de uso incluido
[ ] Precio definido ($1,800 MXN lanzamiento)
[ ] Pitch listo

## Resultado final
[ ] APROBADO PARA ENTREGA
[ ] REQUIERE AJUSTES

Objetivo:
Permitir validar rapidamente si CFDI Shield esta listo para cliente final.
