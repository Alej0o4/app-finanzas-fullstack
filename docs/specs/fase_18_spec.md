# Spec — Fase 18: Categorías personalizables

> Plan de implementación detallado para los 4 ítems de Fase 18 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 18 — Categorías
> personalizables", decidida en sesión de grilling del 2026-09-12). Este documento no cambia
> el alcance ahí definido — lo desglosa en tareas ejecutables, con esquemas de datos,
> endpoints y componentes concretos, separados en Backend/Frontend por ítem para que
> `backend-engineer`/`frontend-engineer` puedan tomar cada mitad en paralelo.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de
> `docs/specs/fase_18_spec.md` fue modificado al producir este documento. Los hallazgos de
> exploración de código fueron verificados directamente contra `backend/` y `frontend/` el
> 2026-09-12 (lectura completa de `categories.py`, `models.py`, `schemas.py`, `main.py`,
> `users.py`, `transactions.py` §16.2, `BUSINESS_RULES.md`, `categories/page.tsx`,
> `TransactionCaptureForm.tsx`, `OnboardingIncomeStep.tsx`, `capture/page.tsx`,
> `register/page.tsx`, `budgets/page.tsx`, `transactions/page.tsx`, `queryKeys.ts`,
> `types/api.ts`, `CategoryIcon.tsx`), no inferidos del texto del ROADMAP. Las siete preguntas
> de arquitectura sin respuesta única (Q1–Q7 abajo) fueron evaluadas por el agente
> `software-architect` a partir de ese mismo código, con cita de línea exacta, el 2026-09-12.

Estado del repo al momento de escribir esto: Fases 7–17 están completas. Fase 18 es la segunda
fase post-MVP decidida en la sesión de grilling del 2026-09-12 (junto con Fase 17 y 19) — sin
usuarios reales todavía, por lo que ningún cambio de esquema necesita ruta de compatibilidad ni
backfill (`docs/ROADMAP.md:630-631`).

---

## Hallazgos de exploración que precisan el ROADMAP

1. **`Category` no tiene ninguna noción de visibilidad por usuario hoy.**
   `backend/app/models/models.py:63-74`: `id, name, type, icon, updated_at, user_id
   (nullable)`. `user_id IS NULL` = categoría de sistema, compartida por todos los usuarios,
   inmutable vía API (`categories.py:63-64`, `83-84`). No existe ninguna tabla de overlay
   por usuario en todo el esquema — cada relación de `User` hoy es una FK directa
   (`accounts`, `categories`, `transactions`, `budgets`), nunca una tabla puente ni una
   columna JSON.

2. **El CRUD de categorías propias ya existe completo y probado desde antes de Fase 11** —
   `backend/app/api/categories.py` (102 líneas): `POST /`, `GET /` (sistema + propias),
   `GET /{id}`, `PUT /{id}` (403 si es de sistema), `DELETE /{id}` (403 si es de sistema, 400
   si tiene transacciones o presupuestos activos, si no borrado lógico). Fase 11 §11.6 lo dejó
   oculto detrás de `CUSTOM_CATEGORY_EDITING_ENABLED = false`
   (`frontend/app/(dashboard)/categories/page.tsx:24`) a propósito, documentando
   explícitamente "el código ya existe, solo queda oculto" — este ítem es el que lo reactiva.

