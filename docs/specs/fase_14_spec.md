# Spec — Fase 14: Resumen semanal automático

> Plan de implementación detallado para los 4 ítems de Fase 14 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 14 — Resumen semanal
> automático"). Este documento no cambia el alcance ahí definido — lo desglosa en tareas
> ejecutables, con archivos concretos, esquemas de datos, decisiones de diseño numeradas y una
> estimación de horas revisada contra el código real.
>
> **No implementa nada.** Es el hand-off para quien vaya a codear (backend-engineer /
> frontend-engineer). Ningún archivo del repositorio fuera de `docs/specs/fase_14_spec.md` fue
> modificado al producir este documento. La evaluación arquitectónica de las implicaciones
> (scheduler, idempotencia, timezone, alcance real del ítem de preferencia) se hizo con el agente
> `software-architect` antes de redactar este documento — las decisiones abajo son su análisis,
> verificado contra el código real de `backend/`.

Estado del repo al momento de escribir esto (2026-09-06): Fases 7–13 están completas. Fase 13
(presupuestos con alertas + infraestructura de notificaciones/push) es la que más importa como
precedente aquí — dejó, a propósito, el terreno preparado para esta fase (ver hallazgo 1). Fase 14
es la primera fase que introduce un **job periódico** en el proyecto: hasta hoy todo lo que corre
en el backend es una respuesta a un request HTTP (incluida la evaluación de presupuestos de Fase
13, que es síncrona dentro del propio request de crear/editar transacción). No existe scheduler,
cola de trabajos, ni ningún otro mecanismo de "correr algo sin que un usuario lo dispare".

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El modelo de datos para "dónde vive el aviso" ya está listo — Fase 13 lo construyó
   previendo esta fase, verificado línea por línea.** `backend/app/models/models.py:193-235`
   (`Notification`): el comentario de clase dice literalmente *"tanto el motor de presupuestos
   (§13.3) como, en el futuro, el resumen semanal de Fase 14, insertan aquí"*; el campo `type`
   trae el comentario `# Fase 14 agrega "weekly_summary"`; `budget_id` es nullable con el
   comentario *"Fase 14 (resumen semanal) no apunta a un presupuesto puntual"*. No hace falta
   una tabla nueva para el aviso en sí.

2. **Pero el índice único que da idempotencia a Fase 13 EXCLUYE explícitamente las filas de esta
   fase — no hay ninguna protección de unicidad a nivel de base de datos hoy para
   `weekly_summary`.** El índice `uq_notifications_budget_type_active`
   (`models.py:227-234`) es `postgresql_where=text("budget_id IS NOT NULL")` — a propósito, para
   que las notificaciones sin presupuesto (esta fase) no ocupen slot de esa unicidad. Es decir: el
   comentario del modelo puede leerse como "ya está resuelto", pero solo resuelve *dónde* vive el
   aviso, no *cómo se evita duplicarlo*. Eso lo resuelve este documento (Decisión 14.1.2).

3. **El módulo `budget_alerts.py` ya es, de facto, un módulo de utilidades compartidas disfrazado
   de módulo de un solo propósito — antes incluso de que Fase 14 lo toque.**
   `backend/app/api/dashboard.py:10` ya importa `spent_por_categoria_y_moneda` desde
   `budget_alerts.py` para su propio uso, sin relación con alertas de presupuesto. El resumen
   semanal necesita el mismo patrón de "persistir en `notifications` + enviar push" que ya vive en
   `_crear_notificacion`/`_enviar_push` (`budget_alerts.py:138-231`) — si Fase 14 llama a esas
   funciones sin moverlas, el nombre del módulo queda definitivamente equivocado. Se extraen a un
   módulo neutral (Decisión 14.2.1).

4. **`spent_por_categoria_y_moneda` NO es reusable tal cual para el resumen semanal.** Está atada
   a (a) un conjunto de `category_ids` conocido de antemano —viene de los presupuestos existentes
   del usuario— y (b) un rango de **mes calendario completo** (`monthrange`), no una ventana
   arbitraria de 7 días. El resumen semanal necesita una query nueva que siga el mismo idioma
   (agrupar por `(category_id, currency)`, filtrar `type == "expense"` + rango de fechas) pero
   parametrizada por fecha de inicio/fin arbitraria y sin restringir `category_id` de antemano —
   ver Decisión 14.3.2. Esto importa especialmente porque el proyecto ya corrigió **tres bugs de
   mezcla de monedas** en Fase 11 (`ROADMAP.md:276-282`): el resumen semanal es la cuarta
   oportunidad de reintroducir el mismo defecto si no se sigue exactamente ese idioma de query.

5. **No existe ningún scheduler, cola de trabajo, ni hook de `shutdown` en toda la app —
   confirmado, no asumido.** `backend/requirements.txt` no tiene APScheduler, Celery, RQ ni
   Redis. `backend/app/main.py` solo declara `@app.on_event("startup")`
   (líneas 180-182, llama a `seed_default_categories()`) — **no hay ningún
   `@app.on_event("shutdown")` en todo el archivo.** Esto importa: si se arranca un
   `BackgroundScheduler` en `startup` sin un `shutdown` simétrico, cada reinicio del proceso (en
   particular `docker-compose.dev.yml`, que corre con `--reload` y reinicia el proceso en cada
   cambio de archivo) deja un hilo de scheduler huérfano.

