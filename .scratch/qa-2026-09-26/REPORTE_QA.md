# Reporte QA — Oikos @ bc9dcb9 (2026-09-26)

> **Nota:** las capturas referenciadas (`screenshots/*.png`) no están versionadas (`*.png` en `.gitignore`); quedan solo en la copia local de quien corrió la QA.


Dos pasadas:

1. **Pasada 1:** solo Fase 0. Se detuvo porque el stack local es producción (ver QA-001).
2. **Pasada 2:** Fases 1–3 en un entorno aislado sin Docker.
   - Backend en `127.0.0.1:8001` sobre un archivo SQLite desechable, frontend `pnpm dev` en `:3001`.
   - Se verificó que todas las peticiones del navegador fueron a `:8001`.
   - No se tocaron producción, `*.ts.net` ni `backend/finanzas.db`.

## 1. Resumen ejecutivo

- **Fase 0 en verde:**
  - pytest: 313/313, cobertura del 97%.
  - `pnpm lint`: limpio.
  - No hay tests de frontend ni e2e.
- **Contabilidad correcta en operaciones secuenciales:**
  - Tras crear, editar (monto, cuenta, tipo y fecha a la vez) y borrar, la conciliación de saldos da 0.
  - Los KPIs de Analytics = la suma de buckets = `/transactions` = `category-distribution`, en semana, mes y año, en COP y USD, y en los bordes (31-dic/1-ene, 31-ago/1-sep, domingo/lunes).
- **Aislamiento entre usuarios correcto:** 25 intentos cruzados por API y 2 por UI, todos con 404.
- **Auth completo OK.** El refresh se verificó esperando la expiración real de 15 min.
- **Los 3 problemas más graves:**
  - **QA-003 🔴:** operaciones concurrentes descuadran el saldo.
  - **QA-004 🟠:** un 422 de validación tumba la página entera.
  - **QA-005 🟠:** el onboarding de moneda e ingreso nunca aparece tras registrarse con contraseña.

## 2. Bugs

### 🔴 Crítico

**QA-003 — Condición de carrera en DELETE/PUT de transacciones descuadra el saldo** (confirmado en SQLite)
- **Pasos:** lanzar 8 `DELETE /transactions/{id}` en paralelo sobre la misma transacción.
- **Obtenido:** 6 respuestas 200. Saldo final 100.050,00 en vez de 100.000,00 (discrepancia −50). Con 8 PUT paralelos, la discrepancia fue de 35,00.
- **Esperado:** el delta se aplica una sola vez. El backend es la fuente de verdad de los saldos (CLAUDE.md).
- **Causa:** `backend/app/api/transactions.py:278-297` (y el PUT) lee sin lock y actualiza sin condición. No hay `with_for_update` en ningún lugar del backend.
- **Alcance:**
  - Por lectura de código, el mismo patrón falla en Postgres con READ COMMITTED. No se reprodujo en Postgres.
  - En la UI, el doble clic solo manda 1 DELETE. El riesgo real viene de reintentos, varias pestañas o clientes con API key.

### 🟠 Alto

**QA-004 — Un 422 con `detail` en forma de lista tumba la página** (confirmado)
- **Pasos:** monto `0.001` en /capture, o `12.345` en el modal de transacción.
- **Obtenido:**
  - El backend responde 422 con `detail: [...]`.
  - `getApiError` (`frontend/lib/utils.ts:3-6`) pasa esa lista a `toast.error`.
  - React falla con "Objects are not valid as a React child", aparece "This page couldn't load" y se pierde lo escrito en el formulario.
- **Alcance:** `getApiError` se usa en 13 archivos.
- **Evidencia:** `screenshots/QA-004_crash_422_capture.png`

**QA-005 — El onboarding (moneda + ingreso) nunca aparece para registros con contraseña** (confirmado)
- **Pasos:** registro → el auto-login devuelve 403 `EMAIL_NOT_VERIFIED` → `/login?registered=true` → verificar → login → llega a `/capture` **sin `?onboarding=1`**.
- **Causa:**
  - El único push a `/capture?onboarding=1` está en `app/(auth)/register/page.tsx:71`, dentro de un auto-login que siempre falla desde que la verificación de email es obligatoria (2026-09-12).
  - `app/(auth)/login/page.tsx:85-87` manda a `/capture` sin el flag.