3. **Cuatro consumidores de `GET categories/` en el frontend, todos compartiendo hoy
   `queryKeys.categories.all()`** — confirmado línea por línea:
   - `TransactionCaptureForm.tsx:57-65` — grid de categorías al crear una transacción,
     filtrado por `type` en cliente. **Es el único consumidor que el ROADMAP quiere que
     "ocultar" afecte** (ítem 3, explícito: "Ocultar solo afecta el selector al crear una
     transacción nueva").
   - `transactions/page.tsx:182-184` — filtro de categoría (línea ~414) y el selector de
     categoría del modal de edición manual (línea ~605): ambos deben seguir mostrando
     **todas** las categorías, incluidas las ocultas — una transacción histórica puede ya
     estar categorizada bajo algo que el usuario ocultó después, y debe seguir siendo
     filtrable/editable.
   - `budgets/page.tsx:58-71` (`expenseCategories`) — selector al crear/editar un
     presupuesto. El ROADMAP no lo menciona; se mantiene sin filtrar (ver Decisión Q6/Q4:
     ocultar es una preferencia del selector de captura, no una restricción de qué se puede
     presupuestar).
   - `OnboardingIncomeStep.tsx:27-30,41-43` — busca la categoría de sistema "Salario" por
     nombre para sembrar el ingreso declarado del onboarding. Debe seguir encontrándola sin
     importar su estado de visibilidad.

4. **El registro (`register/page.tsx`, 195 líneas) es deliberadamente mínimo — nombre, email,
   contraseña, confirmación — y no toca categorías hoy.** La Decisión 15.0.3
   (`docs/specs/fase_15_spec.md`) estableció auto-login post-registro precisamente para evitar
   fricción; el wizard de onboarding (`app/capture/page.tsx:16-46`, `?onboarding=1`) es el
   lugar ya establecido para pedir algo "justo después del registro" sin tocar el formulario
   de registro mismo — y solo se usa hoy para datos que la app genuinamente no puede
   default-ear (`OnboardingIncomeStep`, el ingreso mensual, que alimenta directamente el
   dato principal del dashboard de flujo).

5. **`CategoryIcon.tsx` resuelve cualquier export nombrado de `lucide-react` dinámicamente en
   tiempo de render** (`icon` es un string libre, sin whitelist en backend ni frontend) — agregar
   categorías nuevas con íconos nuevos no requiere tocar ningún mapeo, solo elegir un nombre de
   ícono real de la librería.

6. **`seed_default_categories()` (`main.py:68-106`) corre en cada arranque y ya soporta altas
   puras sin migración** — upsert por `(name, type)` sobre filas `user_id IS NULL`. Mismo
   mecanismo verificado y usado en Fase 8 §4 para ampliar el pool de 7 a 11 categorías sin
   ninguna migración de Alembic (`docs/specs/fase_08_spec.md` sección 4).

7. **No existe `backend/tests/test_categories.py`** — el CRUD de categorías no tiene suite
   dedicada hoy (se ejerce indirectamente desde `test_transactions.py`/`test_budgets.py` vía
   fixtures). Fase 18 es quien lo crea, dado que introduce comportamiento nuevo
   (visibilidad) que si no se prueba explícitamente puede regresar en silencio.

---

## Decisiones de arquitectura (Q1–Q7, evaluadas por `software-architect` el 2026-09-12)

Estas siete preguntas no tenían una respuesta única derivable solo del texto del ROADMAP —
requerían leer el código real y, en el caso de Q2/Q3, corregir una lectura literal del
encabezado del ítem 2 contra una decisión ya tomada en una fase anterior (mismo criterio que
Fase 10 §10.1.4, Fase 11 §11.6/§11.7 y Fase 17 P1/P3 ya aplicaron).

**Q1 — Dónde vive "oculta para mí": una tabla puente nueva, `hidden_categories`, sin
soft-delete.** Una columna en `Category` queda descartada: las filas `user_id IS NULL` son
genuinamente compartidas (Hallazgo 1), así que una columna ahí filtraría para todos los
usuarios a la vez, no para uno. Se descarta también un array JSON en `User` por ser la primera
tabla de este esquema en romper el patrón "cada relación por usuario es una FK en su propia
tabla" (`accounts`, `categories`, `transactions`, `budgets`) sin ninguna ganancia a cambio (sin
integridad relacional, no filtrable/joinable en SQL).

```python
# backend/app/models/models.py — nueva clase, no extiende SoftDeleteMixin a propósito:
# la existencia de la fila ES la señal; no hay un tercer estado que un booleano interno
# necesite representar, y "des-ocultar" es un DELETE real, no un borrado lógico — la fila
# no tiene historia que valga la pena auditar y es trivialmente reconstruible.
class HiddenCategory(Base):
    __tablename__ = "hidden_categories"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)
    hidden_at = Column(DateTime(timezone=True), server_default=func.now())
```

Sin `ondelete=` en ninguna FK — mismo patrón que el resto de `models.py`
(`Budget.user_id`/`category_id`, `Transaction.account_id`/`category_id`, ninguna especifica
`ondelete`). Es seguro porque ni `User` ni `Category` tienen una ruta de borrado físico —
ambas usan `SoftDeleteMixin`; una fila huérfana de `hidden_categories` nunca ocurre hoy.

