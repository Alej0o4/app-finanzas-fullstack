# Guía de despliegue y operación

## Variables de entorno mínimas

- `SECRET_KEY`

## Recomendaciones para producción

- Migrar a PostgreSQL.
- Reemplazar `Base.metadata.create_all()` por migraciones con Alembic.
- Externalizar secretos y configuración por entorno.
- Ejecutar detrás de un servidor ASGI apropiado para producción.
- Revisar CORS para que solo incluya los orígenes necesarios.

## Riesgos operativos actuales

- Precisión monetaria basada en `Decimal`/`Numeric` que debe mantenerse consistente entre backend y frontend.
- Falta de observabilidad estructurada.
- Falta de rate limiting.
- Falta de logging centralizado.
- Falta de migraciones y rollback formal.

## Checklist antes de escalar

1. Configuración por entorno.
2. Migraciones.
3. Observabilidad.
4. Seguridad HTTP adicional.
5. Pruebas de integración para transacciones y presupuestos.