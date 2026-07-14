# Oikos

App web de finanzas personales con soporte multi-moneda. Backend en FastAPI, frontend en Next.js App Router, base de datos PostgreSQL.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, Pydantic |
| Frontend | React 19, Next.js 15 App Router, TanStack Query, Zustand, Recharts, Tailwind CSS 4 |
| Base de datos | PostgreSQL 16 (Docker) o SQLite (desarrollo sin Docker) |
| Autenticación | JWT + Refresh Token rotation, bcrypt |
| Rate limiting | slowapi (5 req/min en login) |

## Requisitos

- Docker + Docker Compose (recomendado)
- O: Python 3.12, Node.js 22, pnpm 9

## Inicio rápido

### Docker (recomendado)

```sh
# Producción — levantar todo
docker compose up -d --build

# Desarrollo — hot-reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Logs
docker compose logs -f backend
```

### Sin Docker

```sh
# Backend (necesita .env con SECRET_KEY)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0

# Frontend
cd frontend
pnpm install
pnpm dev
```

## Carga de datos de prueba

```sh
# Docker
docker compose exec backend python -c "from app.core.seed import run_seed; run_seed()"

# Sin Docker (desde backend/)
python -c "from app.core.seed import run_seed; run_seed()"
```

Crea 3 cuentas, 45 transacciones y 6 presupuestos multi-moneda.

### Credenciales de prueba

- **Email**: `test@test.com`
- **Contraseña**: `testpass123`

## Estructura del proyecto

```
oikos/
├── backend/          # API REST (FastAPI)
│   ├── app/
│   │   ├── api/      # Routers
│   │   ├── core/     # Config, seguridad, DB
│   │   ├── models/   # SQLAlchemy models
│   │   └── schemas/  # Pydantic schemas
│   ├── Dockerfile
│   └── README.md
├── frontend/         # SPA (Next.js)
│   ├── app/          # App Router pages
│   ├── components/   # UI components
│   ├── lib/          # Utilidades, hooks, API client
│   ├── types/        # TypeScript interfaces
│   ├── Dockerfile
│   └── README.md
├── docs/             # Documentación
├── scripts/          # Scripts de utilidad
├── docker-compose.yml
└── README.md
```

## Documentación relacionada

- [Reglas de negocio](backend/docs/BUSINESS_RULES.md)
- [API Reference](backend/docs/API_REFERENCE.md)
- [Contrato frontend](frontend/docs/API_CONTRACT.md)
- [Roadmap](docs/ROADMAP.md)
- [TODO / Deuda técnica](docs/TODO.md)