**Q2 — Un solo mecanismo: el pre-marcado del registro (ítem 2) ES pre-sembrar
`hidden_categories`.** El propio texto del ítem 2 ya lo dice de forma equivalente: "el resto
queda visible para agregar cuando el usuario quiera" (`ROADMAP.md:637-639`) es semánticamente
lo mismo que "oculto hasta que se des-oculte". Tratarlos como dos conceptos separados
obligaría a reconciliar deriva entre ambos (¿qué pasa si el usuario des-oculta una categoría
que nunca "seleccionó" al registrarse?) — con una sola tabla, "agregarla" es solo un `DELETE`,
sin distinción necesaria.

```python
# backend/app/main.py, junto a DEFAULT_CATEGORIES — set base pre-marcado del registro.
# Incluye Salario/Otros ingresos (no nombrados en el ROADMAP, que solo da ejemplos de gasto)
# porque dejar el lado de ingreso vacío por defecto sería peor primera experiencia que la
# que el ítem 2 busca — es una interpretación, no una cita literal del ROADMAP.
BASE_REGISTRATION_CATEGORY_NAMES = {
    "Mercado", "Transporte", "Vivienda", "Salud", "Entretenimiento", "Otro",
    "Salario", "Otros ingresos",
}
```

**Q3 — El ítem 2 no tiene ninguna pantalla nueva; es un default de aprovisionamiento
silencioso.** Corrige la lectura literal del encabezado "Selección de categorías en el
registro" (que sugiere una pantalla), con el mismo criterio que ya aplicaron Fase 10 §10.1.4 y
Fase 15 §15.0.3: el wizard de onboarding se reserva para datos que la app no puede default-ear
razonablemente (el ingreso mensual no tiene default sano y alimenta el dato principal del
dashboard). Las preferencias de categoría sí tienen un default razonable (Q2) y equivocarse en
él no cuesta nada — siempre se puede corregir después vía el ítem 3. `register/page.tsx` y
`app/capture/page.tsx` **no se tocan** por este ítem. El "agregar cuando el usuario quiera" del
ROADMAP ocurre en `/categories` (extendida por el ítem 3, más abajo), no durante el registro.

**Q4 — Superficie de API: `is_hidden` en cada fila de `CategoryResponse`, sin query param, sin
fragmentar el caché; dos endpoints nuevos de toggle.** Se evaluaron dos opciones: (A) un query
param (`visible_only`) en `GET /categories/`, usado solo por `TransactionCaptureForm`; o (B)
devolver siempre un `is_hidden: bool` computado y dejar que cada consumidor decida. **Se
decide (B)**: la opción A forzaría exactamente la fragmentación de caché que
`frontend/docs/STATE_AND_FETCHING.md` pide evitar — los 5 consumidores de `GET categories/`
(Hallazgo 3, más el propio editor de `/categories`) comparten hoy una sola
`queryKeys.categories.all()`; un segundo round-trip para filtrar ~15-20 filas no se justifica.
`TransactionCaptureForm` ya filtra en cliente por `type` (`TransactionCaptureForm.tsx:62-65`)
— agregar `&& !c.is_hidden` ahí es un cambio de una línea, sin superficie de caché nueva.

```python
# backend/app/schemas/schemas.py
class CategoryResponse(CategoryBase):
    id: int
    user_id: int | None = None
    icon: str | None = None
    is_hidden: bool = False  # 🆕 Fase 18 — computado por usuario, no persistido en Category

    class Config:
        from_attributes = True
```

Endpoints nuevos, mismo patrón "POST crea una fila marcador, DELETE la quita" que ya existe en
este código para `push_subscriptions` (`api/push.py:36` `POST /subscribe`, `:66`
`DELETE /subscribe`) — no es un patrón nuevo:

```python
@router.post("/{category_id}/hide", status_code=204)
def ocultar_categoria(category_id, db, current_user): ...  # idempotente

@router.delete("/{category_id}/hide", status_code=204)
def mostrar_categoria(category_id, db, current_user): ...  # idempotente
```

**Refinamiento sobre el borrador del arquitecto (encontrado al ensamblar esta spec):** el
sketch de `is_hidden: bool = False` como default de Pydantic solo es correcto para
`GET /categories/` (Decisión 18.3, que construye `CategoryResponse` a mano por fila). Los
otros tres handlers que devuelven una sola categoría vía `response_model=CategoryResponse` con
serialización automática (`crear_categoria`, `obtener_categoria`, `actualizar_categoria`) le
pasan un objeto `models.Category` que no tiene atributo `is_hidden` — Pydantic v2 usará el
`default=False` silenciosamente vía `getattr(obj, "is_hidden", <default>)`, lo cual es
**incorrecto** para `obtener_categoria`/`actualizar_categoria` si esa categoría puntual ya
tiene una fila en `hidden_categories` (ej. el usuario edita el nombre de una categoría propia
que ya había ocultado — la respuesta del `PUT` reportaría `is_hidden: false` aunque siga
oculta). Se corrige en la Decisión 18.3 abajo computando `is_hidden` explícitamente en los tres
handlers, no solo en el de listado.

