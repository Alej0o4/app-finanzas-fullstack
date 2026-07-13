# Guía de despliegue y operación

## Variables de entorno

| Variable | Requerida | Descripción |
|----------|-----------|-------------|
| `SECRET_KEY` | Sí | Clave para firmar JWT. Generar con `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DATABASE_URL` | Sí (Docker) | URL de conexión a PostgreSQL. Ej: `postgresql://oikos:oikos_secret@postgres:5432/oikos` |
| `ALLOWED_ORIGINS` | Sí | Orígenes CORS permitidos, separados por coma. Ej: `http://localhost:3000,http://100.124.221.83:3000` |

En ausencia de `DATABASE_URL`, el backend usa SQLite como fallback (`sqlite:///./finanzas.db`).

## Despliegue con Docker (recomendado)

### Producción

```sh
# Levantar todo (postgres + backend + frontend)
docker compose up -d --build

# Ver estado
docker compose ps

# Logs
docker compose logs -f backend
```

### Desarrollo (hot-reload)

```sh
# Sin rebuilds — cambios se reflejan al instante
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Seed de datos de prueba

```sh
docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"
# Credenciales: test@test.com / testpass123
```

### Resetear base de datos

```sh
docker compose down -v   # -v elimina el volumen de PostgreSQL
docker compose up -d --build
```

## Despliegue sin Docker (alternativa)

```sh
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://oikos:oikos_secret@localhost:5432/oikos"
export SECRET_KEY="tu-clave-secreta"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
pnpm install
NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

## Healthchecks

Los servicios exponen healthchecks en Docker:

| Servicio | Endpoint | Intervalo |
|----------|----------|-----------|
| postgres | `pg_isready -U oikos` | 5s |
| backend | `GET /` (HTTP status) | 10s |
| frontend | (sin healthcheck — Next.js standalone no expone endpoint de salud) | — |

## Variables de entorno para producción

### Backend

```env
SECRET_KEY=<generar-con-secrets-module>
DATABASE_URL=postgresql://oikos:<password>@<host>:5432/oikos
ALLOWED_ORIGINS=https://tu-dominio.com
```

### Frontend (build-time)

```env
NEXT_PUBLIC_API_URL=https://tu-backend.com
```

> `NEXT_PUBLIC_API_URL` se inyecta al buildear la imagen Docker. Para cambiarla, reconstruir con `docker compose up --build`.

## Riesgos operativos actuales

- Precisión monetaria basada en `Decimal`/`Numeric` que debe mantenerse consistente entre backend y frontend.
- Falta de observabilidad estructurada.
- Falta de logging centralizado.
- Falta de migraciones y rollback formal (usa `create_all()` en startup).
- Backup manual del volumen PostgreSQL (ver REFACTOR_ROADMAP Fase 5).

## Checklist antes de escalar

1. Configuración por entorno.
2. Migraciones (Alembic).
3. Observabilidad.
4. Seguridad HTTP adicional (HTTPS, rate limiting generalizado).
5. Pruebas de integración para transacciones y presupuestos.
6. Backup automático del volumen PostgreSQL.