- **Alcance:** forzando `?onboarding=1` a mano, el wizard funciona bien.
- **Evidencia:** `screenshots/QA-005_capture_sin_onboarding.png`

### 🟡 Medio — tocan dinero

**QA-006 — `GET /transactions` cuenta las transacciones borradas en `total`**
- **Causa:** `transactions.py:261`. `with_entities(func.count())` se salta el filtro global de soft-delete.
- **Obtenido:** la lista muestra "Cargar más (12 de 17)" para siempre, y cada clic trae una página vacía.
- **Evidencia:** `screenshots/qa_tx_total_incluye_borradas.png`

**QA-007 — Todos los montos se redondean a la unidad, también USD/EUR**
- **Causa:** `formatters.ts`.
- **Obtenido:** un gasto de 0,10 se muestra como "-US$ 0", y la tarjeta muestra "Te quedan 2.955" con Ingresos 3.000 y Gastos 46.

**QA-008 — "Te quedan" no cuadra con "Ingresos del Mes"**
- **Causa:** "Te quedan" usa el ingreso *declarado*, mientras que la tarjeta muestra el ingreso *real* (3.200).
- **Obtenido:** 3.200 − 106 ≠ 2.894.
- **Evidencia:** `screenshots/qa_dashboard_card_no_cuadra.png`

**QA-009 — Transacción con categoría de otro tipo**
- Al editar un gasto y cambiarlo a Ingreso, la UI muestra "Salario" pero envía el `category_id` de Mercado, y el backend lo acepta.
- También se acepta cambiar la "Naturaleza" de una categoría que ya tiene movimientos.

**QA-011 — Detalle de cuenta y categoría truncado a 100 movimientos**
- Afecta a `/accounts/[id]` y `/categories/[id]`: no hay paginación ni aviso. Probado con 103 y 110 movimientos.

**QA-012 — `BudgetRing` topa el porcentaje en 100%**
- Muestra "100% GASTADO" con un gasto real de 105,5%. La notificación, en cambio, dice 106%.

**QA-015 — Sin límite de dígitos en los montos** (no confirmado en Postgres)
- El schema no define `max_digits`, y en SQLite se aceptan 13 dígitos.
- En Postgres, `Numeric(14,2)` probablemente terminaría en un 500.

### 🟡 Medio — otros

**QA-010 — Un error de la API en `/transactions` se muestra como "Aún no tienes movimientos"**
- La UI permite un rango de fechas invertido sin avisar.
- Durante los reintentos, los filtros desaparecen tras un esqueleto.
- Es la misma clase de bug que la Fase 24 arregló en el dashboard.
- **Evidencia:** `screenshots/qa_tx_error_como_vacio.png`, `screenshots/qa_tx_rango_invertido.png`

**QA-013 — Paso de ingreso del onboarding sin mensaje de error**
- Con un valor negativo o vacío, "Continuar" no hace nada y no aparece ningún mensaje.

**QA-014 — Accesibilidad de modales y categorías**
- `ModalShell` no tiene `role="dialog"` ni gestión de foco: al abrirlo con teclado, el foco queda fuera del modal.
- Los botones de editar/borrar categoría son invisibles al foco en escritorio.

**QA-016 — Seed descuadrado y docs desactualizadas**
- El seed deja las cuentas descuadradas respecto a `opening_balance` (2.519.000 COP, 2.735 USD, −150.000 COP).
- CLAUDE.md dice que el seed crea 45 transacciones; en realidad crea 76.

**QA-002 — Usuario semilla con contraseña conocida en la base de producción** — **RESUELTO 2026-09-26**
- Hallazgo: `test@test.com` (id 18) estaba en la base de producción desde el 2026-09-25, con 3 cuentas, 75 transacciones y 6 presupuestos.
- Se borró con `delete_user_by_email`.
- Quedan solo los ids 15 y 17.

### 🟢 Bajo

- **QA-017:** hydration mismatch en `/settings` (solo en dev).
- **QA-018:**
  - "Entretenimiento" desborda su casilla en /capture a 390 px.
  - Flujo de Caja vacío, sin mensaje.
  - Unos 7 s en blanco ante un 404 de un recurso ajeno.
  - Descripción obligatoria solo en el modal.
  - "Último uso: Nunca" desactualizado en la lista de API keys.

### Entorno