**Q5 — Lista final de categorías nuevas (todas `type=expense`), íconos verificados contra
`lucide-react` instalado:**

| name | type | icon |
|---|---|---|
| Mercado | expense | `ShoppingCart` |
| Pareja | expense | `HeartHandshake` |
| Regalos | expense | `Gift` |
| Restaurantes | expense | `Utensils` (distinto de `UtensilsCrossed` de "Alimentación") |
| Gastos hormiga | expense | `Coins` |
| Uber | expense | `CarTaxiFront` |
| Carro | expense | `Fuel` |
| Transporte público | expense | `Bus` |

Ningún nombre choca con uno existente bajo la comparación case/acento-insensible de
`_normalizar_nombre_categoria` (`transactions.py:26-30`) — "Transporte" convive con "Transporte
público"/"Uber"/"Carro" como strings distintos, tal como pide el ROADMAP
(`ROADMAP.md:635-636`). Confirmado zero-migración: son altas puras, no renombres —
`LEGACY_DEFAULT_CATEGORY_NAMES` no necesita entradas nuevas (Hallazgo 6).

**Q6 — "Oculta para mí" aplica tanto a categorías de sistema como propias.** El ROADMAP
restringe qué le hace ocultar a una categoría de sistema ("no modifica ni borra", nada — sigue
compartida e inmutable), no restringe el toggle a solo-sistema. Limitarlo a sistema-solamente
necesitaría una rama de ownership que el diseño de Q1 no tiene naturalmente (`HiddenCategory`
está indexada solo por `category_id`, agnóstica de si `user_id IS NULL`) y socavaría el
propósito del ítem 4: un usuario con CRUD completo puede acumular categorías propias que quiera
sacar del selector de captura sin chocar contra los guardas de borrado
(`categories.py:86-97` — 400 si tiene transacciones o presupuestos activos). Ocultar es
estrictamente más débil que borrar y debe estar disponible sin importar el dueño.

**Q7 — Las categorías ocultas siguen resolviendo por nombre en el endpoint de Fase 16 §16.2
(atajos móviles) — sin ningún cambio en `_resolver_categoria_por_nombre`.** Tres razones: (1)
el ROADMAP es explícito — ocultar "solo afecta el selector al crear una transacción nueva"
(`ROADMAP.md:642-643`), no la resolución por nombre. (2) Los atajos de iOS existen
precisamente para saltarse ese selector visual (Fase 16) — un usuario que oculta "Uber" del
dropdown manual justamente porque siempre lo captura por Shortcut vería su atajo empezar a
fallar con 404 si las ocultas dejaran de resolver, exactamente lo opuesto de lo que busca
ocultar. (3) No hace falta ningún cambio mecánico: el diseño de Q4 devuelve `is_hidden` como
bandera por fila en vez de filtrar la lista en el backend, así que no hay una query "filtrada"
de la que `_resolver_categoria_por_nombre` (`transactions.py:33-70`) pueda desviarse. Se deja
constancia explícita en esta spec para que nadie "corrija" esta función después asumiendo una
simetría que no existe.

---

## Orden de ejecución recomendado

```
1. Backend: ampliar DEFAULT_CATEGORIES (§18.1)
   ── Zero-migración, cero dependencias. Se hace primero porque "Mercado" (nuevo) es parte
      del set base del registro (§18.2) — debe existir como categoría de sistema antes de
      que el registro pueda dejarlo sin ocultar.

2. Backend: modelo HiddenCategory + migración Alembic + CategoryResponse.is_hidden +
   endpoints POST/DELETE /{id}/hide (§18.3, backend)
   ── Fundacional para 18.2 (necesita la tabla para sembrar) y para el frontend de 18.3.

3. Backend: sembrado de HiddenCategory en el registro (§18.2)
   ── Depende de (1) para que "Mercado" exista y de (2) para que exista la tabla.

4. Frontend: is_hidden en types/api.ts, filtro en TransactionCaptureForm, toggle
   mostrar/ocultar en categories/page.tsx (§18.3, frontend)
   ── Depende de (2).

5. Frontend: activar CUSTOM_CATEGORY_EDITING_ENABLED (§18.4)
   ── Independiente de todo lo demás — un solo archivo, ya tocado en (4), así que conviene
      empaquetarlo en el mismo cambio de categories/page.tsx aunque no dependa de nada.
```

