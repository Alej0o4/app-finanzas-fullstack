# Backend de Finanzas Personales

Backend para un MVP de finanzas personales construido con FastAPI, SQLAlchemy y JWT. Este proyecto cubre autenticación, usuarios, cuentas, categorías, transacciones, presupuestos y un dashboard con agregados listos para el Frontend.

## Alcance funcional

- Registro e inicio de sesión con JWT.
- CRUD de transacciones con impacto contable sobre cuentas.
- CRUD de cuentas con saldo inicial y saldo derivado de movimientos.
- CRUD de categorías con categorías base del sistema y categorías personalizadas.
- CRUD de presupuestos por categoría, mes y año.
- Endpoints agregados para dashboard.

## Documentación técnica

- [Arquitectura y decisiones](docs/ARCHITECTURE.md)
- [Referencia de API](docs/API_REFERENCE.md)
- [Reglas de negocio](docs/BUSINESS_RULES.md)
- [Guía de integración para Frontend](docs/FRONTEND_INTEGRATION.md)
- [Guía de despliegue y operación](docs/DEPLOYMENT.md)

## Arranque local

1. Crear y activar un entorno virtual.
2. Instalar dependencias con `pip install -r requirements.txt`.
3. Definir `SECRET_KEY` en el archivo `.env`.
4. Ejecutar la aplicación con Uvicorn apuntando a `app.main:app`.

## Notas importantes

- El backend usa SQLite en desarrollo.
- El secret de JWT debe venir desde variables de entorno.
- Los montos se validan en el backend con tipos decimales; conviene mantener ese criterio en contratos y persistencia.