6. **El deployment es un solo contenedor backend, un solo proceso `uvicorn` sin `--workers`.**
   `backend/Dockerfile:14` (`CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app
   --host 0.0.0.0 --port 8000"]`) y `docker-compose.yml` solo declaran un servicio `backend`, sin
   réplicas, con `restart: unless-stopped`. Es el mismo hecho que ya usó Fase 7 para diferir el
   rate limiting distribuido (`docs/ROADMAP.md:96-100`, §2.6.1 de `fase_07_spec.md`) — aplica
   textualmente al scheduler de esta fase: un `BackgroundScheduler` in-process no tiene problema
   de coordinación entre procesos porque no hay más de un proceso.

7. **No existe ningún dato de zona horaria en el proyecto, en ningún nivel.** `grep -rn
   "timezone|ZoneInfo|pytz|tzinfo" backend/app` solo devuelve metadata de tipo de columna
   (`DateTime(timezone=True)`), nunca lógica de zona horaria de usuario. Todo el código usa
   `datetime.now(UTC)` (`dashboard.py:53`, `seed.py:174`, `notifications.py:86`). No hay columna
   `User.timezone`. "Cada lunes" (`docs/ROADMAP.md:45`, sección "El MVP en cinco componentes") no
   tiene, hoy, ninguna zona horaria de referencia.

8. **`freezegun` está en `requirements.txt` (línea 61) pero solo se usa hoy en
   `test_auth.py`**, para el TTL del JWT (`from freezegun import freeze_time`,
   `with freeze_time(now + timedelta(minutes=14, seconds=30)):`). Ningún test de
   `test_budget_alerts.py` lo necesita, porque esa lógica solo depende de `month`/`year`, no de
   "hoy". El resumen semanal sería el primer uso real de `freezegun` para congelar una ventana de
   fechas de 7 días — no hay un test existente que copiar 1:1, solo el patrón mecánico.

9. **`User` no tiene ninguna columna de preferencia de notificaciones, y no existe ninguna
   superficie de "Ajustes"/"Perfil" en el frontend hoy.** `PreferencesUpdate`
   (`backend/app/schemas/schemas.py:97-100`) solo cubre `preferred_currency/locale/theme`. El
   único punto de la UI que escribe preferencias es `frontend/components/ThemeToggle.tsx`
   (`api.patch('users/me/preferences', ...)`) — no hay ninguna página `settings`/`profile`
   (`find frontend/app -iname "*setting*" -o -iname "*profile*"` no devuelve nada). El ROADMAP
   dimensiona el ítem de preferencia en 4h asumiendo que solo falta el campo backend + un
   checkbox; en realidad hace falta construir la primera superficie de ajustes del producto — ver
   Decisión 14.6.3 y el ajuste de horas en la tabla final.

10. **`docs/BUSINESS_RULES.md` no tiene ninguna sección de Notificaciones/Push**, pese a que Fase
    13 ya envió 7 endpoints nuevos (`notifications.py`, `push.py`). Es deuda preexistente, no
    introducida por esta fase, pero Fase 14 la agrava (un `type` nuevo, una preferencia nueva) si
    se pospone otra vez — se cierra en este documento (§14.7) en vez de diferirla de nuevo.

11. **`seed.py` ya borra `Notification` en el orden correcto de FKs** (líneas 107-127) — si se
    agrega la columna `period_key` (sin tabla nueva), no requiere ningún cambio en el seed. Si
    Fase 14 introdujera una tabla de estado separada (descartado, ver Decisión 14.1.2), sí
    necesitaría entrar en ese mismo bloque.

12. **`budget_recurrence.ensure_recurring_budgets_for_period` es el patrón de referencia más
    cercano a "garantizar algo una vez por período de forma idempotente"**, y resuelve el
    problema con un índice único parcial + `except IntegrityError: db.rollback()` — mismo idioma
    que se recomienda para la Decisión 14.1.2, no algo que haya que inventar de cero.

---

## Orden de dependencia real (no el orden del ROADMAP)

El ROADMAP lista los 4 ítems en el orden "scheduler → cálculo → envío → preferencia", pero
scheduler y envío son, en la práctica, la infraestructura alrededor de una sola función central
("calcular y notificar a un usuario"); construirla primero como función pura, sin nada que la
dispare todavía, es lo que permite probarla con `freezegun` sin depender de que el scheduler
funcione. Dependencia real:

```
1. Modelo de datos (§14.1)               — columna `User.weekly_summary_enabled` + columna
   `Notification.period_key` + índice único parcial nuevo. Prerrequisito de todo lo demás: el
   cálculo (3) necesita period_key para su propia idempotencia, y el scheduler (4) necesita
   filtrar por weekly_summary_enabled antes de iterar usuarios.

2. Extracción de _crear_notificacion/_enviar_push a módulo neutral (§14.2) — refactor previo,
   sin lógica nueva. Se hace antes del cálculo (3) para que este último ya llame a la versión
   final, sin tener que tocarla otra vez después.

3. Cálculo del resumen semanal (§14.3) — función pura invocable directamente
   (`build_and_send_weekly_summary(db, user, reference_date)`), sin nada que la dispare todavía.
   Es la pieza que se prueba con freezegun sin necesitar el scheduler corriendo.

4. Scheduler (§14.4) — invoca (3) para todos los usuarios con weekly_summary_enabled=True, cada
   lunes. Depende de (1) para el filtro y de (3) para tener qué invocar.

5. Envío push + bandeja (§14.5) — no es un paso aparte: ya lo resuelve (2)+(3). Se documenta como
   ítem propio solo porque el ROADMAP lo lista como tal, pero no hay trabajo adicional aquí más
   allá de lo ya cubierto.

6. Preferencia de usuario, superficie de UI (§14.6) — la columna ya existe desde (1); lo que
   falta es el endpoint (extensión barata) y la página de Ajustes del frontend (el trabajo real
   no dimensionado por el ROADMAP, hallazgo 9). Puede construirse en paralelo desde el día 1.
```