**QA-001 — El entorno "dev" comparte base de datos, puertos y nombre de proyecto con producción** — 🟠 Alto
- `docker-compose.dev.yml` solo cambia `command`, `COOKIE_SECURE` y los volúmenes del frontend. Mantiene el volumen `pgdata`, los puertos 3000/8000 y el nombre de proyecto `app-finanzas-fullstack`.
- Correr el comando dev de CLAUDE.md reemplaza los contenedores de producción y escribe en la base real.
- **Workaround usado (funcionó):** backend sin Docker con `DATABASE_URL` apuntando a SQLite en un directorio aparte, en 8001/3001. Receta en la memoria del proyecto y en `docs/TODO.md` (QA-001).
- **Arreglo de fondo:** un override con proyecto, volumen y puertos propios.

## 3. Matriz de cobertura

| Flujo | Estado |
|---|---|
| Fase 0: pytest + lint | OK |
| Auth (registro, verificación, login, refresh, logout, reset, tokens reusados) | OK |
| Onboarding | Bug: QA-005, QA-013 |
| Estados vacíos | OK, con detalles en QA-010 y QA-018 |
| /capture | Bug: QA-004. Validación y doble clic OK |
| Transacciones + consistencia de saldos | OK en secuencial. Bugs: QA-003 (concurrencia), QA-009 |
| Filtros / "Esta semana" | OK. Bugs: QA-006, QA-010 |
| Multimoneda | OK, nunca mezcla monedas |
| Presupuestos | OK. Bug: QA-012 |
| Dashboard `?month=` | OK |
| Tarjeta principal del dashboard | Bug: QA-007, QA-008 |
| Analytics `?ref=` / KPIs | OK |
| Categorías | OK. Bug: QA-009 |
| Cuentas | OK. Bug: QA-011 |
| Ajustes / API keys / borrado de cuenta | OK |
| Aislamiento entre usuarios | OK |
| Móvil 390×844 | OK, con detalles 🟢 |
| Teclado | Login OK. Modal con bug: QA-014 |
| Push real, resumen semanal, botón atrás, `GET /budgets/?month=&year=` | No probado |

## 4. Observaciones (no bugs)

- **Artefactos de SQLite:**
  - Las fechas llegan sin zona horaria y el navegador las muestra 5 h adelantadas. En Postgres (`timestamptz`) deberían venir con offset.
  - Los saldos se guardan como REAL (`3183.19921875`), pero la API los devuelve bien redondeados.
- **Fecha por defecto del modal:** usa el día UTC, así que a las 19:43 en Bogotá propone el día siguiente. Es otra cara del ítem conocido de UTC en el TODO.
- **Ingreso mensual sin moneda propia:** al cambiar la moneda principal, el ingreso declarado se reinterpreta en la nueva moneda. Está documentado en la Fase 22, pero Ajustes no avisa.
- **Transferencias:** no existen como tipo; solo hay el tag `payment_method=transfer`.
- **Idempotencia:** aguanta bajo concurrencia (6 POST paralelos con la misma clave crearon 1 sola transacción).
- **Cobertura baja:**
  - `core/email.py` 45% (la rama SMTP real no tiene tests).
  - `core/user_deletion.py` 74%.
  - `core/weekly_summary.py` 77%.
  - `main.py` 78%.
  - `api/transactions.py` 84%, justo el módulo que muta saldos.
- **Advertencias de pytest:**
  - `SAWarning` por coerción de Subquery en `app/api/dashboard.py:128,145`.
  - `DeprecationWarning` en `main.py:188,202`.
  - `passlib` usa `crypt`, que se elimina en Python 3.13.
- **pnpm:** `pnpm.onlyBuiltDependencies` en `package.json` ya no lo lee pnpm 11.

## 5. Bugs de docs/TODO.md confirmados vigentes

- **Filtro de cuentas destacadas inconsistente:** en agosto, la tarjeta de gastos da $693.000 y las barras suman $893.000.
- **Mes y semana en UTC** frente a la hora de Bogotá.
- **Google OAuth:** sin client ID el botón no aparece, que es la degradación correcta.
- **Fixes de Fase 30 verificados como resueltos:** redirección del login a `/`, invalidación del dashboard al cambiar moneda y KPIs calculados en el backend.

## Estado del entorno al cerrar

- Procesos de 8001/3001 detenidos. Los contenedores de producción siguen Up.
- `git status`: solo `?? .scratch/`.
- Los archivos de entorno (base SQLite, logs, `env.sh`) se borraron el 2026-09-26 tras registrar los hallazgos.

