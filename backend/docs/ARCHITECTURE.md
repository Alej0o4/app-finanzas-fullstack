# Arquitectura del Backend

## Resumen

La aplicación sigue una arquitectura simple por capas:

- `app/main.py` ensambla la aplicación FastAPI, CORS y routers.
- `app/core/` concentra configuración, base de datos, seguridad y rate limiting (`rate_limit.py`).
- `app/models/` define el modelo relacional con SQLAlchemy (6 modelos: User, Account, Category, Transaction, Budget, RefreshToken).
- `app/schemas/` define contratos de entrada y salida con Pydantic.
- `app/api/` implementa los endpoints por dominio funcional.

## Flujo de autenticación

1. El usuario se registra en `/api/users/`.
2. La contraseña se hashea con bcrypt.
3. El login en `/api/auth/login` verifica credenciales (rate limiting: 5 req/min).
4. Se emite un JWT con `sub = user_id` (expira en 60 min).
5. Se genera un refresh token opaco (expira en 30 días, almacenado hasheado en DB).
6. Las rutas protegidas leen el token con `OAuth2PasswordBearer` y recuperan el usuario desde la base.
7. `/api/auth/refresh` rota el refresh token y emite un nuevo JWT.
8. `/api/auth/logout` revoca el refresh token.

## Decisiones relevantes

- La autenticación se basa en JWT bearer token + refresh token rotation.
- Refresh token: `RefreshToken` model con `token_hash` (SHA-256), `user_id`, `expires_at` (30 días), `revoked_at`. Se almacena hasheado; el token opaco viaja al frontend.
- CORS configurado vía variable de entorno `ALLOWED_ORIGINS` + regex para IPs de Tailscale (100.x.x.x).
- Rate limiting en login via `slowapi` (5 req/min). Instancia `Limiter` en `app/core/rate_limit.py`, registrada en `main.py:127`.
- La base de datos es PostgreSQL en Docker (`postgres:16-alpine`), con fallback a SQLite en ausencia de `DATABASE_URL`.
- El backend hace validación y reglas de negocio en servidor, no en Frontend.
- El dashboard devuelve agregados ya calculados para evitar lógica duplicada en el cliente.
- Los montos se modelan como `Decimal` en contratos y `Numeric(14, 2)` en persistencia para evitar precisión flotante.
- Las categorías base del sistema se siembran al arrancar la aplicación.
- Cada cuenta, transacción y presupuesto almacena su moneda (`currency` column, default "COP").
- Preferencias de usuario: `preferred_currency`, `preferred_locale`, `preferred_theme`, `weekly_summary_enabled` y `timezone` (exponen en `GET/PATCH /api/users/me/preferences`).

## Zona horaria (Fase 34)

- `User.timezone` (migración `a34c0de1b7f2`) es la zona IANA del usuario; `app/core/timezones.py` es el único punto de validación (`es_zona_valida`, `zona_o_default`, `get_zoneinfo`).
- `app/core/periods.py` es el módulo único de aritmética de calendario con zona: funciones puras con `ahora` y la zona inyectados (`resolver_mes`, `rango_mes`, `limites_semana`, `rango_dias`, `dia_local`, `instante_de_dia`, `resolver_rango`). Devuelve datetimes aware en UTC con límite superior exclusivo. Lo consumen `api/dashboard.py`, `api/accounts.py`, `api/transactions.py`, `core/budget_alerts.py` y `core/weekly_summary.py`; ningún otro módulo construye `datetime(...)` naive ni resuelve "actual" desde UTC.
- `core/weekly_summary.py` calcula la semana en la zona de cada usuario (la constante `SUMMARY_TIMEZONE` se eliminó); el cron sigue siendo único (lunes 07:00 `America/Bogota`, `main.py`).
- `tzdata` está en `requirements.txt`: la imagen slim de Docker no trae los alias IANA que lista Chrome (`Asia/Calcutta`, `Europe/Kiev`…); sin él el selector de Ajustes ofrecería zonas que el backend rechaza con `422`. Tras traer este cambio hay que reconstruir la imagen y reinstalar requirements en los venvs locales.
- La migración de datos `c7d3e9a4b1f6` (separada de la del esquema) mueve las fechas históricas `00:00Z` a `17:00Z`; corre sola en el `CMD` de Docker con `alembic upgrade head`. `scripts/fase34_reporte_x1.py` genera el reporte de totales antes/después sobre una copia.

## Migraciones en runtime (sin Alembic)

En cada arranque, `main.py` ejecuta:

1. `_ensure_user_preference_columns()` — inspecciona columnas de `users` y agrega `preferred_currency`, `preferred_locale`, `preferred_theme` vía `ALTER TABLE ADD COLUMN` si no existen. Permite agregar preferencias nuevas sin romper la DB existente.
2. `seed_default_categories()` — si la tabla `categories` está vacía, inserta las categorías base del sistema (gasto e ingreso).
3. Migración de categorías legacy — renombra `"Otro (Gasto)"` → `"Otro"` y migra transacciones de `"Otro (Ingreso)"` a `"Otro"` con `type=income`.

## Limitaciones conocidas

- No hay sistema de roles o permisos avanzados.
- No hay migraciones automáticas con Alembic (`create_all()` en startup).
- No hay logging estructurado ni observabilidad avanzada.
- La sesión de navegador usa cookies `httpOnly` + CSRF double-submit desde Fase 26 (antes: JWT en `localStorage`, vulnerable a XSS). Los clientes no-browser (API keys `oikos_pat_...`) siguen autenticando por header `Authorization: Bearer` sin cookies.
- Las rutas agregadas del dashboard incluyen resumen, progreso de presupuestos, serie temporal de flujo de caja y distribución por categoría.