Los pasos 1-3 (backend) y 4-5 (frontend) son, en la práctica, dos líneas de trabajo que pueden
asignarse a `backend-engineer`/`frontend-engineer` en paralelo una vez que (2) esté mergeado —
mismo criterio que Fases 11 y 17 ya aplicaron a sus ítems sin dependencia cruzada.

---

## 18.1 Ampliar el pool de categorías default

### Backend

**Archivo a modificar:** `backend/app/main.py`, `DEFAULT_CATEGORIES` (líneas 47-59).

Agregar las 8 entradas de la tabla de la Decisión Q5 al final del arreglo existente. No se
toca `LEGACY_DEFAULT_CATEGORY_NAMES` (Hallazgo 6/Q5 — son altas, no renombres). No se necesita
migración de Alembic — `seed_default_categories()` las insertará en el próximo arranque.

**Testing** (`backend/tests/test_categories.py`, nuevo — ver §18.3 para el resto del archivo):
- `GET /categories/` tras un arranque limpio devuelve las 11 categorías originales más las 8
  nuevas (19 en total), todas con `user_id: null`.
- Ninguna colisiona por nombre+tipo con una existente (case/acento-insensible).

**Criterio de aceptación:**
- Las 8 categorías nuevas aparecen en `GET /categories/` sin migración de Alembic.
- "Transporte" (genérica) sigue existiendo junto a "Transporte público"/"Uber"/"Carro".

---

## 18.2 Selección de categorías en el registro

### Backend

**Decisión 18.2.1 (Q2/Q3) — no hay pantalla nueva; el registro pre-siembra
`hidden_categories` con el complemento del set base.** Ver Decisiones Q2/Q3 arriba.

**Archivos a modificar:**
- `backend/app/main.py`: agregar `BASE_REGISTRATION_CATEGORY_NAMES` (ver Decisión Q2), junto
  a `DEFAULT_CATEGORIES`.
- `backend/app/api/users.py`, `crear_usuario` (línea 43): después de crear la cuenta por
  defecto y antes del `commit()` final que persiste ambos en la misma transacción (mismo
  principio ya documentado ahí — "o existen ambos, o ninguno" — extendido a un tercer
  elemento):

```python
from app.main import BASE_REGISTRATION_CATEGORY_NAMES  # o mover la constante a un módulo
                                                          # compartido si esto genera un
                                                          # import circular con main.py

categorias_sistema = db.query(models.Category).filter(models.Category.user_id.is_(None)).all()
for categoria in categorias_sistema:
    if categoria.name not in BASE_REGISTRATION_CATEGORY_NAMES:
        db.add(models.HiddenCategory(user_id=nuevo_usuario.id, category_id=categoria.id))
```

**Nota de implementación:** `main.py` importa routers (incluido `users.py`) — importar
`BASE_REGISTRATION_CATEGORY_NAMES` desde `main.py` en `users.py` crea un import circular. Mover
la constante a un módulo neutral (ej. `app/core/default_categories.py`, junto con
`DEFAULT_CATEGORIES` y `LEGACY_DEFAULT_CATEGORY_NAMES`, importado tanto por `main.py` como por
`users.py`) antes de escribir el código — decisión de organización, no de diseño, dejada al
`backend-engineer` que implemente esto.

**Testing** (`backend/tests/test_categories.py` o `test_users.py`):
- Registrar un usuario nuevo → `GET /categories/` para ese usuario muestra `is_hidden: true`
  para toda categoría de sistema fuera de `BASE_REGISTRATION_CATEGORY_NAMES`, y
  `is_hidden: false` para las 8 del set base.
- El seed de categorías propias del usuario (`Freelance`, `Servicios Públicos` en
  `backend/app/core/seed.py:142-144`) no se ve afectado — el sembrado de `hidden_categories`
  solo itera categorías de sistema (`user_id IS NULL`), nunca las propias del usuario recién
  creado (que en el momento del registro normal, a diferencia del seed de test, no existen
  todavía).

### Frontend

Ningún cambio (Decisión Q3 — `register/page.tsx` y `app/capture/page.tsx` no se tocan).