---

# Pasada 3 — Re-verificación contra Postgres 16 (2026-09-26)

- **Entorno:** contenedor `postgres:16-alpine` suelto en `127.0.0.1:5433`, con los datos en tmpfs (se borran al detenerlo). Backend en `:8001` y frontend en `:3001`.
- **Aislamiento verificado:** el seed quedó en ese Postgres y el navegador llamó a `:8001`. Producción no se tocó.
- **Logs:** borrados tras registrar los hallazgos.

| Ítem | Veredicto en Postgres | Evidencia |
|---|---|---|
| QA-003 🔴 | **CONFIRMADO**, y en el caso mixto es peor que en SQLite | **DELETE ×8:** 1–5 respuestas 200 por ronda, discrepancia = (n200−1)×50 (hasta +200). **PUT ×8:** 8/8 respuestas 200, discrepancia −15 a −135. **4 PUT + 4 DELETE:** la transacción queda borrada con el monto editado. `reconcile` confirma cada discrepancia |
| QA-015 → 🟠 | **CONFIRMADO: 500** | 13 dígitos → 500 en transacciones, cuentas y `users/me` (en las dos últimas, excepción no controlada). Con la cuenta en 999.999.999.999,99, un ingreso de 1,00 también da 500 (`NumericValueOutOfRange`). El rollback funciona |
| QA-006 | **CONFIRMADO** | `total` 110 vs 101 items reales (9 borradas) |
| Fechas (artefacto SQLite) | **No existe en Postgres** | `timestamptz`, la API devuelve fechas con `Z` y la UI las muestra a la hora correcta de Bogotá (`screenshots/pg_tx_horas_bogota.png`) |
| Saldos (artefacto SQLite) | **No existe en Postgres** | `numeric(14,2)` exacto: 1947.71 en la columna, en la API y en `reconcile` |
| Bordes de periodo | **OK, 18/18** | 9 periodos × 2 monedas: KPI = buckets = `/transactions` = `category-distribution` |
| Idempotencia, payload idéntico | **OK** | 6 POST paralelos → 1 fila, delta aplicado una vez |

## Bugs nuevos

- **QA-021 🟠 — Bucle infinito de recargas en `/login` con una cookie `csrf_token` huérfana**
  - **Obtenido:** unas 5 recargas por segundo y 157 respuestas 401 de `/auth/refresh`. No se puede iniciar sesión.
  - **Causa:**
    - `UserPreferencesSync` activa la query de preferencias con `haySesionActiva()`, que solo mira si existe `csrf_token`.
    - El interceptor de `lib/api.ts:71` redirige a `/login` aunque ya esté en `/login`.
    - El 401 de `/auth/refresh` no limpia las cookies.
  - **Alcance:** no depende del motor de base de datos.
- **QA-019 🟢 — Un ingreso registrado en el último segundo del mes desaparece del dashboard de ese mes**
  - **Obtenido:** con un ingreso de 3.300 a las `2025-12-31T23:59:59.999Z`, `/?month=2025-12` muestra "Ingresos $0", aunque la lista de la misma página muestra el ingreso.
  - **Causa:** `periods.py:80` usa como techo del mes `23:59:59` sin fracción de segundo.
  - **Evidencia:** `screenshots/pg_dashboard_2025-12_ingreso_perdido.png`
- **QA-020 🟢 — La misma Idempotency-Key con payloads distintos, en carrera, devuelve 200 con una transacción ajena en vez de 409**
  - **Causa:** la rama `except IntegrityError` no compara `request_hash`.
- **QA-022 🟢 — Riesgo latente: `cashflow-series` y `summary` asumen que la sesión Postgres está en UTC**
  - Hoy no aplica, porque la imagen usa UTC por defecto.

## Nota de montaje

Sobre una base recién migrada, el seed hay que correrlo después del primer arranque del backend. Las categorías del sistema las siembra `main.py`; sin ellas, el seed crea solo 1 presupuesto y 9 transacciones. Anotado en QA-016.

## Estado del entorno

- Contenedor `oikos-qa-pg` detenido; sus datos se borraron.
- Puertos 8001, 3001 y 5433 libres.
- Contenedores de producción Up y healthy.
- Sin cambios en archivos versionados.