Orden de implementación recomendado: **14.1 → 14.2 → 14.3 → 14.4, con 14.6 en paralelo desde el
día 1**. El ítem "Envío" del ROADMAP no es un paso independiente — se disuelve en 14.2+14.3, y se
documenta así explícitamente para que quien implemente no busque un ítem separado que no existe.

---

## 14.1 Modelo de datos y migración

**Decisión 14.1.1 — `User.weekly_summary_enabled`, `Boolean, nullable=False, default=True`
(opt-out, no opt-in).** A diferencia de Fase 13 (que decidió explícitamente NO agregar ningún
toggle de notificaciones, `docs/specs/fase_13_spec.md` hallazgo 8), el ROADMAP de Fase 14 sí pide
el toggle — la pregunta abierta no es "¿toggle sí o no?" sino "¿qué default?". Un default opt-in
(`default=False`) dejaría la feature en 0% de alcance real al lanzamiento: nadie tiene ningún
gancho de UI para encontrar el ajuste el primer día (hallazgo 9), lo que contradice el objetivo
explícito del ROADMAP ("re-engagement pasivo, el usuario recibe valor sin abrir la app"). El
riesgo de spam de un opt-out es bajo — máximo un envío por semana, a diferencia de las alertas de
presupuesto de Fase 13, que pueden dispararse varias veces por período.

```python
# backend/app/models/models.py, clase User
weekly_summary_enabled = Column(Boolean, nullable=False, default=True)
```