**Criterio de aceptación:**
- Un usuario recién registrado ve, en el grid de `TransactionCaptureForm`, únicamente las
  categorías del set base (Mercado, Transporte, Vivienda, Salud, Entretenimiento, Otro,
  Salario, Otros ingresos) hasta que visite `/categories` y des-oculte más.
- El registro no gana ningún campo, paso ni pantalla nueva.

---

## 18.3 Categorías "ocultas para mí"

### Backend

**Decisión 18.3.1 (Q1) — tabla `hidden_categories`.** Ver sketch completo en Decisión Q1.
Migración: `alembic revision --autogenerate -m "fase_18_hidden_categories"` — tabla nueva, sin
backfill (sin usuarios reales, `docs/ROADMAP.md:630-631`). Revisar a mano que autogenerate
detecte correctamente las dos FKs compuestas como primary key (no siempre se infiere limpio,
mismo cuidado que ya documentó Fase 13/14/17 para índices/constraints no triviales).

**Decisión 18.3.2 (Q4) — `CategoryResponse.is_hidden`, computado en los 4 handlers de
`categories.py` que devuelven una categoría, no solo en el de listado** (ver el
"Refinamiento" de la sección de Decisiones arriba — corrige el sketch original del arquitecto,
que solo cubría `GET /`):

```python
# backend/app/api/categories.py

def _esta_oculta(db: Session, user_id: int, category_id: int) -> bool:
    return (
        db.query(models.HiddenCategory)
        .filter_by(user_id=user_id, category_id=category_id)
        .first()
        is not None
    )


@router.post("/", response_model=schemas.CategoryResponse)
def crear_categoria(categoria, db, current_user):
    nueva_categoria = models.Category(**categoria.model_dump(), user_id=current_user.id)
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    return schemas.CategoryResponse(
        id=nueva_categoria.id, name=nueva_categoria.name, type=nueva_categoria.type,
        user_id=nueva_categoria.user_id, icon=nueva_categoria.icon, is_hidden=False,
    )  # una categoría recién creada nunca puede estar ya oculta — sin query extra


@router.get("/", response_model=list[schemas.CategoryResponse])
def obtener_categorias(db, current_user):
    categorias = (
        db.query(models.Category)
        .filter(or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id))
        .all()
    )
    ocultas_ids = {
        row.category_id
        for row in db.query(models.HiddenCategory.category_id)
        .filter(models.HiddenCategory.user_id == current_user.id)
        .all()
    }
    return [
        schemas.CategoryResponse(
            id=c.id, name=c.name, type=c.type, user_id=c.user_id, icon=c.icon,
            is_hidden=c.id in ocultas_ids,
        )
        for c in categorias
    ]


@router.get("/{category_id}", response_model=schemas.CategoryResponse)
def obtener_categoria(category_id, db, current_user):
    categoria = ...  # lookup existente, sin cambios
    return schemas.CategoryResponse(
        id=categoria.id, name=categoria.name, type=categoria.type, user_id=categoria.user_id,
        icon=categoria.icon, is_hidden=_esta_oculta(db, current_user.id, categoria.id),
    )


@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def actualizar_categoria(category_id, categoria_actualizada, db, current_user):
    categoria = ...  # lookup + guardas + mutación existentes, sin cambios
    db.commit()
    db.refresh(categoria)
    return schemas.CategoryResponse(
        id=categoria.id, name=categoria.name, type=categoria.type, user_id=categoria.user_id,
        icon=categoria.icon, is_hidden=_esta_oculta(db, current_user.id, categoria.id),
    )
```

**Decisión 18.3.3 (Q4) — endpoints `POST`/`DELETE /{category_id}/hide`, idempotentes,
misma regla de visibilidad que `GET /categories/` (propia o de sistema):**

```python
@router.post("/{category_id}/hide", status_code=204)
def ocultar_categoria(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    categoria = (
        db.query(models.Category)
        .filter(
            models.Category.id == category_id,
            or_(models.Category.user_id.is_(None), models.Category.user_id == current_user.id),
        )
        .first()
    )
    if not categoria:
        raise HTTPException(status_code=404, detail="La categoría no existe o no tienes permisos.")
    if not _esta_oculta(db, current_user.id, category_id):
        db.add(models.HiddenCategory(user_id=current_user.id, category_id=category_id))
        db.commit()


@router.delete("/{category_id}/hide", status_code=204)
def mostrar_categoria(category_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db.query(models.HiddenCategory).filter_by(
        user_id=current_user.id, category_id=category_id
    ).delete()
    db.commit()
```

