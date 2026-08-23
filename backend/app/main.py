import logging
import os
import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api import accounts, auth, budgets, categories, dashboard, preferences, transactions, users
from app.core.database import SessionLocal
from app.core.logging_config import configure_logging, request_id_var
from app.core.rate_limit import limiter
from app.models import models

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API de Finanzas Personales", description="Backend para gestión de ingresos, gastos y presupuestos."
)

DEFAULT_CATEGORIES = [
    {"name": "Alimentación", "type": "expense", "icon": "UtensilsCrossed"},
    {"name": "Transporte", "type": "expense", "icon": "Car"},
    {"name": "Ocio", "type": "expense", "icon": "Gamepad2"},
    {"name": "Cuidado personal", "type": "expense", "icon": "Heart"},
    {"name": "Suscripción", "type": "expense", "icon": "Radio"},
    {"name": "Otro", "type": "expense", "icon": "CircleEllipsis"},
    {"name": "Salario", "type": "income", "icon": "Wallet"},
]

LEGACY_DEFAULT_CATEGORY_NAMES = {
    ("expense", "Otro"): "Otro (Gasto)",
    ("income", "Otro"): "Otro (Ingreso)",
}


def seed_default_categories() -> None:
    db = SessionLocal()
    try:
        for category_data in DEFAULT_CATEGORIES:
            existing_category = (
                db.query(models.Category)
                .filter(
                    models.Category.user_id.is_(None),
                    models.Category.name == category_data["name"],
                    models.Category.type == category_data["type"],
                )
                .first()
            )

            if existing_category is None:
                legacy_name = LEGACY_DEFAULT_CATEGORY_NAMES.get((category_data["type"], category_data["name"]))
                if legacy_name:
                    existing_category = (
                        db.query(models.Category)
                        .filter(
                            models.Category.user_id.is_(None),
                            models.Category.name == legacy_name,
                            models.Category.type == category_data["type"],
                        )
                        .first()
                    )

                    if existing_category is not None:
                        existing_category.name = category_data["name"]

            if existing_category is not None:
                if existing_category.icon != category_data.get("icon"):
                    existing_category.icon = category_data.get("icon")
            else:
                db.add(models.Category(**category_data, user_id=None))

        db.commit()
    finally:
        db.close()


async def security_headers_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


async def request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
    finally:
        request_id_var.reset(token)


# 2. CONFIGURACIÓN CORS (Bloqueo de Fronteras)
# Leer orígenes permitidos desde variable de entorno
# IPs de Tailscale (100.x.x.x) se permiten vía regex, solo si ENABLE_TAILSCALE_CORS=true
# (el despliegue actual sigue usando Tailscale; al salir de esa red privada, no setear
# la variable desactiva el regex sin bifurcar el código — ver docs/specs/fase_07_spec.md §3.3).
cors_origins_env = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
origenes_permitidos = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

_TAILSCALE_CORS_REGEX = r"^https?://100\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$"
allow_origin_regex = _TAILSCALE_CORS_REGEX if os.getenv("ENABLE_TAILSCALE_CORS", "false").lower() == "true" else None

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=security_headers_middleware,
)

app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=request_id_middleware,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. Conexión de Enrutadores
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transacciones"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["Cuentas"])
app.include_router(categories.router, prefix="/api/categories", tags=["Categorías"])
app.include_router(budgets.router, prefix="/api/budgets", tags=["Presupuestos"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(preferences.router, prefix="/api/users", tags=["Preferencias"])


@app.on_event("startup")
def initialize_shared_data():
    seed_default_categories()


@app.get("/")
def ruta_raiz():
    return {"estado": "OK", "mensaje": "Motor de Finanzas seguro y en línea."}