**Decisión 14.1.2 — idempotencia por `Notification.period_key` + índice único parcial nuevo, no
solo un chequeo de aplicación.** El índice existente de Fase 13
(`uq_notifications_budget_type_active`) excluye a propósito las filas sin `budget_id`
(hallazgo 2) — las notificaciones de `weekly_summary` no tienen hoy ningún backstop de base de
datos. A diferencia del motor de alertas de Fase 13 (invocado una vez por transacción, dentro de
un solo request HTTP), el job semanal **itera todos los usuarios en un loop fuera de un request**
— el escenario realista de fallo (crash a mitad del loop, doble disparo del scheduler tras un
restart) es justamente el que un chequeo de aplicación ("¿ya existe un `weekly_summary` de los
últimos 6 días?") no cubre de forma segura bajo condición de carrera. Mismo criterio que ya usa el
proyecto para presupuestos duplicados (`uq_budgets_user_category_period_active`,
`models.py:111-121`) y para el motor de alertas (Decisión 13.3.2: "garantía de base de datos, no
solo de aplicación") — aplica con más fuerza aquí, no menos.

```python
# backend/app/models/models.py, clase Notification — agregar columna e índice
    # `period_key` (Fase 14, p. ej. "2026-W37" vía `date.isocalendar()`) identifica el período
    # que originó un aviso sin ligarlo a una entidad de dominio como `budget_id` — nullable
    # porque las notificaciones de Fase 13 (alertas de presupuesto) no tienen período semanal.
    period_key = Column(String(10), nullable=True)

    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
        Index(
            "uq_notifications_budget_type_active",
            "budget_id", "type", unique=True,
            postgresql_where=text("budget_id IS NOT NULL"),
            sqlite_where=text("budget_id IS NOT NULL"),
        ),
        # Fase 14: un `weekly_summary` por usuario y semana ISO — mismo idioma que el índice
        # de arriba, con `period_key` en vez de `budget_id` como discriminador de período.
        Index(
            "uq_notifications_user_type_period_active",
            "user_id", "type", "period_key", unique=True,
            postgresql_where=text("period_key IS NOT NULL"),
            sqlite_where=text("period_key IS NOT NULL"),
        ),
    )
```

*(Nota: confirmar el `sqlite_where` exacto del índice ya existente leyendo el modelo real antes de
copiar — este documento reproduce lo visto en `models.py:227-234`, revisar si el proyecto usa
`sqlite_where` o si SQLite simplemente ignora `postgresql_where`; los tests corren sobre SQLite en
memoria, así que esto decide si la unicidad se ejercita en la suite de pytest o solo en Postgres.)*

**Decisión 14.1.3 — `NotificationType` (schemas.py) gana el miembro `weekly_summary`, la
columna sigue siendo `String(30)` libre (no `Enum` de Postgres).** Mismo criterio que Decisión
13.5.2: un `Enum` de base de datos exige una migración de esquema por cada `type` nuevo; el
proyecto ya evita eso (`Transaction.payment_method` valida el enum solo en Pydantic).

```python
# backend/app/schemas/schemas.py
class NotificationType(str, Enum):
    budget_threshold_80 = "budget_threshold_80"
    budget_threshold_100 = "budget_threshold_100"
    weekly_summary = "weekly_summary"  # Fase 14


class NotificationResponse(BaseModel):
    id: int
    type: str
    title: str
    body: str
    budget_id: int | None = None
    period_key: str | None = None  # Fase 14
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
```

**Migración Alembic:** `alembic revision --autogenerate -m "fase_14_weekly_summary"` — dos
columnas nuevas (`users.weekly_summary_enabled`, `notifications.period_key`) + un índice único
parcial nuevo. Revisar a mano que el autogenerate capture el `postgresql_where`/`sqlite_where` del
índice (Alembic no siempre lo infiere bien en índices parciales — comparar contra la migración de
Fase 13 que creó `uq_notifications_budget_type_active` como referencia de qué debería generar).
`server_default=text("true")` para `weekly_summary_enabled` en la migración (no solo `default` de
SQLAlchemy) — mismo criterio que `updated_at` en `User` (`models.py`, comentario sobre
`server_default` cubriendo bases ya migradas donde SQLite no permite `ADD COLUMN` con default no
constante).

---

## 14.2 Refactor previo: módulo de notificación/push compartido

**Decisión 14.2.1 — extraer `_crear_notificacion`/`_enviar_push` de `budget_alerts.py` a un
módulo neutral, `backend/app/core/notification_dispatch.py`, antes de escribir el cálculo del
resumen semanal.** `budget_alerts.py` ya es de facto un módulo de utilidades compartidas
(hallazgo 3) — llamarlo desde `weekly_summary.py` sin moverlo dejaría un nombre de módulo
engañoso permanentemente. La firma se generaliza para no asumir un `Budget`:

```python
# backend/app/core/notification_dispatch.py
def crear_y_enviar_notificacion(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    body: str,
    budget_id: int | None = None,
    period_key: str | None = None,
) -> models.Notification:
    """Persiste el aviso en la bandeja in-app y dispara el push sobre la misma fila
    (Decisión 13.2.3, ahora compartida entre el motor de presupuestos y el resumen
    semanal). Un fallo aquí es un fallo del caller — este helper no atrapa excepciones
    de escritura en `notifications`, solo las de envío push (ver `enviar_push`)."""
    notificacion = models.Notification(
        user_id=user_id, type=type, title=title, body=body,
        budget_id=budget_id, period_key=period_key,
    )
    db.add(notificacion)
    db.commit()
    enviar_push(db, notificacion)
    return notificacion


def enviar_push(db: Session, notificacion: models.Notification) -> None:
    ...  # cuerpo idéntico al `_enviar_push` actual de budget_alerts.py, sin cambios de lógica
```

`budget_alerts.py` pasa a importar `crear_y_enviar_notificacion` desde el módulo nuevo en vez de
definir su propia `_crear_notificacion`/`_enviar_push` — cero cambio de comportamiento, solo
ubicación. Actualizar `backend/tests/test_budget_alerts.py` si mockea `_enviar_push` por su
nombre/ruta anterior.

---

## 14.3 Cálculo del resumen semanal

**Decisión 14.3.1 — semana = lunes 00:00 a domingo 23:59:59, en una zona horaria fija de
despliegue (`America/Bogota`), no por usuario.** No existe ninguna infraestructura de timezone
por usuario (hallazgo 7), y el proyecto ya descarta i18n explícitamente
(`docs/ROADMAP.md`, "Fuera de scope"). `America/Bogota` es coherente con los defaults actuales
(`User.preferred_currency="COP"`, `preferred_locale="es-CO"`). Se fija como constante en el módulo
nuevo, no como variable de entorno — no hay ningún otro despliegue previsto que la necesite
distinta, y agregar una env var para un valor que no varía sería la misma complejidad
desproporcionada que el proyecto ya evita en otros lados. Diferido a propósito: timezone por
usuario, si el proyecto sale de LATAM (ver §14.7).

**Decisión 14.3.2 — nueva función de agregación, `spent_por_categoria_y_moneda_en_rango`, no
reuso directo de la existente.** Mismo idioma de query que `spent_por_categoria_y_moneda`
(`budget_alerts.py:34-64`) pero parametrizada por `start`/`end` arbitrarios y **sin** filtrar por
`category_ids` conocidos de antemano (hallazgo 4) — el resumen semanal no sabe de antemano qué
categorías tuvieron gasto:

```python
# backend/app/core/weekly_summary.py
def spent_por_categoria_y_moneda_en_rango(
    db: Session, user_id: int, start: datetime, end: datetime
) -> list[tuple[int, str, Decimal]]:
    """(category_id, currency, spent) para todo el gasto del usuario en [start, end].
    Mismo idioma de query que `budget_alerts.spent_por_categoria_y_moneda` (agrupar por
    category_id + currency, filtrar type == "expense") pero sin restringir category_ids
    de antemano — el resumen semanal no sabe qué categorías tuvieron gasto hasta calcularlo."""
    rows = (
        db.query(
            models.Transaction.category_id,
            models.Transaction.currency,
            func.sum(models.Transaction.amount).label("spent"),
        )
        .filter(
            models.Transaction.user_id == user_id,
            models.Transaction.type == "expense",
            models.Transaction.date >= start,
            models.Transaction.date <= end,
        )
        .group_by(models.Transaction.category_id, models.Transaction.currency)
        .all()
    )
    return [(r.category_id, r.currency, r.spent) for r in rows]
```

**Decisión 14.3.3 — "total gastado" y "categoría principal" solo en `preferred_currency` del
usuario; otras monedas se ignoran en el resumen (no se convierten, no se listan aparte).** Mismo
criterio que `cashflow-series`/`category-distribution`
(`dashboard.py:29,184`, default `current_user.preferred_currency or "COP"`). No hay tasas de
cambio en el proyecto (`ROADMAP.md`, backlog "Multi-moneda ampliado" queda en prioridad Baja) y el
espacio de un push/bandeja no permite un desglose multi-moneda legible de todos modos. Un usuario
cuyo gasto de la semana fue enteramente en una moneda distinta a su preferida recibe un resumen en
$0 — comportamiento aceptado, coherente con el resto del dashboard (que tiene el mismo límite).

**Decisión 14.3.4 — se envía siempre, incluso con `spent == 0` en la moneda preferida.** El
objetivo explícito del ROADMAP es "re-engagement pasivo" — omitir el envío justo para el usuario
que no registró nada esa semana es omitirlo exactamente para la población que la feature existe
para recuperar. El mensaje para el caso $0 usa una plantilla distinta ("Esta semana no registraste
gastos — ¿todo tranquilo?") en vez de forzar el mismo formato con un total de $0.

**Decisión 14.3.5 — comparación con la semana anterior: mismo cálculo aplicado al rango `[start -
7d, end - 7d]`, expresado como delta porcentual, sin manejo especial de "no había datos la semana
pasada" más allá de tratar esa base como 0** (evita división por cero: si el gasto de la semana
anterior fue 0 y esta semana hay gasto, se reporta como "gasto nuevo" en el texto, no como "+∞%").

```python
def build_weekly_summary(db: Session, user: models.User, reference_date: datetime) -> dict:
    """Calcula el resumen de la semana ISO que contiene `reference_date` (lunes-domingo,
    America/Bogota — Decisión 14.3.1). Pura función de cálculo, sin efectos secundarios —
    `run_weekly_summary_for_user` (más abajo) es quien persiste y envía."""
    tz = ZoneInfo("America/Bogota")
    start, end = _limites_semana(reference_date, tz)              # lunes 00:00 - domingo 23:59:59
    start_prev, end_prev = _limites_semana(reference_date - timedelta(days=7), tz)

    moneda = user.preferred_currency or "COP"
    filas = spent_por_categoria_y_moneda_en_rango(db, user.id, start, end)
    filas_prev = spent_por_categoria_y_moneda_en_rango(db, user.id, start_prev, end_prev)

    total = sum((s for _, c, s in filas if c == moneda), Decimal("0.00"))
    total_prev = sum((s for _, c, s in filas_prev if c == moneda), Decimal("0.00"))

    categoria_principal_id = max(
        ((cat_id, s) for cat_id, c, s in filas if c == moneda), key=lambda x: x[1], default=(None, None)
    )[0]

    return {
        "period_key": start.strftime("%G-W%V"),   # semana ISO, p. ej. "2026-W37"
        "total": total,
        "currency": moneda,
        "categoria_principal_id": categoria_principal_id,
        "delta_pct": None if total_prev == 0 else float((total - total_prev) / total_prev * 100),
    }
```

*(`_limites_semana` es un helper trivial de `isocalendar()` + `timedelta` — se omite el cuerpo
aquí por brevedad, no representa ninguna decisión de diseño.)*

**Título/cuerpo del mensaje**, siguiendo el mismo estilo que `budget_alerts._crear_notificacion`
(texto en español, con cifras formateadas):

```python
def run_weekly_summary_for_user(db: Session, user: models.User, reference_date: datetime) -> None:
    resumen = build_weekly_summary(db, user, reference_date)
    if resumen["total"] == 0:
        title = "Tu resumen semanal"
        body = "Esta semana no registraste gastos — ¿todo tranquilo?"
    else:
        categoria = ...  # nombre de resumen["categoria_principal_id"], "sin categoría" si None
        delta_txt = "" if resumen["delta_pct"] is None else f" ({resumen['delta_pct']:+.0f}% vs. semana pasada)"
        title = "Tu resumen semanal"
        body = f"Gastaste {resumen['total']:,.2f} {resumen['currency']} — el mayor gasto fue en {categoria}{delta_txt}."

    crear_y_enviar_notificacion(
        db, user_id=user.id, type="weekly_summary", title=title, body=body,
        period_key=resumen["period_key"],
    )
```

La unicidad de la Decisión 14.1.2 hace que una segunda invocación para el mismo usuario/semana
falle con `IntegrityError` en el `db.commit()` de `crear_y_enviar_notificacion` — se atrapa en el
loop del scheduler (§14.4.3), no aquí, siguiendo el mismo criterio que
`ensure_recurring_budgets_for_period` (hallazgo 12).

---

## 14.4 Scheduler

**Decisión 14.4.1 — APScheduler `BackgroundScheduler` in-process, no `AsyncIOScheduler` ni cron
externo.** `BackgroundScheduler` porque el job necesita una sesión síncrona de SQLAlchemy
(`SessionLocal()`, mismo patrón que `seed_default_categories()`) y no hay razón para acoplarlo al
loop de asyncio de FastAPI. Se descarta cron externo (crontab del host, o un segundo servicio en
`docker-compose.yml` que le pega a un endpoint interno): agregaría un componente desplegable más +
un endpoint "disparar resumen semanal" que habría que proteger con un secreto interno, para una
infraestructura que hoy es "un contenedor, un `docker compose up`" — el mismo antipatrón que el
ROADMAP ya evita en otros lados (CI/CD, rate limiting distribuido). Con un solo worker (hallazgo
6), `BackgroundScheduler` no tiene problema de coordinación entre procesos porque no hay más de un
proceso — mismo razonamiento que ya usó Fase 7 para diferir la versión distribuida de
`slowapi`.

```python
# backend/app/main.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.weekly_summary import run_weekly_summary_job

scheduler = BackgroundScheduler()


@app.on_event("startup")
def initialize_shared_data():
    seed_default_categories()
    scheduler.add_job(
        run_weekly_summary_job,
        trigger=CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="America/Bogota"),
        id="weekly_summary",
        replace_existing=True,
    )
    scheduler.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown(wait=False)
```

**Decisión 14.4.2 — agregar `@app.on_event("shutdown")`, que hoy no existe en absoluto en el
proyecto (hallazgo 5).** Sin él, cada reload de `docker-compose.dev.yml --reload` deja un hilo de
`BackgroundScheduler` huérfano — barato de evitar, y es la primera vez que el proyecto necesita
un hook de shutdown, así que se agrega ahora en vez de quedar como deuda.

**Decisión 14.4.3 — el job corre una query batch (no un loop de N+1) y hace `commit` por usuario
dentro del loop, no una transacción para todos.** Una sola query trae a todos los usuarios
elegibles de una vez:

```python
# backend/app/core/weekly_summary.py
def run_weekly_summary_job() -> None:
    """Entry point del scheduler — abre su propia sesión (no hay request HTTP del que
    tomarla, a diferencia del motor de alertas de Fase 13)."""
    db = SessionLocal()
    try:
        usuarios = (
            db.query(models.User)
            .filter(models.User.weekly_summary_enabled.is_(True), models.User.deleted_at.is_(None))
            .all()
        )
        ahora = datetime.now(UTC)
        for user in usuarios:
            try:
                run_weekly_summary_for_user(db, user, ahora)
            except IntegrityError:
                db.rollback()  # ya se envió esta semana para este usuario (Decisión 14.1.2) — no es un error
            except Exception:
                db.rollback()
                logger.exception("Error al generar el resumen semanal del usuario %s", user.id)
    finally:
        db.close()
```

No es optimización prematura: es la misma cantidad de código estructurado como una query en vez de
N, y evita construir el hábito incorrecto desde el principio (mismo criterio que ya usan
`spent_por_categoria_y_moneda` y las queries de `dashboard.py`, ninguna hace loops por fila para
traer datos). El `commit` por usuario (dentro de `crear_y_enviar_notificacion`) es igual de
importante: un fallo a mitad del loop no debe revertir ni bloquear a los usuarios ya procesados —
mismo criterio que Decisión 13.3.4 del motor de alertas. Explícitamente fuera de alcance de Fase
14: cola de trabajos/worker pool para el fan-out — solo si el volumen de usuarios lo justifica
(ver §14.7).

**Decisión 14.4.4 (riesgo aceptado, diferido a propósito) — sin catch-up si se pierde la corrida
exacta del lunes.** El job vive en memoria (`MemoryJobStore` por defecto de APScheduler); un
restart del contenedor exactamente en la ventana de disparo pierde esa corrida, sin reintento
automático ni "detectar al arrancar que se saltó un lunes". Para un resumen semanal (no crítico,
no financiero) esto es aceptable — construir lógica de catch-up sería complejidad
desproporcionada para una feature de re-engagement. `requirements.txt` gana `APScheduler`.

---

## 14.5 Envío vía push + entrada en la bandeja in-app

No es un ítem de trabajo aparte — ya lo resuelven §14.2 (extracción del helper compartido) y
§14.3 (`run_weekly_summary_for_user` llama a `crear_y_enviar_notificacion`). Se documenta aquí
solo para dejar explícito lo que el ROADMAP lista como ítem propio pero que este análisis
disolvió en los anteriores (ver "Orden de dependencia real").

**Decisión 14.5.1 — la bandeja in-app siempre se puebla; el push es best-effort sobre la misma
fila, exactamente como en Fase 13.** Hereda la limitación ya documentada en el ROADMAP de Fase 13:
push solo funciona si el usuario instaló la PWA en su pantalla de inicio (Safari 16.4+) — un
usuario que solo usa la web en navegador no recibe nada por push. `crear_y_enviar_notificacion`
(Decisión 14.2.1) ya garantiza este orden (`db.add` + `db.commit` antes de intentar
`enviar_push`), así que no hace falta ninguna decisión nueva aquí — es una herencia directa de
13.2.3.

**Frontend:** ninguna pieza nueva. `NotificationBell.tsx` (Fase 13) ya renderiza cualquier
`NotificationResponse` genérica — un aviso `type="weekly_summary"` aparece en la bandeja sin
cambios en el componente. Único ajuste opcional: si se quiere un ícono distinto por `type` en la
lista (p. ej. un ícono de calendario para `weekly_summary` vs. uno de alerta para
`budget_threshold_*`), es un `switch` de una línea en `NotificationBell.tsx` — cosmético, no
bloqueante.

---

## 14.6 Preferencia de usuario

**Decisión 14.6.1 — la columna ya se agrega en §14.1.1; aquí solo se expone por API.** Extender
`PreferencesUpdate`/la respuesta de `GET /users/me/preferences`
(`backend/app/api/preferences.py`) — no un endpoint nuevo, mismo criterio que
`preferred_currency/locale/theme`:

```python
# backend/app/schemas/schemas.py
class PreferencesUpdate(BaseModel):
    preferred_currency: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    weekly_summary_enabled: bool | None = None  # Fase 14
```

```python
# backend/app/api/preferences.py — get_preferences y update_preferences agregan el campo
# al dict de respuesta, mismo patrón que los tres existentes (líneas 12-17 y 27-31)
```

**Decisión 14.6.2 — el costo real de este ítem no es el campo backend (barato), es que no existe
ninguna superficie de "Ajustes" en el frontend hoy (hallazgo 9).** El ROADMAP dimensiona el ítem
completo en 4h; el campo + endpoint son, en efecto, ~1h de trabajo. Falta construir la primera
página de ajustes del producto — no cablear un checkbox a algo que ya existe. Se propone:

- **Archivo nuevo:** `frontend/app/(dashboard)/settings/page.tsx` — página simple, un único
  toggle "Recibir resumen semanal" (`Switch`/checkbox existente del sistema de componentes, ver
  `frontend/docs/COMPONENTS_GUIDE.md`), que lee/escribe `weekly_summary_enabled` vía
  `useUserPreferences` (extender el hook existente,
  `frontend/lib/hooks/useUserPreferences.ts`, con el campo nuevo — mismo patrón que
  `preferred_theme`).
- **Entrada de navegación:** un ítem "Ajustes" en el bloque secundario del sidebar
  (`frontend/components/Sidebar.tsx`), agrupado junto a Analítica/Cuentas/Categorías
  (mismo criterio de reagrupación que Fase 11 §11.7) — no en el bloque primario, es una página de
  configuración infrecuente, no una del flujo diario.
- Alcance deliberadamente mínimo: **un solo control.** No es el lugar para anticipar futuros
  ajustes de cuenta (cambio de contraseña, email, etc.) que no pide esta fase — evitar inflar el
  alcance de "la primera página de ajustes" más allá de lo que Fase 14 necesita.

**Decisión 14.6.3 — sin endpoint de "preview" del resumen ni botón "enviar ahora" en esta
página.** El ROADMAP no lo pide y agregaría una superficie de testing manual en producción
(dispararía un push real) sin necesidad — para probar el cálculo en desarrollo alcanza con invocar
`run_weekly_summary_for_user` directamente desde un shell o un test, no desde la UI.

---

## 14.7 Documentación y deuda diferida a propósito

**Cerrar ahora, no diferir:** `backend/docs/BUSINESS_RULES.md` gana una sección "Notificaciones"
breve (tipos de aviso, regla de idempotencia por `(budget_id, type)` y por
`(user_id, type, period_key)`, y que el push es best-effort sobre la bandeja) — es la segunda fase
consecutiva que toca este sistema sin que exista la sección; posponerla otra vez la vuelve deuda
estructural. `backend/docs/API_REFERENCE.md` y `frontend/docs/API_CONTRACT.md` deben reflejar el
`PreferencesUpdate` extendido (CLAUDE.md: "si cambia un contrato de API compartido, actualizar
ambos docs en el mismo cambio") — no hay endpoints nuevos si se reusa `PATCH
/users/me/preferences`, pero el shape del schema cambia y cuenta como contrato compartido.

**Diferido a propósito** (mismo patrón que rate limiting distribuido / limpieza de
`idempotency_keys` en fases anteriores — documentado, con criterio explícito de cuándo revisar):

| Deuda | Razón para diferir | Revisar cuando |
|---|---|---|
| Scheduler multi-worker/multi-réplica | `BackgroundScheduler` in-process asume un solo proceso (hallazgo 6) | El deployment pase a `--workers > 1` o más de una réplica — mismo trigger que Fase 7 §2.6.1 |
| Timezone por usuario | No hay infraestructura de timezone en ningún nivel (hallazgo 7); mercado actual es LATAM/español | El proyecto salga de LATAM o pida soporte multi-zona explícitamente |
| Corrida perdida por restart en el instante exacto del disparo | Sin catch-up (Decisión 14.4.4); resumen no crítico, no financiero | Si en producción real se observa que restarts coinciden con la ventana del lunes con frecuencia relevante |
| Cola de trabajos / worker pool para el fan-out del job | Volumen actual de usuarios no lo justifica (Decisión 14.4.3) | El loop de `run_weekly_summary_job` se vuelva medible como lento en producción |
| Botón de preview/envío manual del resumen | No pedido por el ROADMAP; agregaría superficie de testing en producción (Decisión 14.6.3) | Si soporte/QA lo pide explícitamente para depurar un caso de usuario puntual |

---

## Testing

**Decisión (testing) — primer uso real de `freezegun` fuera de auth; primer módulo de `app/core/`
probado por llamada directa, no vía `TestClient`.** El cálculo (`build_weekly_summary`,
`run_weekly_summary_for_user`) se prueba llamándolo directamente con una sesión de test y
`freeze_time` fijando `reference_date`, no a través de un endpoint HTTP — no existe ningún
endpoint que dispare este cálculo, lo dispara el scheduler. Esto se aparta de la convención
establecida en `backend/tests/` (`conftest.py` está diseñado alrededor de `TestClient` + fixtures
de registro/login vía HTTP) — se documenta como excepción justificada, no como descuido, mismo
criterio que ya usó Fase 13 para separar el testing del motor de alertas del resto de la suite.

**`backend/tests/test_weekly_summary.py` (nuevo), casos mínimos:**
- Un usuario con gasto en `preferred_currency` recibe el total y la categoría principal correctos
  (`freeze_time` fijando un lunes conocido, transacciones sembradas en la semana anterior).
- Un usuario sin ningún gasto en la semana recibe el mensaje de "sin gastos" (Decisión 14.3.4), no
  se omite.
- Gasto en una moneda distinta a `preferred_currency` no se cuenta en el total (Decisión 14.3.3).
- Comparación con la semana anterior: delta correcto, y `delta_pct is None` cuando la semana
  anterior tuvo `total_prev == 0` (Decisión 14.3.5, evita división por cero).
- Invocar `run_weekly_summary_for_user` dos veces para el mismo usuario/semana lanza
  `IntegrityError` en la segunda (Decisión 14.1.2) — verifica la unicidad a nivel de DB, no solo
  que el código "decida no enviar".
- `weekly_summary_enabled=False` — el usuario queda fuera del batch de `run_weekly_summary_job`
  (query, no lógica de cálculo).

**No recomendado:** probar que APScheduler realmente dispara en un lunes real (bajo valor, alta
fragilidad) — basta con inspeccionar `scheduler.get_jobs()[0].trigger` para confirmar que el
`CronTrigger` quedó configurado como se espera, sin ejecutar el job real en el test.

---

## Resumen de estimación de horas

| Ítem | ROADMAP | Ajustado | Motivo del ajuste |
|---|---|---|---|
| 14.1 Modelo de datos + migración | *(embebido en "scheduler", ver abajo)* | 3h | Dos columnas + índice único parcial nuevo — revisar a mano el autogenerate del índice (hallazgo 2) |
| 14.2 Refactor `budget_alerts.py` → módulo compartido | *(no dimensionado por el ROADMAP)* | 2h | Extracción mecánica, sin lógica nueva, pero toca un archivo con tests existentes que hay que ajustar |
| 14.3 Cálculo del resumen semanal | 1d (8h) | 1.5d (12h) | Query nueva (no reuso directo, hallazgo 4), decisión de $0/multi-moneda, comparación con semana anterior, plantillas de mensaje |
| 14.4 Scheduler | 1d (8h) | 1d (8h) | Sin cambio de alcance — agregar `shutdown` hook (hallazgo 5) compensa con simplificar la decisión (in-process, sin cron externo) |
| 14.5 Envío (push + bandeja) | 1d (8h) | 0h | Se disuelve en 14.2 + 14.3 — no hay trabajo adicional (ver "Orden de dependencia real") |
| 14.6 Preferencia de usuario | 4h | 1.5d (12h) | El campo/endpoint son ~1h; el resto es la primera página de Ajustes del frontend, que no existe hoy (hallazgo 9) |
| Testing (`test_weekly_summary.py`) | *(no dimensionado aparte)* | 4h | Primer uso de `freezegun` fuera de auth + primer módulo probado sin `TestClient` (excepción a la convención de la suite) |
| Documentación (`BUSINESS_RULES.md` + `API_REFERENCE.md`/`API_CONTRACT.md`) | *(no dimensionado aparte)* | 2h | Cerrar deuda preexistente de Fase 13 en vez de diferirla otra vez (§14.7) |
| **Total** | **~3.5d (28h)** | **~5.9d (47h)** | |

El mayor ajuste al alza es §14.6 (preferencia de usuario): no es la columna ni el endpoint lo que
falta, es que no existe ningún lugar en la UI donde vivir el ajuste — ese gap no está dimensionado
en ningún ítem del ROADMAP ni tiene precedente en fases anteriores. El segundo ajuste relevante es
que "Envío" (1d en el ROADMAP) no es trabajo independiente: se disuelve por completo en el
refactor de 14.2 y el cálculo de 14.3, así que su costo real ya está contado ahí, no aparte.

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 14.1 Modelo de datos | `backend/app/models/models.py` (`User.weekly_summary_enabled`, `Notification.period_key` + índice), `backend/app/schemas/schemas.py` (`NotificationType.weekly_summary`, `NotificationResponse.period_key`), migración Alembic nueva |
| 14.2 Refactor compartido | `backend/app/core/notification_dispatch.py` (nuevo), `backend/app/core/budget_alerts.py` (import en vez de definición propia), `backend/tests/test_budget_alerts.py` (ajustar mocks si aplica) |
| 14.3 Cálculo | `backend/app/core/weekly_summary.py` (nuevo), `backend/tests/test_weekly_summary.py` (nuevo) |
| 14.4 Scheduler | `backend/requirements.txt` (`APScheduler`), `backend/app/main.py` (`startup`/`shutdown`, `add_job`) |
| 14.5 Envío | ninguno adicional — cubierto por 14.2/14.3 |
| 14.6 Preferencia de usuario | `backend/app/schemas/schemas.py` (`PreferencesUpdate.weekly_summary_enabled`), `backend/app/api/preferences.py`, `frontend/lib/hooks/useUserPreferences.ts`, `frontend/app/(dashboard)/settings/page.tsx` (nuevo), `frontend/components/Sidebar.tsx` (entrada de navegación) |
| Cruzando toda la fase | `backend/docs/BUSINESS_RULES.md` (sección Notificaciones, nueva), `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (`PreferencesUpdate` extendido) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 14" de `docs/ROADMAP.md`, con archivos, esquemas de datos y decisiones de diseño
concretas para que backend-engineer/frontend-engineer puedan partir directamente de aquí. A
diferencia de Fase 13 (donde nada de lo pedido existía), Fase 14 encuentra un terreno parcialmente
preparado a propósito: el modelo `Notification` ya anticipaba esta fase en sus comentarios
(hallazgo 1), pero esa preparación cubre solo *dónde* vive el aviso, no *cómo se evita duplicarlo*
bajo un job que itera todos los usuarios fuera de un request HTTP (hallazgo 2) — ese es el gap que
más decisiones de este documento resuelve (§14.1.2, §14.4.3, §14.4.4). El segundo hallazgo con más
impacto práctico es que el ítem "Preferencia de usuario" del ROADMAP, dimensionado en 4h, esconde
la construcción de la primera superficie de ajustes del producto (hallazgo 9, Decisión 14.6.2) —
sin frontend previo del que partir, a diferencia de todos los demás ítems de esta fase. Todos los
hallazgos fueron verificados contra el código real de `backend/` (y la ausencia confirmada en
`frontend/`) el 2026-09-06, con el análisis arquitectónico de scheduler/idempotencia/timezone hecho
por el agente `software-architect` antes de redactar este documento. Ningún archivo del repositorio
fuera de `docs/specs/fase_14_spec.md` fue modificado al producirlo.