Nota de orden de rutas (mismo cuidado que `accounts.py`, ver `docs/specs/fase_17_spec.md`
Hallazgo 8): `/{category_id}/hide` tiene una profundidad de ruta distinta a `/{category_id}` (dos
segmentos contra uno) — sin colisión posible independientemente del orden de declaración.

**Decisión 18.3.4 (Q6) — sin rama de ownership en el toggle.** El único chequeo de permisos es
"propia o de sistema", igual que `GET /categories/` — no existe un chequeo adicional de "solo
sistema" ni "solo propia". Ver Decisión Q6.

**Decisión 18.3.5 (Q7) — `_resolver_categoria_por_nombre` (`transactions.py:33-70`) no se
toca.** Ver Decisión Q7 — constancia explícita para que no se "corrija" en el futuro.

**Testing** (`backend/tests/test_categories.py`, nuevo):
- `POST /categories/{id}/hide` sobre una categoría de sistema: `204`, y `GET /categories/`
  para ese usuario muestra `is_hidden: true` para esa categoría — pero `GET /categories/` para
  **otro** usuario sigue mostrando `is_hidden: false` para la misma fila (la ocultación es
  estrictamente por usuario, no global).
- `POST .../hide` sobre una categoría propia: mismo comportamiento.
- `POST .../hide` dos veces seguidas: `204` ambas veces, una sola fila en `hidden_categories`
  (sin `IntegrityError` por duplicado de la primary key compuesta).
- `DELETE .../hide` sobre una categoría no oculta: `204`, no-op.
- `POST .../hide` sobre una categoría de otro usuario (propia de un tercero): `404`, misma
  regla que `GET /categories/{id}`.
- `PUT /categories/{id}` sobre una categoría propia ya oculta: la respuesta reporta
  `is_hidden: true` (verifica el "Refinamiento" de la Decisión 18.3.2 — antes de este fix
  hubiera reportado `false` por el default de Pydantic).
- `POST /transactions/` con `category: "Uber"` (nombre) sobre una categoría previamente
  ocultada por ese usuario: sigue resolviendo y creando la transacción con éxito (regresión
  directa de la Decisión Q7/18.3.5).

### Frontend

**Decisión 18.3.6 (Q4) — `Category.is_hidden: boolean` en `types/api.ts`, filtro de una línea
en `TransactionCaptureForm`, toggle Eye/EyeOff en `categories/page.tsx` sin gatear tras
`CUSTOM_CATEGORY_EDITING_ENABLED`.**

**Archivos a modificar:**
- `frontend/types/api.ts`: agregar `is_hidden: boolean` a la interfaz `Category`.
- `frontend/components/forms/TransactionCaptureForm.tsx:62-65`:
  ```tsx
  const filteredCategories = useMemo(
    () => categories?.filter((c) => c.type === type && !c.is_hidden) || [],
    [categories, type]
  );
  ```
- `frontend/app/(dashboard)/categories/page.tsx`: nuevo `toggleHiddenMutation` (POST/DELETE a
  `categories/${id}/hide` según el estado actual), invalidando `queryKeys.categories.all()` en
  `onSuccess`. Un ícono `Eye`/`EyeOff` (lucide-react) por tarjeta, **renderizado
  incondicionalmente** — no envuelto en `{CUSTOM_CATEGORY_EDITING_ENABLED && (...)}`, porque
  ocultar no es "editar los campos" de una categoría (ver Decisión Q4, cierre del párrafo).
  Colocar junto al bloque de acciones existente (líneas 214-241) pero fuera de su condición.

**Testing:** sin suite de frontend (igual que fases anteriores). Verificación manual: ocultar
una categoría de sistema en `/categories` la saca del grid de `TransactionCaptureForm` en el
próximo `/capture`; sigue apareciendo (marcada como oculta o sin marca visual especial, a
criterio de implementación) en el filtro y el modal de edición de `/transactions`, y en el
selector de `/budgets`; des-ocultarla la trae de vuelta al grid de captura.

**Criterio de aceptación:**
- `/categories` permite ocultar/mostrar cualquier categoría (sistema o propia) sin afectar a
  otros usuarios.
- El grid de captura de transacción (`TransactionCaptureForm`) deja de mostrar categorías
  ocultas.
- Ningún otro selector de categoría (filtro/edición de transacciones, presupuestos, búsqueda
  por nombre de Fase 16) cambia de comportamiento.

