# Arquitectura del Backend

## Resumen

La aplicación sigue una arquitectura simple por capas:

- `app/main.py` ensambla la aplicación FastAPI, CORS y routers.
- `app/core/` concentra configuración, base de datos y seguridad.
- `app/models/` define el modelo relacional con SQLAlchemy.
- `app/schemas/` define contratos de entrada y salida con Pydantic.
- `app/api/` implementa los endpoints por dominio funcional.

## Flujo de autenticación

1. El usuario se registra en `/api/users/`.
2. La contraseña se hashea con bcrypt.
3. El login en `/api/auth/login` verifica credenciales.
4. Se emite un JWT con `sub = user_id`.
5. Las rutas protegidas leen el token con `OAuth2PasswordBearer` y recuperan el usuario desde la base.

## Decisiones relevantes

- La autenticación se basa en JWT bearer token.
- La base de datos de desarrollo es SQLite.
- El backend hace validación y reglas de negocio en servidor, no en Frontend.
- El dashboard devuelve agregados ya calculados para evitar lógica duplicada en el cliente.

## Limitaciones conocidas

- No hay refresh tokens.
- No hay sistema de roles o permisos avanzados.
- No hay migraciones automáticas con Alembic.
- No hay logging estructurado ni observabilidad avanzada.
- Los montos siguen modelados como `float`.