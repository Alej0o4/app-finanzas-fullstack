# Spec — Fase 16: Automatizaciones y preparación móvil (post-MVP)

> Plan de implementación detallado para los 4 ítems de Fase 16 del [ROADMAP](../ROADMAP.md).
> Fuente de verdad de alcance: `docs/ROADMAP.md` (sección "Fase 16 — Automatizaciones y
> preparación móvil"). Este documento no cambia el alcance ahí definido — lo desglosa en
> tareas ejecutables, con archivos concretos, esquemas de datos y decisiones de diseño
> numeradas, para que backend-engineer/frontend-engineer puedan partir directamente de aquí.
>
> **No implementa nada.** Ningún archivo del repositorio fuera de
> `docs/specs/fase_16_spec.md` fue modificado al producir este documento. Todos los hallazgos
> fueron verificados contra el código real de `backend/` y `frontend/` el 2026-09-06 —
> incluyendo una inspección directa del `openapi.json` real generado por la app (ver
> hallazgo 7) y la firma exacta de los routers de `transactions.py`/`accounts.py`, no
> inferencia a partir de comentarios o memoria de fases anteriores.

Estado del repo al momento de escribir esto (2026-09-06): Fases 7–15 están completas, más la
parada de correcciones de UX post-pivote. Fase 16 es post-MVP — los cinco componentes
funcionales del MVP (`docs/ROADMAP.md` "El MVP en cinco componentes") ya están construidos y
en uso. A diferencia de Fase 14 (que introdujo el primer job periódico del proyecto) y de
Fase 13 (que introdujo la primera infraestructura de push), Fase 16 introduce el primer
**mecanismo de autenticación alternativo al flujo OAuth2 password + refresh** (§16.1) y la
primera vez que el proyecto genera código a partir de su propio contrato de API (§16.3) — dos
precedentes nuevos, no extensiones de algo ya construido.

---

## Hallazgos de exploración que corrigen/precisan el ROADMAP

1. **El backend ya es, en efecto, "REST/JSON stateless con bearer tokens" como dice el
   encabezado de la fase — confirmado, no asumido.** `backend/app/core/security.py:42`
   define `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")` y
   `get_current_user` (líneas 83-102) solo sabe decodificar JWT. No hay sesiones de servidor,
   cookies de sesión, ni estado en memoria por request más allá de la conexión a DB — el punto
   de extensión para API keys es exactamente uno: esa función.

2. **`Account.balance` NO se deriva en cada consulta — es una columna mutada con deltas en
   cada `INSERT`/`UPDATE`/`DELETE` de transacción, confirmado en las tres rutas.**
   `backend/app/api/transactions.py:103-110` (crear), `:298-322` (actualizar) y `:222-229`
   (eliminar) ejecutan `update(models.Account).values(balance=models.Account.balance + delta)`
   — un `UPDATE ... SET balance = balance + :delta` atómico a nivel SQL, no una suma calculada
   al leer. Esto confirma el problema real que motiva §16.4: si algún camino de código
   (un bug futuro, una migración de datos, una intervención manual en producción) toca
   `balance` sin pasar por estas tres rutas, o si una de estas tres falla a mitad de camino
   de forma no atrapada, **no existe ningún mecanismo — ni automático ni manual — para
   detectar la desviación**, porque no hay ninguna función que calcule "el saldo que debería
   ser" para compararlo contra el valor guardado. `backend/docs/BUSINESS_RULES.md:16` ya dice
   "el saldo real se deriva de transacciones e impactos contables", pero esa frase describe la
   intención de diseño, no un mecanismo verificable — hoy es una afirmación sin forma de
   probarse falsa.

3. **La categoría "editor sin v1" no es una restricción del backend — es solo una omisión de
   UI, confirmado en `categories.py`.** `POST /api/v1/categories/` (`categories.py:15-25`)
   sigue aceptando cualquier `name`/`type` y crea una fila con `user_id=current_user.id`, sin
   ninguna validación de unicidad contra categorías existentes (ni del sistema ni propias). No
   hay `UniqueConstraint`/índice único sobre `(user_id, name, type)` en el modelo `Category`
   (`models.py:58-69`) — a diferencia de `Budget`, que sí tiene
   `uq_budgets_user_category_period_active`. Esto importa directamente para §16.2: un cliente
   que le pegue a la API cruda (un Shortcut, o cualquier herramienta de prueba) **puede crear
   hoy mismo** una categoría personal llamada "Alimentación" tipo `expense`, duplicando el
   nombre de la categoría de sistema homónima — el editor está oculto en la UI de React, no
   deshabilitado en el servidor. La resolución por nombre de §16.2 tiene que asumir que este
   caso, aunque raro, es posible.

4. **Los Decimal del backend ya se tipan como `string` en el `openapi.json` real — verificado
   generando el schema en vivo, no asumido.** Se ejecutó
   `app.openapi()["components"]["schemas"]["TransactionResponse"]["properties"]["amount"]`
   contra el código de este worktree: devuelve `{"type": "string", "pattern": "...decimal..."}`,
   no `{"type": "number"}`. Esto coincide exactamente con el comportamiento en runtime que ya
   documentó Fase 15 (`docs/ROADMAP.md:451-453`, hallazgo 2: *"los `Decimal` del backend
   serializan a `string` en JSON"*) — pero **`frontend/types/api.ts` (mantenido a mano) tipa
   esos mismos campos como `number`**: `balance: number` (línea 4), `amount: number` (línea
   12), `spent: number` (línea 45), `monthly_income: number | null` (línea 87). Es decir: el
   drift que motiva §16.3 no es hipotético — ya existe hoy, en el campo más sensible del
   dominio (dinero), y ya causó al menos un bug real y corregido (Fase 15, Decisión 15.6,
   `dashboard/page.tsx:101`, `Number(...)` agregado a mano tras encontrar el caso en vivo). Un
   codegen desde `openapi.json` habría tipado `amount`/`balance` como `string` desde el primer
   día, exponiendo el mismatch en tiempo de compilación en vez de en producción.

5. **`openapi.json` vive en la raíz de la app (`/openapi.json`), no bajo `/api/v1/`.** FastAPI
   expone el schema en `app.openapi_url` (default `/openapi.json`), un setting a nivel de
   `FastAPI()` en `backend/app/main.py:37-39`, independiente del prefijo con el que se montan
   los routers (`/api/v1/...`, líneas 176-185). El ROADMAP dice correctamente "FastAPI ya
   expone `/openapi.json`", pero conviene precisarlo porque `frontend/lib/api.ts:4` fija
   `baseURL` en `${NEXT_PUBLIC_API_URL}/api/v1` — es fácil asumir por costumbre que el schema
   también cuelga de ahí. El script de codegen de §16.3 debe apuntar a
   `http://localhost:8000/openapi.json`, no a `.../api/v1/openapi.json`.

6. **El rate limiting de `slowapi` está keyed por IP (`get_remote_address`), y `POST
   /transactions` hoy no tiene NINGÚN rate limit — ni por IP ni de ningún otro tipo.**
   `backend/app/core/rate_limit.py:4` (`Limiter(key_func=get_remote_address)`) y
   `backend/docs/API_REFERENCE.md:7` confirman que solo `/auth/login`, `POST /users/` y
   `/auth/password-reset/request` llevan `@limiter.limit(...)`. Esto es relevante para §16.1:
   una API key comprometida usada para automatizar `POST /transactions` no encuentra ningún
   límite existente que la frene — ni el de login (no aplica, no hay login de por medio) ni
   ninguno propio del endpoint de captura.

7. **El deployment sigue siendo un solo proceso `uvicorn` sin `--workers`, sin cambios desde
   Fase 14.** `backend/Dockerfile` y `docker-compose.yml` no declaran réplicas — el mismo
   hecho que ya usaron Fase 7 (§2.6.1) y Fase 14 (§14.4.1, hallazgo 6 de su spec) para diferir
   infraestructura distribuida sigue vigente sin cambios. Importa para §16.1: el diferimiento
   del rate limiting distribuido (Redis + `storage_uri`) **no se reabre por las API keys** — es
   un eje ortogonal (almacenamiento del contador: memoria vs. Redis) distinto del eje que sí
   cambia con las API keys (la *clave* del contador: IP vs. usuario/key). Ver Decisión 16.1.6.

8. **`GET /accounts/{account_id}` y `accounts.py` en general no tienen ningún endpoint de
   "operación" además de CRUD + `toggle_destacada`** (`accounts.py:90-103`) — no hay
   precedente en el propio módulo de una ruta que dispare un recálculo o una acción de
   negocio sobre una cuenta puntual. El patrón más cercano en todo el backend es
   `PATCH /{account_id}/highlighted` (toggle sin body, respuesta = recurso actualizado) — se
   usa como plantilla de forma/convención para el endpoint de reconciliación de §16.4, no
   porque haya lógica compartida.

9. **`AccountCreate.balance` (`schemas.py:165`) es hoy, literal y únicamente, el saldo de
   apertura — el nombre del campo ya es engañoso.** Se documenta como "Saldo inicial" en el
   propio `Field(..., description="Saldo inicial")`, y `accounts.py:19`
   (`models.Account(**cuenta.model_dump(), ...)`) lo escribe directo en la única columna
   `balance` que existe hoy. No hay ninguna ruta de la API que permita cambiar `balance`
   después de la creación salvo las tres de transacciones (hallazgo 2) — `actualizar_cuenta`
   (`accounts.py:70-87`) actualiza `name`/`type`/`highlighted` explícitamente y nunca toca
   `balance`, confirmando `BUSINESS_RULES.md:15` ("en edición, `balance` no debe ser
   modificable por el Frontend"). Separar `opening_balance`/`current_balance` (§16.4) es, en
   ese sentido, más una aclaración de nombre + la construcción de la verificación que falta,
   que un cambio de comportamiento.

10. **Ya existe una primera página de Ajustes (`/settings`) construida en Fase 14** —
    `frontend/app/(dashboard)/settings/page.tsx`, un único `<section>` con un `Switch`. Esto
    cambia el costo real de la UI de gestión de API keys (§16.1): a diferencia de Fase 14, que
    tuvo que construir la superficie de Ajustes desde cero (hallazgo 9 de su spec, +12h de
    ajuste), Fase 16 solo necesita **agregar una segunda sección** a una página que ya existe,
    con navegación ya resuelta (entrada "Ajustes" ya está en el sidebar). El costo de UI de
    §16.1 es sustancialmente menor que si esta fuera la primera pieza de Ajustes del producto.

11. **No existe ningún registro de accesos ni columna `last_login`/`last_used_at` en ningún
    modelo del proyecto hoy.** `grep -rn "last_used\|last_login\|last_seen" backend/app` no
    devuelve nada — el patrón más cercano es `RefreshToken.expires_at`/`revoked_at`, que
    registra vigencia pero no uso. `Notification.created_at` tampoco cuenta como precedente
    (es de creación, no de acceso). `last_used_at` en `api_keys` (§16.1.1) es, entonces, la
    primera columna del proyecto que trackea "cuándo se usó por última vez" algo — no hay un
    patrón existente que copiar, se diseña desde cero en este documento (Decisión 16.1.4).

12. **`docs/TODO.md` tiene una entrada desactualizada que colisiona con el análisis de
    §16.1.** La sección "🟡 Integridad y escala" (`docs/TODO.md:65-67`) todavía lista **"Sin
    idempotencia en `POST /transactions`"** como pendiente, pero ese ítem se resolvió en Fase
    10 (`docs/ROADMAP.md:243-248`, `Idempotency-Key` + tabla `idempotency_keys`, confirmado en
    `transactions.py:29-64`) y nunca se movió a la sección "Resueltos" de `TODO.md`. No es un
    hallazgo de esta fase per se, pero es relevante porque el mismo archivo también documenta
    correctamente **"Saldos de cuenta sin reconciliación posible"** (línea 59, sigue vigente,
    confirma hallazgo 2) — quien implemente Fase 16 debería corregir la entrada de
    idempotencia obsoleta en el mismo cambio que mueve la de reconciliación a "Resueltos" y
    agrega la de API keys, para no dejar una tercera inconsistencia en el archivo.

13. **El único agente de revisión de seguridad disponible en este entorno vive fuera del
    repo** (`~/.claude/agents/security-reviewer.md`, agente global, no específico de Oikos) —
    no hay ningún hallazgo de seguridad de fases anteriores que lo haya invocado
    explícitamente en el historial de specs revisado (`fase_07_spec.md` §2.5.1 documenta una
    decisión de seguridad —no agregar blacklist de JWT— pero como análisis propio del spec, no
    como resultado de una revisión delegada). §16.1 sería el primer punto del proyecto donde
    se recomienda explícitamente invocarlo antes de escribir código — ver Decisión 16.1.7.

---

## Orden de dependencia real (no el orden del ROADMAP)

El ROADMAP lista los 4 ítems en el orden "API keys → captura por nombre → codegen →
reconciliación". Ese orden es correcto para los primeros dos (hay una dependencia de producto
real, ver abajo) pero no para los últimos dos, que son mutuamente independientes entre sí y
del resto:

```
1. API keys (§16.1)         — pieza habilitante. Sin dependencias de código de los otros 3
   ítems. Es el único que toca la superficie de autenticación compartida por todos los
   routers (get_current_user) — cualquier error aquí tiene radio de impacto de app completa,
   no de un endpoint. Recomendado primero también por eso: si algo va a requerir una segunda
   vuelta de diseño, mejor que sea antes de construir algo encima.

2. Captura por nombre (§16.2) — CERO dependencia de código de (1): el cambio de schema/router
   de este ítem es independiente y se puede escribir y probar (vía JWT normal, en pytest) sin
   que (1) exista todavía. La dependencia es de PRODUCTO, no de código: sin (1), un Shortcut
   de iOS no tiene forma de autenticarse contra este endpoint — el ROADMAP lo dice
   explícitamente para el conjunto de la fase ("Un Shortcut de iOS no puede hacer el flujo
   OAuth2 password"). Construir (2) antes que (1) es viable técnicamente pero no entrega
   nada usable por el canal que motiva la fase hasta que (1) también esté.

3. Reconciliación de saldos (§16.4) — independiente de (1) y (2) en código y en producto
   (arregla un problema de integridad de datos que existe hoy, con o sin API keys). Se ubica
   aquí, después de (1)+(2) y antes de (4), porque comparte dominio (`Account`/`Transaction`)
   con el trabajo recién hecho en (2) — aprovechar el contexto ya cargado del módulo de
   transacciones reduce el costo real de cambio de contexto, no por dependencia técnica.

4. Codegen de tipos (§16.3) — independiente de los tres anteriores en código. Se ubica último
   a propósito: el primer snapshot generado captura de una sola vez los schemas nuevos de (1)
   (`ApiKeyResponse`) y (4) → (3) (`AccountReconcileResponse`), en vez de generarse, quedar
   desactualizado en cuanto (1)/(3) agreguen schemas, y tener que regenerarse de nuevo. El
   costo de regenerar es casi cero (un comando), así que esto no es una dependencia dura —
   es la secuencia que evita trabajo repetido sin costo.
```

**Orden de implementación recomendado: 16.1 → 16.2 → 16.4 → 16.3.** Esto invierte el orden
16.3/16.4 del ROADMAP (que lista codegen antes que reconciliación) — el ROADMAP no declara
una dependencia entre ellos y el análisis de este documento no encuentra ninguna; el swap es
puramente para que §16.3 no tenga que regenerarse una segunda vez. Si por alguna razón se
prioriza tener el codegen operativo cuanto antes (p. ej. para empezar a migrar tipos de forma
incremental en paralelo a los otros ítems), no hay ningún riesgo real en construir §16.3
primero — es una preferencia de secuencia, no una regla.

---

## 16.1 API keys personales revocables

### 16.1.1 Modelo de datos

**Decisión 16.1.1 — tabla `api_keys` nueva, sin `SoftDeleteMixin`, mismo criterio que
`RefreshToken`/`PasswordResetToken`/`EmailVerificationToken`/`IdempotencyKey`.** Es
credencial/bitácora técnica, no un dato de dominio que el usuario liste como historial — una
key revocada no tiene valor de negocio una vez revocada, y "revocada" ya es un estado
representable con `revoked_at`, no hace falta borrado lógico encima.

```python
# backend/app/models/models.py
class ApiKey(Base):
    """API key personal revocable (Fase 16 §16.1). Habilita clientes que no pueden hacer el
    flujo OAuth2 password + refresh (Shortcuts de iOS/Android; en el futuro, la nota de voz
    de v1.2, ver backlog del ROADMAP).

    Sin scopes en v1 (Decisión 16.1.1): una API key tiene exactamente los mismos permisos
    que el JWT del mismo usuario — la autorización real ya vive en cada router, filtrada por
    `user_id` (ver `transactions.py`, `accounts.py`, etc.), no en el tipo de token. Agregar
    scopes ahora sería anticipar una necesidad no pedida por el ROADMAP.
    """

    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)  # etiqueta elegida por el usuario, ej. "Shortcut iPhone"
    key_hash = Column(String, nullable=False, index=True)  # sha256, mismo helper que RefreshToken
    # Primeros 12 caracteres de la key en texto plano — NO es secreto por sí solo (no tiene
    # entropía suficiente), solo permite distinguir keys en la lista sin volver a mostrar la
    # key completa (mismo patrón que un PAT de GitHub: "ghp_A1b2***"). Decisión 16.1.2.
    key_prefix = Column(String(12), nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", backref="api_keys")

    __table_args__ = (Index("ix_api_keys_user_id_revoked_at", "user_id", "revoked_at"),)
```

Sin expiración obligatoria por diseño — ver Decisión 16.1.7 (recomendación de revisión de
seguridad) para la razón de no fijar esto unilateralmente en este documento.

### 16.1.2 Formato del token y verificación

**Decisión 16.1.2 — token con prefijo reconocible (`oikos_pat_<43 chars urlsafe>`), reusando
el mismo header `Authorization: Bearer <token>` que el JWT — no un header paralelo
(`X-API-Key`) ni un segundo `oauth2_scheme`.** Razones:

- El contrato de autenticación del proyecto, documentado en tres lugares
  (`CLAUDE.md` "Auth flow", `backend/docs/API_REFERENCE.md:6`, `frontend/docs/API_CONTRACT.md`
  sección "Base URL y autenticación"), es un único mecanismo: `Authorization: Bearer <token>`.
  Agregar un segundo header solo para las API keys duplicaría esa documentación con una
  bifurcación que ningún otro cliente del proyecto necesita — el frontend web nunca usará
  API keys (usa el flujo JWT + refresh normal), así que el header nuevo solo existiría para
  clientes externos, que de todos modos tienen que leer la documentación de todas formas.
- El prefijo (`oikos_pat_`) permite distinguir "esto es una API key" de "esto es un JWT" con
  una comparación de string barata (`token.startswith("oikos_pat_")`), **antes** de intentar
  `jwt.decode(...)` — evita apoyar la lógica de branching en capturar `JWTError` como
  mecanismo de control de flujo (frágil: un JWT malformado por otra razón terminaría cayendo
  en la rama de API key y fallando con un mensaje confuso).

```python
# backend/app/core/security.py — extensión de get_current_user, no una función paralela
API_KEY_PREFIX = "oikos_pat_"


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if token.startswith(API_KEY_PREFIX):
        return _get_user_from_api_key(token, db, credentials_exception)

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def _get_user_from_api_key(token: str, db: Session, credentials_exception: HTTPException) -> models.User:
    api_key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.key_hash == hash_token(token), models.ApiKey.revoked_at.is_(None))
        .first()
    )
    if api_key is None:
        raise credentials_exception
    # Decisión 16.1.4: última fecha de uso, sin throttling de escritura — el volumen de
    # llamadas esperado (automatizaciones personales, no tráfico masivo) no lo justifica.
    api_key.last_used_at = datetime.now(UTC)
    db.commit()
    user = db.query(models.User).filter(models.User.id == api_key.user_id).first()
    if user is None:
        raise credentials_exception
    return user
```

**Decisión 16.1.3 — se extiende `get_current_user` directamente, no se crea una dependencia
paralela (`get_current_user_or_api_key`) que cada router tendría que adoptar a mano.** Los 9
routers que ya dependen de `get_current_user`
(`transactions`, `accounts`, `categories`, `budgets`, `dashboard`, `notifications`, `push`,
`preferences`, `users`) heredan soporte de API keys sin tocar una sola línea de router —
coherente con el encabezado del ítem en el ROADMAP ("no hay que rehacer nada, solo agregar las
piezas que faltan") y con CLAUDE.md ("no hay capa de servicios... a la escala actual"):
duplicar la dependencia de auth por router sería el tipo de fragmentación que esa misma nota
de arquitectura ya evita en otros lados. Efecto secundario aceptado y explícito: **toda ruta
protegida del backend queda accesible con una API key**, no solo `POST /transactions` — es
coherente con que las API keys no tienen scopes en v1 (Decisión 16.1.1); si en el futuro se
necesita una key de alcance más angosto ("solo crear transacciones"), ahí sí se justifica
agregar `scopes` a la tabla y filtrar por endpoint, pero no antes de que haya una necesidad de
producto concreta.

### 16.1.3 Revocación inmediata

**Decisión 16.1.4 — revocación de una API key es efectiva en el siguiente request, sin
ventana de gracia, a diferencia del JWT (15 min sin blacklist, `fase_07_spec.md` §2.5.1).**
`_get_user_from_api_key` consulta `revoked_at IS NULL` en cada llamada — un `UPDATE
api_keys SET revoked_at = now() WHERE id = :id` hace que la siguiente petición con esa key
falle con 401 inmediatamente. Esto es precisamente la superficie de seguridad que la fase
pide ("revocación inmediata") y es más fuerte que el JWT porque el costo de una consulta
extra por request autenticado con API key es aceptable (no aplica a las peticiones
autenticadas con JWT, que no pagan ese costo — la rama de `if token.startswith(...)` es
barata y no toca DB para JWT).

### 16.1.4 Exposición única en creación + UI de gestión

**Decisión 16.1.5 — la key en texto plano se devuelve UNA sola vez, en la respuesta del
`POST`, igual que un PAT de GitHub; nunca se puede volver a consultar.**

```python
# backend/app/schemas/schemas.py
class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str  # texto plano — SOLO aparece en esta respuesta
    key_prefix: str
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
```

```python
# backend/app/api/api_keys.py (nuevo router)
@router.post("/", response_model=schemas.ApiKeyCreateResponse)
def crear_api_key(body: schemas.ApiKeyCreate, db=Depends(get_db), current_user=Depends(get_current_user)):
    raw_key = security.generate_api_key()
    nueva = models.ApiKey(
        user_id=current_user.id,
        name=body.name,
        key_hash=security.hash_token(raw_key),
        key_prefix=raw_key[:12],
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return {
        "id": nueva.id, "name": nueva.name, "key": raw_key,
        "key_prefix": nueva.key_prefix, "created_at": nueva.created_at,
    }


@router.get("/", response_model=list[schemas.ApiKeyResponse])
def listar_api_keys(db=Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.ApiKey).filter(models.ApiKey.user_id == current_user.id).all()


@router.delete("/{api_key_id}")
def revocar_api_key(api_key_id: int, db=Depends(get_db), current_user=Depends(get_current_user)):
    api_key = db.query(models.ApiKey).filter(
        models.ApiKey.id == api_key_id, models.ApiKey.user_id == current_user.id
    ).first()
    if not api_key or api_key.revoked_at is not None:
        raise HTTPException(status_code=404, detail="La API key no existe o ya fue revocada.")
    api_key.revoked_at = datetime.now(UTC)
    db.commit()
    return {"estado": "OK", "mensaje": "API key revocada exitosamente."}
```

`DELETE` revoca (marca `revoked_at`), no borra la fila — conserva `last_used_at`/`created_at`
para que el usuario pueda ver en la lista que existió y cuándo se usó por última vez, útil
para auditar un incidente ("¿esta key comprometida se usó recientemente?").

**Decisión 16.1.6 — UI nueva: sección "API keys" en `/settings` (hallazgo 10), no una página
aparte.** Extiende la página que ya existe (`frontend/app/(dashboard)/settings/page.tsx`) con
una segunda `<section>`, siguiendo el mismo patrón visual que la sección de resumen semanal
(tarjeta `bg-surface border-border/70 rounded-2xl`). Contenido: lista de keys (nombre, prefijo,
"último uso hace X", botón revocar con `ConfirmDialog` ya existente en el proyecto), botón
"Nueva API key" que abre un modal con el campo `name` y, tras crear, muestra la key completa
una sola vez con un botón "Copiar" y una advertencia explícita de que no se puede volver a ver.

### 16.1.5 Rate limiting

**Decisión 16.1.7 — se agrega un rate limit nuevo, keyed por usuario (no por IP), aplicado
solo a las rutas de escritura más expuestas a automatización (`POST /transactions`), no a
todas las rutas protegidas.** El limiter existente (`get_remote_address`) no protege nada aquí
porque una automatización personal corre desde una IP estable — el riesgo real no es "un
humano hace 300 requests por minuto desde el navegador" (no cambia con esta fase) sino "una
API key filtrada permite automatizar creación de transacciones sin el freno implícito de que
un humano tiene que tocar la pantalla". `slowapi` soporta `key_func` por decorador —
`crear_transaccion` gana un límite generoso (`60/minute`, muy por encima de cualquier uso
legítimo de un Shortcut) keyed por `current_user.id` cuando la petición está autenticada con
API key:

```python
# backend/app/core/rate_limit.py
def key_func_por_usuario_o_ip(request: Request) -> str:
    """Si la petición trae una API key (Fase 16 §16.1), el límite es por usuario — una
    automatización corre desde una IP estable y el límite por IP no la protege de sí misma
    ni de un abuso si la key se filtra. Si es JWT o anónima, se mantiene el límite por IP
    existente (sin cambio de comportamiento para el frontend web)."""
    auth = request.headers.get("authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token.startswith(security.API_KEY_PREFIX):
        # El propio endpoint ya resolvió current_user vía get_current_user antes de este
        # punto en el ciclo de vida del request — se re-decodifica aquí porque slowapi
        # evalúa el key_func antes de que la dependencia de FastAPI corra. Costo: una
        # consulta extra a api_keys, aceptable dado que ya se paga una en get_current_user.
        ...  # resolver user_id del mismo modo que _get_user_from_api_key, sin mutar last_used_at otra vez
    return get_remote_address(request)
```

*(Nota de implementación: `slowapi` evalúa `key_func` antes de que las dependencias de
FastAPI se resuelvan, así que este `key_func` no puede simplemente leer
`request.state.current_user` a menos que se agregue un middleware que lo popule antes. Evaluar
en implementación si conviene mover la resolución del usuario a un middleware liviano que la
deje en `request.state` para que tanto `get_current_user` como este `key_func` la reusen sin
consultar la tabla dos veces — optimización, no bloqueante para la primera versión.)*

**Sobre si el diferimiento de rate limiting distribuido (Fase 7 §2.6.1) sigue vigente: sí, sin
cambios (hallazgo 7).** Las API keys cambian la *clave* del contador (usuario en vez de IP
para ese caso puntual), no el *almacenamiento* del contador (sigue en memoria, sigue siendo
válido porque sigue habiendo un solo worker). Son ejes ortogonales — este documento no
reabre esa decisión, solo la reafirma explícitamente para que quede claro que no se pasó por
alto.

### 16.1.6 Recomendación de revisión de seguridad

**Decisión 16.1.8 — se recomienda explícitamente una pasada de `security-reviewer`
(`~/.claude/agents/security-reviewer.md`) sobre la implementación final de §16.1, antes de
mergear, no como parte de este documento de spec.** Razones concretas, no genéricas:

1. Es el primer mecanismo de autenticación del proyecto que se diseña para vivir guardado en
   una aplicación de terceros fuera del control del proyecto (la app de Shortcuts de iOS,
   potencialmente sincronizada vía iCloud) — una superficie de exposición sin precedente
   comparable a un JWT de 15 minutos o un refresh token que solo vive en `localStorage` del
   propio frontend.
2. La extensión de `get_current_user` (Decisión 16.1.3) es compartida por **todas** las rutas
   protegidas del backend — un error de lógica aquí (p. ej. una condición mal puesta en el
   `if token.startswith(...)`) tiene radio de impacto de aplicación completa, a diferencia de
   un bug en un router individual.
3. Es, tal como quedó diseñado en este documento, **el único tipo de credencial del proyecto
   sin expiración obligatoria** — `RefreshToken` expira en 30 días, `PasswordResetToken` en 45
   minutos, `EmailVerificationToken` en 48 horas (todos en `security.py:29-32`); una API key
   revocable pero sin TTL es una decisión de producto razonable (mismo criterio que un PAT de
   GitHub) pero es exactamente el tipo de tradeoff que vale una segunda opinión explícita en
   vez de asumirse en un documento de planificación.
4. Punto verificado y descartado como riesgo en este análisis (no hace falta que
   `security-reviewer` lo repita): `backend/app/core/logging_config.py` y el
   `request_id_middleware` de `main.py:118-137` no loguean headers de request —
   confirmado por lectura directa, no hay riesgo de que la key en texto plano quede en logs
   estructurados vía este camino.

No es responsabilidad de este documento tomar esas tres decisiones (TTL sí/no, scopes sí/no,
diseño final del `key_func`) de forma unilateral — se dejan explícitamente para la revisión.

### Migración Alembic — 16.1

`alembic revision --autogenerate -m "fase_16_api_keys"` — una tabla nueva, sin backfill de
datos (no hay filas preexistentes que migrar). Revisar a mano que el índice compuesto
`ix_api_keys_user_id_revoked_at` se genere correctamente (autogenerate normalmente sí infiere
índices simples sin `where` parcial, a diferencia de los índices únicos parciales de Fases 13/14
— este no lleva `postgresql_where`, así que no debería requerir el mismo cuidado extra).

---

## 16.2 Endpoint de captura rápida por nombre

### 16.2.1 Mismo endpoint, no uno nuevo

**Decisión 16.2.1 — se extiende `POST /api/v1/transactions/` (mismo endpoint, mismo router),
no se crea un endpoint paralelo.** Un segundo endpoint tendría que reimplementar entera la
lógica contable de `crear_transaccion` (verificación de cuenta/categoría, actualización
atómica de saldo, idempotencia, hook del motor de presupuestos) — exactamente el tipo de
duplicación que `docs/TODO.md` ya señala como deuda ("🟢 Modularidad... lógica contable
duplicada en crear/actualizar/eliminar transacción", línea 87) y que este ítem empeoraría en
vez de mejorar si se resuelve con un tercer lugar donde vive esa lógica. La resolución por
nombre es, en cambio, un paso de *traducción* antes de que la lógica existente corra sin
cambios.

```python
# backend/app/schemas/schemas.py — TransactionBase gana un campo alternativo
class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = "COP"
    type: TransactionType
    description: str | None = Field(None, max_length=500)
    account_id: int | None = None       # antes: obligatorio (Decisión 16.2.4)
    category_id: int | None = None      # antes: obligatorio
    category: str | None = Field(None, max_length=100)  # alternativa por nombre (Decisión 16.2.2)
    date: datetime | None = None
    payment_method: PaymentMethod | None = None

    @model_validator(mode="after")
    def category_id_xor_category_name(self) -> "TransactionBase":
        if (self.category_id is None) == (self.category is None):
            raise ValueError("Especificar exactamente uno de 'category_id' o 'category'.")
        return self
```

La resolución de `category` → `category_id` ocurre en el router (`crear_transaccion`), **antes**
de la verificación de pertenencia que ya existe (líneas 76-88 de `transactions.py`) — una vez
resuelto, el resto del endpoint no cambia una sola línea.

### 16.2.2 Resolución de categoría por nombre

**Decisión 16.2.2 — normalización sin acentos/mayúsculas, filtrado por `type` (elimina
ambigüedad cruzada gasto/ingreso gratis), precedencia de categoría propia sobre categoría de
sistema si ambas matchean, y `409` si hay más de un match dentro del mismo alcance
(propio o sistema).**

```python
# backend/app/api/transactions.py
import unicodedata


def _normalizar_nombre_categoria(nombre: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return sin_acentos.strip().lower()


def _resolver_categoria_por_nombre(db: Session, user_id: int, nombre: str, tipo: str) -> models.Category:
    objetivo = _normalizar_nombre_categoria(nombre)
    candidatas = (
        db.query(models.Category)
        .filter(
            or_(models.Category.user_id.is_(None), models.Category.user_id == user_id),
            models.Category.type == tipo,
        )
        .all()
    )
    matches = [c for c in candidatas if _normalizar_nombre_categoria(c.name) == objetivo]
    propias = [c for c in matches if c.user_id == user_id]
    sistema = [c for c in matches if c.user_id is None]

    if propias:
        if len(propias) > 1:
            raise HTTPException(
                status_code=409,
                detail=f"Tenés más de una categoría propia llamada '{nombre}'. Usá category_id.",
            )
        return propias[0]
    if sistema:
        if len(sistema) > 1:  # no debería pasar hoy (DEFAULT_CATEGORIES no tiene duplicados), defensivo
            raise HTTPException(status_code=409, detail=f"Categoría '{nombre}' ambigua.")
        return sistema[0]

    nombres_validos = sorted({c.name for c in candidatas})
    raise HTTPException(
        status_code=404,
        detail=f"Categoría '{nombre}' no encontrada. Válidas para {tipo}: {', '.join(nombres_validos)}.",
    )
```

Justificación de cada sub-decisión:

- **Filtrar por `type` antes de comparar nombres** elimina de raíz la ambigüedad entre una
  categoría de gasto y una de ingreso con nombres parecidos — `type` ya es un campo
  obligatorio del payload (`TransactionBase.type`), así que no cuesta nada adicional pedirlo.
- **Precedencia propia > sistema** (no error de ambigüedad entre ambas) porque es el
  comportamiento intuitivo de "mi categoría personal reemplaza/oculta la de sistema con el
  mismo nombre" — y porque, si se tratara como error, un usuario que creó sin querer una
  categoría personal duplicada (posible hoy, hallazgo 3) quedaría bloqueado permanentemente
  para usar ese nombre por nombre, sin ninguna UI de edición de categorías para arreglarlo
  (editor oculto en v1).
- **`409` (no elegir arbitrariamente) si hay más de una categoría propia con el mismo nombre**
  — este caso sí es un error real de datos (dos categorías propias idénticas en nombre+tipo,
  posible hoy por el hallazgo 3) y adivinar mal significa gasto mal categorizado, un costo de
  silencio mayor al costo de devolver un error explícito.
- **No se agrega una constraint de unicidad `(user_id, name, type)` en `Category` en este
  ítem.** Cerraría el caso de raíz, pero es un cambio de invariante de dominio que pertenece
  naturalmente al alcance del "Editor de categorías personalizable" del backlog (que ya está
  fuera de v1 por decisión de Fase 8) — agregarlo aquí, de paso, en un ítem de 1 día dimensionado
  para la resolución por nombre, mezclaría dos decisiones de alcance distintas y arriesgaría
  un backfill fallido si ya existen duplicados en producción. Se anota como nota para cuando
  se retome el editor de categorías, no como tarea de esta fase.

### 16.2.3 `account_id` también se vuelve opcional

**Decisión 16.2.4 — `account_id` opcional con fallback "la única cuenta del usuario si tiene
exactamente una; `400` explícito si tiene más de una y no la especifica".** El ROADMAP solo
menciona `category` por nombre explícitamente, pero un Shortcut que arma el payload a mano
tiene el mismo problema con `account_id` que con `category_id` (necesita conocer el ID, no
solo el nombre). La razón por la que el ROADMAP probablemente no lo menciona es que, para la
mayoría de usuarios, la cuenta es un valor fijo: Fase 8 crea una única cuenta por defecto al
registrarse (`users.py:58-63`, "Cuenta principal") y Fase 10 ya trata "una sola cuenta" como el
caso común en la UI (`docs/ROADMAP.md:236`: "el selector solo aparece si el usuario tiene más
de una cuenta"). Mismo criterio aquí: si el usuario nunca agregó una segunda cuenta,
`account_id` no hace falta en el payload en absoluto — el Shortcut ni siquiera necesita
conocer el ID una vez configurado. Si el usuario tiene más de una cuenta y omite el campo, se
devuelve `400` (no se adivina cuál — mismo criterio de "no adivinar con dinero" que la
Decisión de categorías ambiguas). **No se resuelve `account` por nombre en v1** — no lo pide
el ROADMAP y el caso de uso principal (un único usuario con una cuenta) ya lo cubre la
omisión total del campo; agregar un segundo camino de resolución por nombre para un campo que
la mayoría de payloads ni siquiera necesita sería sobre-construir para este ítem de 1 día.

```python
# backend/app/api/transactions.py — dentro de crear_transaccion, antes de la resolución de categoría
if transaccion.account_id is not None:
    cuenta = db.query(models.Account).filter(
        models.Account.id == transaccion.account_id, models.Account.user_id == current_user.id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta especificada no existe o no te pertenece.")
else:
    cuentas_usuario = db.query(models.Account).filter(models.Account.user_id == current_user.id).all()
    if len(cuentas_usuario) != 1:
        raise HTTPException(
            status_code=400,
            detail="Especificá account_id: tenés más de una cuenta." if cuentas_usuario
            else "No tenés ninguna cuenta activa.",
        )
    cuenta = cuentas_usuario[0]
```

### 16.2.4 Espacio para la nota de voz con IA (v1.2) — sin sobre-construir ahora

**Decisión 16.2.5 — no se agrega ningún campo de texto libre nuevo (`raw_text`, `nl_input`)
en este ítem.** `TransactionBase.description` (`schemas.py:130`, `str | None`, ya libre y sin
estructura) ya cubre cualquier necesidad de texto arbitrario que el endpoint necesite hoy. La
resolución por nombre de categoría es la pieza que el backlog de voz (`docs/ROADMAP.md:589`,
"depende de la captura por nombre") necesita reusar — el parseo de lenguaje natural en sí
("gasté 20 mil en el almuerzo" → `amount=20000, category="Alimentación",
description="almuerzo"`) es un paso que **necesariamente ocurre antes** de llegar a este
endpoint (vía un servicio de NLP/LLM externo a definir en v1.2), no algo que este schema deba
anticipar. Diseñar aquí un campo para texto sin estructura que hoy no tiene ningún consumidor
sería la complejidad desproporcionada que el propio ROADMAP evita en otros ítems (rate
limiting distribuido, CI/CD) — se deja fuera, explícitamente, no por descuido.

### 16.2.5 Autenticación y orden con 16.1

Este endpoint hereda automáticamente el soporte de API keys en cuanto §16.1 esté implementado
(Decisión 16.1.3: `get_current_user` extendido cubre todos los routers sin cambios locales) —
**cero líneas de código nuevas en `transactions.py` relacionadas con autenticación**. La
dependencia entre ambos ítems es de producto, no de código (ver "Orden de dependencia real"
arriba): se puede escribir y probar §16.2 completo con JWT normal (vía `TestClient` +
fixtures existentes de `conftest.py`) sin que §16.1 exista todavía, pero no tiene sentido
entregarlo antes que §16.1 si el objetivo es que un Shortcut lo use.

---

## 16.3 Codegen de tipos desde OpenAPI

### 16.3.1 Herramienta y punto de generación

**Decisión 16.3.1 — `openapi-typescript` (devDependency), generación manual bajo demanda vía
script de `package.json`, apuntando a `http://localhost:8000/openapi.json` (hallazgo 5, no
`/api/v1/openapi.json`).** Es la opción estándar para proyectos Next.js/TS (genera tipos
puros a partir del schema, sin runtime propio, sin acoplarse a ningún cliente HTTP particular
— compatible con que el proyecto sigue usando Axios, no `fetch` tipado). No hay CI/CD
(confirmado fuera de scope en el ROADMAP, sección "Fuera de scope") así que la generación no
puede depender de un pipeline — se ejecuta a mano, contra un backend corriendo localmente
(Docker dev o `uvicorn --reload`), igual que ya se hace con `alembic revision --autogenerate`
(mismo patrón de "comando manual antes de commitear", ver skill `alembic-migration`).

```json
// frontend/package.json
{
  "scripts": {
    "gen:types": "openapi-typescript http://localhost:8000/openapi.json -o types/generated/api.ts"
  },
  "devDependencies": {
    "openapi-typescript": "^7"
  }
}
```

El archivo generado (`frontend/types/generated/api.ts`) **se commitea al repo** — sin CI que
lo regenere en build, un clon fresco sin backend corriendo necesita el archivo ya presente
para compilar. Convención (documentada en Decisión 16.3.3): regenerar y commitear como parte
del mismo PR que cambia un schema del backend, mismo criterio manual que ya usa el proyecto
para mantener sincronizados `API_REFERENCE.md`/`API_CONTRACT.md` (regla de CLAUDE.md).

### 16.3.2 Drift real verificado, no asumido

El costo de migración es más bajo de lo que el ROADMAP implícitamente asume ("elimina el
drift manual"): `frontend/types/api.ts` (búsqueda `find frontend -iname "*types*"`) es el
único lugar del frontend con tipos de dominio manuales — 15 interfaces, ~150 líneas,
razonablemente sincronizadas con el backend hoy (`weekly_summary_enabled`, `period_key` de
Fase 14 ya están reflejados, por ejemplo). El drift real y ya confirmado (hallazgo 4) es
puntual pero significativo: **todos los campos `Decimal` del backend
(`amount`, `balance`, `spent`, `amount_limit`, `total`, `monthly_income`) están tipados como
`number` en el archivo manual, pero el backend los serializa como `string`** — verificado
generando el `openapi.json` real de este worktree. No es un riesgo hipotético de "a medida
que crezca la API" — ya causó el bug corregido en Fase 15 (Decisión 15.6).

### 16.3.3 Convivencia, no reemplazo

**Decisión 16.3.2 — los tipos generados (`types/generated/api.ts`) conviven con los manuales
(`types/api.ts`); no se migra ningún call site existente en este ítem de 1 día.** Migrar cada
`useQuery`/`useMutation` que hoy usa una interfaz manual (varias decenas de sitios en
`app/(dashboard)/**`) es un refactor de alcance mucho mayor a 1 día, sin red de seguridad de
tests de frontend que lo cubra (`docs/TODO.md`, "🔵 Solo si el proyecto crece: Tests de
frontend (Vitest + React Testing Library)" sigue sin resolver) — el riesgo de introducir una
regresión silenciosa migrando tipos a ciegas es real. Se usa el mismo criterio de convivencia
gradual que el proyecto ya aplicó en otros lados (editor de categorías oculto, no eliminado;
`CategoryDonutChart` y `CategoryBreakdownBars` coexistiendo en vez de que uno reemplace al
otro, Fase 11): los tipos generados se usan **desde ahora, para código nuevo** (§16.1 y §16.4
son los primeros candidatos naturales, ya que sus schemas nacen junto con el codegen), y los
manuales se migran oportunistamente si/cuando se toque ese archivo por otra razón — no hay
fecha de deprecación fijada porque no hay evidencia de que haga falta una.

**Decisión 16.3.3 — se documenta la convención en `frontend/docs/STATE_AND_FETCHING.md`**
(no en `COMPONENTS_GUIDE.md`, que es sobre componentes visuales, no sobre datos): una sección
nueva breve que explica cuándo usar `types/generated/api.ts` (tipos exactos del contrato,
fuente de verdad para campos nuevos) vs. `types/api.ts` (tipos manuales existentes, con forma
más ergonómica para el código que ya los consume) y el comando para regenerar.

---

## 16.4 Reconciliación de saldos

### 16.4.1 Mecanismo actual confirmado (hallazgo 2)

`Account.balance` es una columna mutada con `UPDATE ... SET balance = balance + delta` en las
tres operaciones de escritura de transacciones (crear/actualizar/eliminar,
`transactions.py:103-110,298-322,222-229`) — no una vista ni un cálculo en cada lectura. El
bug que motiva este ítem (desviación no detectable) existe estructuralmente hoy: no hay
ninguna función en el backend que calcule "cuál debería ser el saldo" para poder compararlo.

### 16.4.2 Separar `opening_balance` de `current_balance`

**Decisión 16.4.1 — se agrega la columna nueva `opening_balance` (inmutable tras la
creación); NO se renombra la columna existente `balance`.** Renombrar `balance` →
`current_balance` tocaría el contrato de API en cascada:
`AccountResponse.balance`/`AccountCreate.balance` (`schemas.py:165,175`),
`frontend/types/api.ts` (`Account.balance`, `CreateAccountPayload.balance`), y cada call site
del frontend que lee `account.balance` (tarjetas de cuenta, dashboard, `accounts/[id]`) — un
costo de refactor no pedido por el objetivo real del ítem (poder verificar y corregir el
saldo, no renombrarlo). `balance` sigue siendo, en la práctica y en el nombre, "el saldo
actual" — que es exactamente lo que `BUSINESS_RULES.md:16` ya dice que es
("el saldo real se deriva de transacciones e impactos contables"), solo que ahora existe una
forma de comprobarlo.

```python
# backend/app/models/models.py, clase Account
class Account(Base, SoftDeleteMixin):
    ...
    balance = Column(Numeric(14, 2), default=0)  # saldo actual — sin cambios de nombre ni de semántica
    # Fase 16 §16.4: saldo de apertura, inmutable tras la creación de la cuenta. Ancla para
    # recalcular `balance` desde el historial de transacciones (ver reconcile_account_balance).
    opening_balance = Column(Numeric(14, 2), nullable=False, default=0, server_default=text("0"))
```

`crear_cuenta` (`accounts.py:16-23`) pasa a setear ambas columnas al mismo valor en la
creación (`opening_balance = balance = cuenta.balance` del payload) — `AccountCreate.balance`
no cambia de nombre ni de contrato público, solo alimenta dos columnas en vez de una.
`AccountResponse` gana `opening_balance: Decimal` para que el frontend pueda, opcionalmente,
mostrarlo (p. ej. en `accounts/[id]`, "Saldo de apertura: $X") — no es obligatorio para v1 de
frontend, pero el campo debe estar en el contrato desde el día uno del schema.

### 16.4.3 Endpoint de reconciliación

**Decisión 16.4.2 — `POST /api/v1/accounts/{account_id}/reconcile`, por cuenta individual
(no una operación masiva "todas las cuentas del usuario" en v1), aplica el recálculo de
inmediato y devuelve la discrepancia encontrada — sin paso de confirmación previo
("preview" + "aplicar" en dos pasos).**

```python
# backend/app/schemas/schemas.py
class AccountReconcileResponse(BaseModel):
    account_id: int
    previous_balance: Decimal
    recalculated_balance: Decimal
    discrepancy: Decimal  # recalculated_balance - previous_balance; 0.00 si no había desviación
    opening_balance: Decimal
```

```python
# backend/app/api/accounts.py
@router.post("/{account_id}/reconcile", response_model=schemas.AccountReconcileResponse)
def reconciliar_cuenta(
    account_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    cuenta = db.query(models.Account).filter(
        models.Account.id == account_id, models.Account.user_id == current_user.id
    ).first()
    if not cuenta:
        raise HTTPException(status_code=404, detail="La cuenta no existe o no tienes permisos.")

    neto = (
        db.query(
            func.sum(case((models.Transaction.type == "income", models.Transaction.amount), else_=-models.Transaction.amount))
        )
        .filter(models.Transaction.account_id == account_id, models.Transaction.deleted_at.is_(None))
        .scalar()
    ) or Decimal("0.00")

    saldo_recalculado = cuenta.opening_balance + neto
    saldo_anterior = cuenta.balance
    discrepancia = saldo_recalculado - saldo_anterior

    cuenta.balance = saldo_recalculado
    db.commit()

    return {
        "account_id": cuenta.id,
        "previous_balance": saldo_anterior,
        "recalculated_balance": saldo_recalculado,
        "discrepancy": discrepancia,
        "opening_balance": cuenta.opening_balance,
    }
```

Por qué **sin confirmación en dos pasos**: la acción ya la disparó explícitamente el usuario
(un botón "Recalcular saldo" en `accounts/[id]`, no un job automático) — es la misma cantidad
de intención humana que cualquier otra escritura de un solo paso ya existente en el proyecto
(`toggle_destacada`, por ejemplo). Agregar un paso de "preview, luego confirmar" sería
ceremonia de UI sin seguridad real adicional: la operación no es destructiva en el sentido de
perder datos (recalcula hacia el valor matemáticamente correcto dado el historial de
transacciones, nunca borra transacciones), y el número de discrepancia queda expuesto en la
respuesta para que el frontend lo muestre igual (`"Se corrigió una diferencia de $X"`) — el
usuario se entera del resultado, solo que después de aplicado, no antes.

Por qué **por cuenta, no "reconciliar todas"**: cada cuenta se reconcilia de forma
independiente y el caso de uso (una cuenta puntual que el usuario sospecha desviada) no
necesita una operación masiva. Si en producción se observa que varias cuentas de un mismo
usuario se desvían a la vez de forma recurrente, eso es señal de un bug sistémico que amerita
investigación propia, no una función "reconciliar todo" que lo enmascare — se deja
explícitamente fuera de v1, no por descuido sino porque agregar el endpoint masivo ahora sin
evidencia de que el caso ocurra sería anticipar una necesidad no observada.

### 16.4.4 Límite honesto del backfill (riesgo a documentar, no a resolver)

**Decisión 16.4.3 — estrategia de backfill: `opening_balance = balance_actual − neto(todas
las transacciones no eliminadas de la cuenta)`, ejecutado como parte de la migración
Alembic.**

```python
# backend/alembic/versions/<rev>_fase_16_opening_balance.py — cuerpo relevante de upgrade()
op.add_column("accounts", sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"))
op.execute("""
    UPDATE accounts
    SET opening_balance = accounts.balance - COALESCE((
        SELECT SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE -t.amount END)
        FROM transactions t
        WHERE t.account_id = accounts.id AND t.deleted_at IS NULL
    ), 0)
""")
```

**Advertencia explícita que debe quedar documentada (en el propio `BUSINESS_RULES.md`, no
solo aquí):** este backfill **no puede detectar retroactivamente ninguna desviación que ya
haya ocurrido antes de la migración** — no existe ningún snapshot histórico del saldo más
antiguo que "el `balance` actual" para comparar. La fórmula construye `opening_balance` de
forma que, en el momento exacto de la migración, `reconciliar_cuenta` para cualquier cuenta dé
discrepancia `0.00` — es un punto de partida limpio, no una auditoría del pasado. Esto es
correcto y suficiente para el objetivo real del ítem ("de ahora en adelante, poder detectar y
corregir desviaciones"), pero es distinto de "encontrar bugs de saldo que ya pasaron", que el
ROADMAP no pide y que, dado el mecanismo actual (hallazgo 2), no es técnicamente posible sin
una fuente de verdad externa (backups, `pg_dump` históricos) que este documento no asume
disponible ni recomienda construir para este fin.

### Migración Alembic — 16.4

Revisión separada de la de §16.1 (Decisión de "migraciones separadas" — ver sección
transversal más abajo). Contiene: `ALTER TABLE accounts ADD COLUMN opening_balance` +
`UPDATE` de backfill en el mismo archivo `upgrade()` — mismo patrón que Fase 8 usó para
`updated_at` (columna nueva + backfill en la migración, no en un script aparte). El
`server_default="0"` se mantiene en la columna (no se dropea después, a diferencia del patrón
de `updated_at`) porque `opening_balance=0` es un default legítimo para creación de cuentas
sin depósito inicial, no un placeholder temporal de migración.

---

## Transversal

### Migraciones Alembic — resumen

| Migración | Contenido | Backfill de datos | Reversible sin pérdida |
|---|---|---|---|
| `fase_16_api_keys` (§16.1) | Tabla `api_keys` nueva + índice | No aplica (tabla vacía) | Sí, `DROP TABLE` |
| `fase_16_opening_balance` (§16.4) | `accounts.opening_balance` + backfill `UPDATE` | Sí, calculado desde `transactions` | Downgrade pierde el valor backfillado (aceptable — recalculable de nuevo con el mismo `UPDATE` si hiciera falta) |

**No se combinan en una sola revisión** (Decisión transversal): son dos tablas/columnas sin
relación funcional entre sí, con perfiles de reversibilidad distintos — una es un `DROP TABLE`
trivial, la otra involucra una migración de datos reales. Combinarlas obligaría a
revertir/reaplicar ambas juntas incluso si solo una necesita un ajuste posterior, y acopla
innecesariamente la revisión de seguridad de §16.1 (que puede tomar más tiempo, Decisión
16.1.8) con el despliegue de §16.4 (que no tiene ninguna razón para esperar esa revisión).
§16.2 y §16.3 no requieren ninguna migración.

### Documentación cruzada a actualizar (regla de CLAUDE.md)

| Documento | Cambio |
|---|---|
| `backend/docs/API_REFERENCE.md` | Sección nueva "API keys" (§16.1: `POST`/`GET`/`DELETE /api/v1/api-keys/`); actualizar `POST /transactions/` para `category`/`account_id` opcionales (§16.2); sección nueva `POST /accounts/{id}/reconcile` (§16.4). Actualizar la lista de convenciones generales: el rate limit nuevo de §16.1.7 (`60/min` por usuario en `POST /transactions` cuando la auth es API key). |
| `frontend/docs/API_CONTRACT.md` | Mismos tres cambios reflejados del lado de contrato consumido por el frontend — `AccountResponse.opening_balance`, `TransactionCreate.category`/`account_id` opcionales, nuevos endpoints de API keys y reconciliación. |
| `backend/docs/BUSINESS_RULES.md` | Sección nueva "API keys" (revocación inmediata, sin scopes v1, sin expiración obligatoria); sección "Cuentas" actualizada con la separación `opening_balance`/`balance` + el límite honesto del backfill (§16.4.4, la advertencia debe vivir aquí, no solo en el spec); sección "Transacciones" actualizada con la regla de resolución por nombre (precedencia propia > sistema, `409` en ambigüedad, `404` sin fuzzy match). |
| `frontend/docs/STATE_AND_FETCHING.md` | Sección nueva sobre convivencia de `types/generated/api.ts` vs. `types/api.ts` (Decisión 16.3.3). |
| `docs/TODO.md` | Mover "Saldos de cuenta sin reconciliación posible" a "Resueltos" (§16.4 la cierra); agregar la API key como entrada de "Resueltos" tras el merge; **corregir de paso** la entrada obsoleta "Sin idempotencia en `POST /transactions`" (hallazgo 12 — ya resuelta desde Fase 10, nunca se movió). |

### Riesgos/supuestos del ROADMAP que este análisis ajusta

- **"El backend ya es REST/JSON stateless... no hay que rehacer nada"** — confirmado
  correcto (hallazgo 1), no se ajusta.
- **"Un Shortcut no puede resolver IDs cómodamente" (§16.2 del ROADMAP)** — correcto, pero el
  ROADMAP no menciona que `account_id` tiene el mismo problema; este documento lo resuelve con
  un fallback de menor costo (omitir el campo si hay una sola cuenta) en vez de agregar
  resolución por nombre también para cuentas (Decisión 16.2.4) — no es una corrección al
  ROADMAP sino una precisión que faltaba.
- **Orden ROADMAP (API keys → captura por nombre → codegen → reconciliación)** — se ajusta el
  orden de los últimos dos ítems (codegen después de reconciliación, no antes) por eficiencia
  de secuencia, sin dependencia dura de por medio (ver "Orden de dependencia real").
- **Estimación de horas de §16.1 (2d)** — se mantiene, pero con una salvedad: no incluye el
  tiempo de la revisión de `security-reviewer` recomendada en la Decisión 16.1.8, que es
  trabajo real, aunque no del `backend-engineer`/`frontend-engineer` que ejecute el resto.
- **Nada en el ROADMAP asumía la separación `opening_balance`/`balance` como un rename** — se
  confirma que no lo es (Decisión 16.4.1), lo cual reduce el costo real de §16.4 frente a una
  lectura literal de "separar A de B" que podría interpretarse como renombrar ambos campos.

---

## Testing

- **`test_api_keys.py` (nuevo):** creación devuelve la key en texto plano una sola vez;
  `GET` posterior nunca expone `key`/`key_hash`; una key revocada falla `get_current_user`
  con 401 en el siguiente request (no en el actual, si el mismo test la usa después de
  revocar); un JWT sigue funcionando sin cambios (regresión); el rate limit por usuario de
  `POST /transactions` con API key se dispara al superar el umbral (usar `freezegun` o
  múltiples llamadas rápidas, siguiendo el patrón ya usado en `test_auth.py` para límites de
  slowapi si existe uno — revisar precedente antes de escribir el test desde cero).
- **`test_transactions.py` (extender):** `category` por nombre resuelve correctamente
  (case/acento-insensible); `404` con nombre inexistente lista las categorías válidas del
  tipo correcto; `409` cuando el usuario tiene dos categorías propias con el mismo
  nombre+tipo (sembrar el duplicado directamente en el test, ya que la UI no lo permite);
  precedencia propia > sistema; `account_id` omitido resuelve a la única cuenta; `account_id`
  omitido con 2+ cuentas da `400`; XOR de `category`/`category_id` rechaza ambos o ninguno.
- **`test_accounts.py` (extender):** `POST /accounts/{id}/reconcile` sin desviación devuelve
  `discrepancy=0.00`; con una desviación forzada (mutar `balance` directo en el test,
  simulando el bug que el ítem previene) corrige el valor y reporta la discrepancia
  correcta; `opening_balance` se setea igual a `balance` en la creación.
- **Codegen (§16.3):** no requiere test de pytest — se verifica manualmente corriendo
  `pnpm gen:types` contra un backend local y confirmando que el archivo generado compila
  (`tsc --noEmit` ya cubierto por `pnpm build`).

---

## Resumen de estimación de horas

| Ítem | ROADMAP | Ajustado | Motivo del ajuste |
|---|---|---|---|
| 16.1 API keys | 2d (16h) | 2.5d (20h) | Modelo + extensión de `get_current_user` + endpoints + rate limit por usuario + UI de gestión (costo reducido por hallazgo 10, `/settings` ya existe) + tiempo de coordinar la revisión de `security-reviewer` (no incluye la revisión en sí) |
| 16.2 Captura por nombre | 1d (8h) | 1d (8h) | Sin cambio — el análisis confirma que el alcance real (resolución de categoría + `account_id` opcional) cabe en la estimación original, precisamente porque se reusa el endpoint existente sin duplicar lógica contable |
| 16.3 Codegen | 1d (8h) | 0.5d (4h) | Menor de lo estimado: `openapi-typescript` es una sola dependencia + un script; no hay migración de call sites en este ítem (Decisión 16.3.2) |
| 16.4 Reconciliación | 1d (8h) | 1d (8h) | Sin cambio — migración + endpoint + backfill caben en la estimación, el hallazgo principal (backfill no detecta desviación histórica) es una precisión de alcance, no trabajo adicional |
| Documentación cruzada (§16 transversal) | *(no dimensionado aparte)* | 3h | 4 documentos (`API_REFERENCE.md`, `API_CONTRACT.md`, `BUSINESS_RULES.md`, `STATE_AND_FETCHING.md`) + limpieza de `TODO.md` |
| Testing | *(no dimensionado aparte)* | 6h | `test_api_keys.py` nuevo + extensiones de `test_transactions.py`/`test_accounts.py` |
| **Total** | **~5d (40h)** | **~5.4d (43h)** | Ajuste neto pequeño: el ahorro de §16.3 casi compensa el costo agregado de §16.1 (rate limit por usuario + UI) y el trabajo transversal no dimensionado por el ROADMAP |

---

## Resumen de archivos tocados por ítem

| Ítem | Archivos |
|---|---|
| 16.1 API keys | `backend/app/models/models.py` (`ApiKey`), `backend/app/schemas/schemas.py` (`ApiKeyCreate`/`ApiKeyCreateResponse`/`ApiKeyResponse`), `backend/app/core/security.py` (`generate_api_key`, extensión de `get_current_user`), `backend/app/core/rate_limit.py` (`key_func_por_usuario_o_ip`), `backend/app/api/api_keys.py` (nuevo router), `backend/app/main.py` (registrar router), migración Alembic nueva, `frontend/app/(dashboard)/settings/page.tsx` (sección nueva), `frontend/lib/hooks/` (hook nuevo o extensión), `backend/tests/test_api_keys.py` (nuevo) |
| 16.2 Captura por nombre | `backend/app/schemas/schemas.py` (`TransactionBase` con `category`/`account_id` opcionales + validator XOR), `backend/app/api/transactions.py` (`_resolver_categoria_por_nombre`, `_normalizar_nombre_categoria`, resolución de cuenta), `backend/tests/test_transactions.py` (extender) |
| 16.3 Codegen | `frontend/package.json` (script + devDependency), `frontend/types/generated/api.ts` (nuevo, generado, commiteado), `frontend/docs/STATE_AND_FETCHING.md` (sección nueva) |
| 16.4 Reconciliación | `backend/app/models/models.py` (`Account.opening_balance`), `backend/app/schemas/schemas.py` (`AccountReconcileResponse`, `AccountResponse.opening_balance`), `backend/app/api/accounts.py` (`crear_cuenta` setea ambas columnas, endpoint `reconcile` nuevo), migración Alembic nueva con backfill, `backend/tests/test_accounts.py` (extender) |
| Cruzando toda la fase | `backend/docs/API_REFERENCE.md`, `frontend/docs/API_CONTRACT.md`, `backend/docs/BUSINESS_RULES.md`, `docs/TODO.md` (mover/corregir entradas) |

---

## Cierre

Este documento no implementa ningún cambio en el repositorio — es el desglose ejecutable de
la sección "Fase 16" de `docs/ROADMAP.md`. El hallazgo con más impacto práctico es que los
cuatro ítems, pese a estar agrupados bajo un mismo objetivo ("habilitar atajos de
iOS/Android"), tienen perfiles de riesgo muy distintos: §16.1 es el único que toca la
superficie de autenticación compartida por toda la aplicación y el único que este documento
recomienda no cerrar sin una revisión de seguridad explícita (Decisión 16.1.8); §16.2 y §16.4
son extensiones acotadas de código ya existente, con blast radius de un router cada uno; §16.3
es, de los cuatro, el que menos riesgo introduce y el que ya tiene evidencia concreta (no
hipotética) de que resuelve un problema real — el mismatch `Decimal`-como-`string` verificado
contra el `openapi.json` real de este worktree, que ya causó un bug corregido en Fase 15. El
segundo hallazgo con más impacto es que el mecanismo que motiva §16.4 (`Account.balance`
mutado con deltas SQL atómicos, sin ninguna función que calcule "el saldo que debería ser")
ya existe hoy exactamente como lo describe el ROADMAP, y que el backfill de `opening_balance`
solo puede establecer una línea de base limpia hacia adelante, no auditar desviaciones ya
ocurridas — límite que debe quedar documentado en `BUSINESS_RULES.md`, no solo en este spec.
Todos los hallazgos fueron verificados contra el código real de `backend/` y `frontend/` el
2026-09-06, incluyendo la generación en vivo del `openapi.json` de este worktree con el
intérprete del repo principal (`backend/venv`, dado que este worktree no trae su propio
entorno virtual). Ningún archivo del repositorio fuera de `docs/specs/fase_16_spec.md` fue
modificado al producir este documento.