---

## 18.4 Activar el editor de categorías personalizadas

### Frontend

**Archivo a modificar:** `frontend/app/(dashboard)/categories/page.tsx:24`.

```tsx
// Antes:
const CUSTOM_CATEGORY_EDITING_ENABLED = false;
// Después:
const CUSTOM_CATEGORY_EDITING_ENABLED = true;
```

Sin ningún otro cambio — Fase 11 §11.6 dejó todo el código de creación/edición/borrado
intacto y funcional detrás de este flag (`createCategoryMutation`, `updateCategoryMutation`,
`deleteCategoryMutation`, ambos `ModalShell`, el botón "Nueva Categoría", los íconos de
editar/eliminar por tarjeta). Se recomienda empaquetar este cambio en el mismo PR que §18.3
frontend, ya que ambos tocan el mismo archivo.

**Testing:** sin suite de frontend. Verificación manual: crear una categoría propia nueva
(nombre + tipo), editarla, y borrarla (sin transacciones/presupuestos asociados) desde
`/categories`; confirmar que las categorías de sistema siguen sin mostrar los íconos de
editar/eliminar (la condición `!isSystemCategory` en `categories/page.tsx:214` no se toca).

**Criterio de aceptación:**
- El botón "Nueva Categoría" y las acciones de editar/eliminar por tarjeta (solo en categorías
  propias) son visibles y funcionales en `/categories`.
- El backend no cambia — el CRUD ya estaba completo desde antes de Fase 11.

---

## Resumen de archivos tocados por ítem

| Ítem | Backend | Frontend |
|---|---|---|
| 18.1 ampliar pool default | `app/main.py` (`DEFAULT_CATEGORIES`, 8 entradas nuevas), `tests/test_categories.py` (nuevo) | — |
| 18.2 selección en registro | `app/core/default_categories.py` o similar (`BASE_REGISTRATION_CATEGORY_NAMES`, nuevo módulo para evitar import circular con `main.py`), `api/users.py` (`crear_usuario`), `tests/test_categories.py`/`tests/test_users.py` | — |
| 18.3 ocultas para mí | `models/models.py` (`HiddenCategory`, nuevo), `schemas/schemas.py` (`CategoryResponse.is_hidden`), `api/categories.py` (4 handlers reescritos + 2 endpoints nuevos `/{id}/hide`), migración Alembic nueva, `tests/test_categories.py` | `types/api.ts` (`Category.is_hidden`), `components/forms/TransactionCaptureForm.tsx` (filtro), `app/(dashboard)/categories/page.tsx` (toggle Eye/EyeOff + `toggleHiddenMutation`) |
| 18.4 activar editor | — | `app/(dashboard)/categories/page.tsx` (flag `true`) |
| Cruzando toda la fase | — | `backend/docs/API_REFERENCE.md` + `frontend/docs/API_CONTRACT.md` (documentar `is_hidden` en `CategoryResponse` y los endpoints nuevos `POST`/`DELETE /categories/{id}/hide` — convención de `CLAUDE.md` sobre contratos de API compartidos), `backend/docs/BUSINESS_RULES.md` (agregar la regla de "ocultar" junto a las reglas de categorías existentes, línea ~56-101) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de la
sección "Fase 18" de `docs/ROADMAP.md`, con esquemas, endpoints y componentes concretos para
que un `backend-engineer`/`frontend-engineer` puedan partir directamente de aquí. Dos de sus
decisiones (Q2/Q3) corrigen explícitamente una lectura literal del encabezado del ítem 2 del
ROADMAP ("selección... en el registro" sugiere una pantalla; se resuelve como un default de
backend sin ninguna UI nueva), con el mismo criterio que Fase 10 §10.1.4 y Fase 15 §15.0.3 ya
aplicaron para no reintroducir fricción de registro. Las siete decisiones de arquitectura
(Q1–Q7) fueron evaluadas por el agente `software-architect` contra el código real el
2026-09-12, con cita de línea exacta en cada caso; un refinamiento adicional sobre su sketch de
`CategoryResponse.is_hidden` (Decisión 18.3.2) fue encontrado al ensamblar esta spec y está
documentado explícitamente como tal. Todos los hallazgos de este documento fueron verificados
contra el código real de `backend/` y `frontend/` el 2026-09-12 — ningún archivo del
repositorio fuera de `docs/specs/fase_18_spec.md` fue modificado al producirlo.
