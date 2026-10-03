# Spec — Fase 30: Semana calendario en Transacciones y deuda chica post-Fase 29

> Sintetiza el `/grilling` del 2026-09-26, registrado en `docs/archive/ROADMAP_fases_26-32.md` §"Fase 30 — planificada"
> (decisiones **Q1–Q10** y 4 supuestos aceptados). Esas decisiones las tomó el dueño y esta spec
> no las reabre. Las cita por su número y las baja a decisiones implementables **B** (backend),
> **F** (frontend), **T** (testing) y **D** (docs), con la misma convención que `fase_29_spec.md`.
>
> Antes de escribirla se contrastó el grilling con el código real (2026-09-26). Hay cuatro
> hallazgos que precisan cómo se implementan Q6 y Q8. Ninguno cambia alcance ni contrato más
> allá de lo decidido, así que se resolvieron como decisiones y no como marcadores (ver
> "Hallazgos de exploración").
>
> **No implementa nada.** Solo se agregó este archivo y el pointer en `docs/ROADMAP.md`.

**Estado:** implementada y cerrada el 2026-09-26 (`/analyze-spec 30` antes y al cierre). Los
desvíos quedaron registrados en la entrada de la Fase 30 de `docs/CHANGELOG.md`.

---

## Problem Statement

En `/transactions` el chip "Últimos 7 días" es una ventana móvil, mientras que Analítica, desde la
Fase 29, habla de "Esta semana" como semana calendario lunes → hoy. Las dos pantallas llaman
"semana" a cosas distintas. Además, los presets de `/transactions` arman sus fechas mezclando la
hora local del navegador con UTC. Es el mismo tipo de bug que la Fase 29 corrigió en el
dashboard: después de las 19:00 hora Bogotá, "Este mes" puede arrancar en un mes y terminar en
otro.

La Fase 29 también dejó anotados en `docs/TODO.md` cinco problemas chicos en las mismas
pantallas:

- Al cambiar la moneda preferida, la tarjeta de flujo del dashboard sigue mostrando sumas de la
  moneda vieja hasta que el cache vence.
- El login (con contraseña o con Google) de un usuario con historial manda a `/dashboard`, que da
  404.
- El saludo del dashboard dice siempre "Buenas tardes" y produce un hydration mismatch.
- Los KPIs de Analítica (ingresos, gastos, balance) se suman en el navegador, en contra de la regla
  de que el backend es la fuente de verdad de los agregados.
- La tarjeta del mes de una cuenta cuenta transacciones con fecha futura del mes en curso, y la del
  dashboard no.

## Solution

- **Chip "Esta semana"** en `/transactions` en lugar de "Últimos 7 días": del lunes de la semana
  en curso a hoy, en UTC, igual que Analítica. Los tres presets (semana, mes, año) calculan sus
  fechas con el mismo módulo de períodos que usa Analítica, así que desaparece la mezcla
  local/UTC.
- **KPIs de Analítica desde el backend**: `GET /dashboard/cashflow-series` pasa a devolver un
  objeto con los buckets y los totales del período (`total_income`, `total_expense`, `net`). La
  tarjeta de KPIs y la dona muestran esos números sin sumar nada en el cliente.
- **Techo unificado** en la tarjeta del mes de una cuenta: el mes en curso se corta en "ahora",
  con el mismo helper que el dashboard.
- **Arreglos chicos**: cambiar la moneda preferida refresca todo el dashboard, el login lleva a
  `/`, y el saludo depende de la hora local ("Buenos días", "Buenas tardes", "Buenas noches") sin
  hydration mismatch.

## User Stories

**Transacciones: chip "Esta semana"**

1. Como dueño, quiero un chip "Esta semana" en `/transactions`, para ver lo que registré desde el
   lunes sin armar un rango a mano.
2. Como dueño, quiero que "Esta semana" empiece el lunes y termine hoy, para que coincida con lo
   que me muestra "Esta semana" en Analítica.
3. Como dueño, quiero que "Esta semana" reemplace a "Últimos 7 días", para no tener dos chips que
   dicen casi lo mismo.
4. Como dueño, quiero que los chips sigan siendo cuatro y entren en una fila en el celular, para
   que el filtro no crezca.
5. Como dueño, quiero que "Esta semana" quede en la URL (`?preset=week`), para recargar y caer en
   el mismo filtro.
6. Como dueño, quiero que un link viejo con `?preset=7d` me muestre todo el histórico en vez de
   romper la página, para no quedar en un estado raro.
7. Como dueño, quiero que "Este mes" arranque el día 1 del mes correcto aunque abra la página de
   noche, para no ver transacciones de otro mes mezcladas.
8. Como dueño, quiero que "Este mes" y "Este año" de `/transactions` usen los mismos bordes que
   Analítica, para que el total de un período cuadre entre las dos pantallas.
9. Como dueño, quiero que al editar las fechas a mano el chip resaltado pase a ninguno, como hasta
   ahora, para saber que estoy en un rango personalizado.
10. Como dueño, quiero que "Limpiar filtros" siga volviendo a "Todo el histórico", para no perder
    ese atajo.

**Analítica: KPIs desde el backend**

11. Como dueño, quiero que los ingresos, gastos y balance del período en Analítica vengan del
    backend, para confiar en que son los mismos números que calcula el servidor.
12. Como dueño, quiero que el balance del período sea exactamente ingresos − gastos del período,
    para que la tarjeta cuadre consigo misma.
13. Como dueño, quiero que la dona en modo "% del ingreso" use el mismo total de ingresos que la
    tarjeta de KPIs, para que los porcentajes cuadren con el número de arriba.
14. Como dueño, quiero que los KPIs respeten la cuenta y la moneda elegidas, igual que hoy, para no
    perder los filtros de la Fase 17 y la Fase 29.
15. Como dueño, quiero que un período sin movimientos muestre ingresos, gastos y balance en cero,
    para no ver un error ni una tarjeta vacía.
16. Como dueño, quiero que el gráfico de barras se vea igual que hoy, para que el cambio de
    contrato no se note en la pantalla.

**Cuentas: tarjeta del mes**

17. Como dueño, quiero que la tarjeta del mes de una cuenta no cuente una transacción que fecheé
    para más adelante en el mes, para que cuadre con la tarjeta del dashboard.
18. Como dueño, quiero que las transacciones de hoy sigan contando en la tarjeta de la cuenta, para
    que lo que acabo de registrar se vea.

**Moneda preferida**

19. Como dueño, quiero que al cambiar mi moneda preferida la tarjeta de flujo del dashboard
    muestre las sumas en la moneda nueva de inmediato, para no ver un rótulo en COP con montos en
    USD.
20. Como dueño, quiero que los presupuestos y "Gastos por categoría" del dashboard también se
    refresquen al cambiar la moneda, para que todo el dashboard hable de la misma moneda.
21. Como dueño, quiero que esto valga para cualquier mes que haya navegado, no solo para el actual,
    para no encontrarme datos viejos al volver a un mes pasado.

**Login**

22. Como dueño con historial, quiero que el login con contraseña me lleve al dashboard, para no
    caer en un 404 después de iniciar sesión.
23. Como dueño con historial, quiero que el login con Google me lleve al dashboard, por lo mismo.
24. Como usuario nuevo, quiero que el login me siga llevando a `/capture`, como hasta ahora.

**Saludo del dashboard**

25. Como dueño, quiero que el saludo diga "Buenos días" de 5:00 a 11:59, para que no me diga
    "Buenas tardes" a las 7 de la mañana.
26. Como dueño, quiero "Buenas tardes" de 12:00 a 18:59 y "Buenas noches" de 19:00 a 4:59, según
    la hora de mi dispositivo.
27. Como dueño, quiero que el saludo use mi primer nombre, como hasta ahora.
28. Como dueño, quiero que la página no se regenere entera al cargar por culpa del saludo, para que
    la consola de desarrollo quede limpia y el primer render no parpadee.

## Hallazgos de exploración

Contraste del grilling con el código del 2026-09-26.

**H1. No hay un prefijo de key `dashboard` común (afecta Q8).** Las queries del dashboard tienen
raíces distintas: `['dashboardSummary', month?]`, `['dashboard-category-breakdown', month?,
currency?]` y `['budgets-progress', month?]`. "Invalidar todo el prefijo `dashboard`" no se puede
hacer con una sola llamada: hay que invalidar las tres raíces, que por la regla de segmentos
opcionales de `lib/queryKeys.ts` matchean todos los meses cacheados. Ver F4.

**H2. Las queries de Analítica no necesitan invalidación por moneda (afecta Q8).** Sus keys ya
llevan `effectiveCurrency` como segmento, y `effectiveCurrency` se deriva de
`currentUser.preferred_currency`, que ya se invalida. Al cambiar la moneda preferida la key
cambia y TanStack pide la nueva sola. Del lado del backend, `preferred_currency` solo se usa de
forma implícita en `summary` (orden y `monthly_flow_balance`) y como default de
`cashflow-series`/`category-distribution`, que Analítica nunca usa porque siempre manda
`currency`. `budgets-progress` no depende de la moneda preferida en el backend, pero entra en la
invalidación porque Q8 pide todo el dashboard y el costo es un refetch.

**H3. El balance de Analítica también se calcula en el cliente (afecta Q6).** Además del
`useMemo` de `totals` en `analytics/page.tsx`, `AnalyticsSummary` calcula el balance como
`totalIncome - totalExpense`. Q6 trae `net` del backend, así que el componente pasa a recibirlo
por prop en vez de restar.

**H4. El test de equivalencia de la Fase 19 apunta a los totales del cliente (afecta Q6).**
`TestCategoryDistributionCashflowEquivalence` (`tests/test_dashboard.py`) prueba que la suma de
`category-distribution` (ingresos) es igual a la suma de los buckets de `cashflow-series`, porque
el cliente usaba esa suma como denominador de la dona. Con Q6 el denominador es `total_income`, y
el invariante se reescribe contra ese campo (T3).

Además, para ubicar el trabajo: `frontend/` no tiene test runner (ni Vitest ni Jest), así que la
verificación del frontend es con Playwright, como en la Fase 29 (supuesto 3). Regenerar
`types/generated/api.ts` (`pnpm gen:types`) necesita el backend corriendo en `:8000`.

## Implementation Decisions

### Backend

**B1. `cashflow-series` responde un objeto con buckets y totales (Q6).**

- Nuevo schema de respuesta en el módulo de schemas de dashboard, junto a `CashflowData` (que no
  cambia y pasa a ser el tipo de cada bucket):

  ```
  CashflowSeries:
    buckets: list[CashflowData]   # misma forma y orden que la lista de hoy
    total_income: Decimal
    total_expense: Decimal
    net: Decimal                  # total_income - total_expense
  ```

- El `response_model` del endpoint pasa de `list[CashflowData]` a `CashflowSeries`. Los parámetros
  (`start_date`, `end_date`, `period`, `currency`, `account_id`), el chequeo de pertenencia de la
  cuenta (404), el default de moneda y el `InternalServerError` ante fallas de consulta no
  cambian.
- Los totales se calculan en Python sumando los `Decimal` de las filas ya agrupadas, no con una
  segunda query. Así los totales son por construcción la suma de los buckets con los mismos
  filtros, y el invariante con `category-distribution` (H4) no depende de mantener dos consultas
  alineadas.
- Un rango sin transacciones responde `buckets: []` y los tres totales en `0.00`, nunca `null`.
- El shim `schemas.py` re-exporta con imports explícitos y `__all__`, no con `*`: `CashflowSeries`
  se agrega a los dos, así el router lo usa como `schemas.CashflowSeries`, igual que el resto.
- Cambio de forma que rompe el contrato: aceptado en Q6 porque el único consumidor es Analítica y
  no hay atajos ni scripts propios que lean el endpoint. No hay versionado ni alias de la forma
  vieja.

**B2. `monthly-summary` usa `limites_mes_utc` (Q7).**

- `GET /accounts/{id}/monthly-summary` reemplaza el cálculo a mano del mes (primer día y último
  día a las 23:59:59) por `core.periods.limites_mes_utc(año, mes, ahora)` con el mes UTC en curso.
  En el mes en curso el techo pasa a ser "ahora", igual que `dashboard/summary`.
- Sin `?year=&month=`: el endpoint sigue sin parámetros de período (Q7). Tampoco se llama a
  `resolver_mes`, porque no hay entrada de usuario que validar.
- El resto no cambia: pertenencia con 404, filtro `deleted_at`, forma de la respuesta y balance
  nunca `null`.
- Si el import de `calendar` queda sin uso en el módulo, se elimina.

### Frontend

**F1. `lib/dateRanges.ts` expone los bordes del período en curso (Q1).**

- Nueva función exportada que devuelve las fechas `YYYY-MM-DD` del período de calendario en curso
  para `week | month | year`: inicio = `periodStartUtc(period, now)`, fin = el día UTC de hoy
  (`utcDayKey(now)`). Encapsula el criterio en el módulo en vez de exportar `periodStartUtc`
  suelto, para que `/transactions` no arme fechas por su cuenta.
- El fin es hoy, no el domingo ni el último día del mes (supuesto 1): mismo corte que el período en
  curso de Analítica.
- Todo con getters UTC, según el contrato del módulo. Módulo puro, `now` inyectado.

**F2. Chip "Esta semana" en `/transactions` (Q1, Q2).**

- `DatePreset` pasa a `'all' | 'week' | 'month' | 'year' | 'custom'`. `'7d'` desaparece del
  tipo, de la lista de chips, de la whitelist de `validatePreset` y de la condición del efecto de
  montaje que deriva fechas desde el preset.
- Chips, en este orden: `Todo el histórico`, `Esta semana`, `Este mes`, `Este año`.
- `getPresetDates` delega en F1 para `week`/`month`/`year` y devuelve vacío para `all`. Desaparece
  la mezcla de `getFullYear()`/`getMonth()`/`setDate` con `toISOString()`.
- `?preset=7d` no está en la whitelist y cae a `all` (Q2), sin alias ni reescritura de la URL.
- No cambia: la conversión a `T00:00:00` / `T23:59:59` hacia el backend, el paso a `custom` al
  editar fechas a mano, "Limpiar filtros", ni el link "Ver todas" del dashboard
  (`preset=custom`).
- Sin `◀ ▶` (Q3).

**F3. Analítica consume los totales del backend (Q6).**

- `types/api.ts`: nueva interfaz `CashflowSeries { buckets: CashflowItem[]; total_income: number;
  total_expense: number; net: number }` (los `Decimal` llegan como string o número y se convierten
  con `Number(...)`, igual que los buckets hoy). `types/generated/api.ts` se regenera con
  `pnpm gen:types` (supuesto 2).
- `analytics/page.tsx`: la query de `cashflow-series` pasa a leer `res.data.buckets` para el
  gráfico y los tres totales para los KPIs. Se elimina el `useMemo` de `totals`. La key de la
  query no cambia.
- `AnalyticsSummary` recibe `net` por prop y deja de restar (H3). Las props de ingresos y gastos
  siguen, alimentadas por `total_income`/`total_expense`.
- `CategoryDonutChart` en modo `income-total` usa `total_income` del backend como denominador
  (`totalIncomeForPeriod`). Se actualiza el comentario de la prop que dice que el total sale de
  sumar la serie.

**F4. Invalidación completa al cambiar la moneda preferida (Q8, H1, H2).**

- En `useUserPreferences`, cuando el body trae `preferred_currency`, además de `currentUser()` se
  invalidan las tres raíces del dashboard: `dashboard.summary()`, `dashboard.categoryBreakdown()`
  y `budgets.progress()`. Llamadas sin argumento, así matchean por prefijo todos los meses (y
  monedas) cacheados.
- Analítica no se invalida explícitamente: su key ya lleva la moneda efectiva (H2). Se deja un
  comentario en el hook que lo explique, para que nadie la agregue "por las dudas".

**F5. El login redirige a `/` (Q4).**

- `login/page.tsx` y `GoogleAuthButton` cambian el destino con historial de `'/dashboard'` a
  `'/'`. Los destinos sin historial (`/capture`, `/capture?onboarding=1`) y los fallbacks no
  cambian. Se actualizan los comentarios que citan el destino.

**F6. Saludo por franja horaria, sin hydration mismatch (Q5, Q9).**

- El saludo del dashboard se calcula en el cliente después del montaje, con la hora local del
  navegador (`getHours()`, a propósito: es un saludo, no un borde de datos). Franjas:
  - 5:00–11:59 → "Buenos días"
  - 12:00–18:59 → "Buenas tardes"
  - 19:00–4:59 → "Buenas noches"
- Antes del montaje (y en el render del servidor) el encabezado dice **"Hola"**, sin nombre, para
  que server y cliente rendericen lo mismo (Q9).
- Después del montaje: `"{saludo}, {primer nombre}"`, o solo `"{saludo}"` si no hay nombre. El
  fallback `"de nuevo"` desaparece: era la mitad del mismo mismatch.
- "Montado" se detecta con `useSyncExternalStore` (snapshot de servidor `false`, de cliente
  `true`), no con `useState` + `useEffect`. Evita otro
  `eslint-disable react-hooks/set-state-in-effect`. *(Corregido al cerrar: sí hay un
  re-render al hidratar, porque el snapshot de servidor difiere del de cliente; es el costo
  esperado y no produce mismatch.)* La franja se
  resuelve en una función pura (hora → saludo), así se puede leer y revisar sin montar la página.
- El saludo no se reprograma para cambiar solo al cruzar una franja con la página abierta: se
  recalcula en el siguiente render.

### Docs

**D. Documentación del cambio.**

- Contrato de `cashflow-series` (supuesto 2): nueva forma de la respuesta, totales, caso vacío y
  el hecho de que rompe la forma anterior. En `backend/docs/API_REFERENCE.md` y
  `frontend/docs/API_CONTRACT.md` en el mismo cambio.
- `monthly-summary` en `backend/docs/API_REFERENCE.md`: el techo del mes en curso es "ahora".
- `frontend/docs/STATE_AND_FETCHING.md`: invalidaciones al cambiar la moneda preferida (F4) y por
  qué Analítica no las necesita.
- `frontend/docs/COMPONENTS_GUIDE.md`: prop `net` de `AnalyticsSummary` y origen del denominador
  de `CategoryDonutChart`.
- Menciones de `cashflow-series` como lista en `frontend/docs/ARCHITECTURE.md` y
  `backend/docs/FRONTEND_INTEGRATION.md`, si describen la forma de la respuesta.
- Al cerrar (supuesto 4): marcar como resueltos en `docs/TODO.md` los cinco ítems que entran
  (invalidación por moneda, redirect a `/dashboard`, hydration del saludo, KPIs en el navegador,
  techo de `monthly-summary`), con fecha. Entrada en `docs/CHANGELOG.md` y estado en
  `docs/ROADMAP.md`.

## Testing Decisions

Un buen test acá prueba comportamiento observable desde afuera: la respuesta HTTP de un endpoint
para un conjunto de transacciones dado, o lo que ve el usuario en la pantalla. No prueba cómo se
calcula por dentro (por ejemplo, que los totales se sumen en Python y no en SQL).

Seams, del más alto al más bajo:

- **Backend: la API HTTP vía `TestClient`**, con los fixtures existentes (`auth_headers`,
  `make_account`, `make_category`, `_create_transaction`). Es el mismo seam que ya usan los tests
  de `cashflow-series` y `monthly-summary`. Sin seams nuevos.
- **Frontend: la app real con Playwright**, porque no hay test runner de frontend. Sin tests
  unitarios nuevos de `dateRanges.ts` ni del saludo: agregarlos requeriría instalar un runner, que
  queda fuera de alcance.

**T1. `cashflow-series` (B1)**, en `tests/test_dashboard.py`:

- Los tests existentes del endpoint se adaptan a la nueva forma (`response.json()["buckets"]` en
  lugar de la lista).
- `total_income` y `total_expense` son iguales a la suma de los buckets, y `net` es su diferencia,
  con transacciones en varios días del rango.
- Los totales respetan `currency`: una transacción en USD no entra en los totales de COP.
- Los totales respetan `account_id`: una transacción de otra cuenta no entra.
- Un rango sin transacciones responde `buckets == []` y totales en `0.00`.

**T2. `monthly-summary` (B2)**, en `tests/test_accounts.py`:

- Una transacción con fecha futura dentro del mes en curso no cuenta en `monthly_income` ni en
  `monthly_expense`. Mismo helper y mismo `skip` que
  `TestFutureDatedTransactionExcludedFromCurrentMonth._fecha_futura_mismo_mes`: el último día del
  mes no hay "futuro dentro del mes".
- Una transacción de hoy sí cuenta (regresión del caso normal).
- Los tests existentes (pertenencia, 404, balance) siguen pasando sin cambios.

**T3. Invariante de equivalencia (H4).** `TestCategoryDistributionCashflowEquivalence` compara la
suma de `category-distribution` (ingresos) con `total_income` de `cashflow-series`, en vez de
sumar los buckets. Se actualiza el docstring: el denominador de la dona ya no se suma en el
cliente.

**T4. Verificación manual con Playwright**, en desktop y 390×844 (supuesto 3):

- `/transactions`: los cuatro chips, "Esta semana" filtra del lunes a hoy, `?preset=week` al
  recargar, `?preset=7d` cae a "Todo el histórico", los chips entran en el ancho móvil.
- Analítica: KPIs y dona con los mismos números que antes del cambio para un período con datos, y
  en cero para un período vacío.
- Dashboard: saludo según la hora, sin warning de hydration en la consola de dev.
- Settings: cambiar la moneda preferida y volver al dashboard muestra la tarjeta ya en la moneda
  nueva, sin esperar al `staleTime`.
- Login con contraseña de un usuario con historial cae en `/`. El login con Google no se puede
  verificar mientras el cliente OAuth siga deshabilitado (ver `CLAUDE.md`): se revisa en código.

**T5. Suite completa**: `pytest`, `ruff check`/`ruff format`, `pnpm lint`, `pnpm format`
(`/run-tests`).

## Orden de ejecución

```
1. [backend] app/schemas/dashboard.py + schemas.py (shim) + app/api/dashboard.py (cashflow-series) + tests/test_dashboard.py
   — Decisiones B1, T1, T3.
   Depende de: —
2. [backend] [P] app/api/accounts.py (monthly-summary) + tests/test_accounts.py — Decisiones B2, T2.
   Depende de: —
3. [docs] backend/docs/API_REFERENCE.md + frontend/docs/API_CONTRACT.md (+ ARCHITECTURE.md /
   FRONTEND_INTEGRATION.md si describen la forma) — Decisión D (contrato).
   Depende de: 1, 2
4. [frontend] [P] lib/dateRanges.ts + components/transactions/TransactionFilters.tsx +
   app/(dashboard)/transactions/page.tsx — Decisiones F1, F2.
   Depende de: —
5. [frontend] types/api.ts + types/generated/api.ts (pnpm gen:types) + app/(dashboard)/analytics/page.tsx
   + components/AnalyticsSummary.tsx + components/CategoryDonutChart.tsx — Decisión F3.
   Depende de: 1   (gen:types necesita el backend de 1 corriendo)
6. [frontend] [P] lib/hooks/useUserPreferences.ts — Decisión F4.
   Depende de: —
7. [frontend] [P] app/(auth)/login/page.tsx + components/auth/GoogleAuthButton.tsx — Decisión F5.
   Depende de: —
8. [frontend] [P] app/(dashboard)/page.tsx (saludo) — Decisión F6.
   Depende de: —
9. [docs] frontend/docs/STATE_AND_FETCHING.md + COMPONENTS_GUIDE.md — Decisión D (front).
   Depende de: 5, 6
10. [verif] /run-tests + Playwright desktop y 390×844 — Decisiones T4, T5.
   Depende de: 1, 2, 4, 5, 6, 7, 8
11. [docs] docs/TODO.md + docs/CHANGELOG.md + docs/ROADMAP.md (cierre) — Decisión D (cierre).
   Depende de: 10
```

El paso 1 fija el contrato del que dependen el 3 y el 5. Los pasos 4, 6, 7 y 8 no tocan archivos
en común ni dependen del backend, así que pueden ir en paralelo desde el principio.

## Resumen de archivos tocados

| Decisión | Backend | Frontend |
|---|---|---|
| B1 | `app/schemas/dashboard.py`, `app/schemas/schemas.py` (shim), `app/api/dashboard.py` | — |
| B2 | `app/api/accounts.py` | — |
| F1, F2 | — | `lib/dateRanges.ts`, `components/transactions/TransactionFilters.tsx`, `app/(dashboard)/transactions/page.tsx` |
| F3 | — | `types/api.ts`, `types/generated/api.ts`, `app/(dashboard)/analytics/page.tsx`, `components/AnalyticsSummary.tsx`, `components/CategoryDonutChart.tsx` |
| F4 | — | `lib/hooks/useUserPreferences.ts` |
| F5 | — | `app/(auth)/login/page.tsx`, `components/auth/GoogleAuthButton.tsx` |
| F6 | — | `app/(dashboard)/page.tsx` |
| T1–T3 | `tests/test_dashboard.py`, `tests/test_accounts.py` | — |
| D | `backend/docs/API_REFERENCE.md` (+ `FRONTEND_INTEGRATION.md` si aplica) | `frontend/docs/API_CONTRACT.md`, `STATE_AND_FETCHING.md`, `COMPONENTS_GUIDE.md` (+ `ARCHITECTURE.md` si aplica); `docs/TODO.md`, `docs/CHANGELOG.md`, `docs/ROADMAP.md` |

Sin migraciones: ningún cambio toca `models.py`.

## Out of Scope

- `◀ ▶` en los chips de `/transactions` (Q3): queda en el backlog del ROADMAP.
- Período consultable (`?year=&month=`) en `monthly-summary` (Q7).
- Guard de `GET /budgets/?month=&year=` en meses cerrados: sin call site en el frontend.
- Unificar el filtro de cuentas destacadas y alinear el mes UTC con la hora Bogotá. "Esta semana"
  en `/transactions` hereda el mismo desfase UTC de borde que Analítica, ya registrado en
  `docs/TODO.md`.
- Login con Google caído (externo), puertos de docker, codegen de tipos automático y nomenclatura.
- Instalar un test runner de frontend.

## Decisiones resueltas con el usuario (2026-09-26)

Todas vienen del `/grilling` (Q1–Q10 de `docs/archive/ROADMAP_fases_26-32.md`). Esta spec no abrió preguntas nuevas:
los hallazgos H1–H4 precisan cómo se implementan Q6 y Q8 sin cambiar lo decidido.

## Further Notes

- Spec corta a propósito (Q10): son ajustes chicos, pero Q6 cambia un contrato de API y por eso
  va por el flujo completo de `docs/WORKFLOW.md`.
- Después de B1, el invariante "los totales son la suma de los buckets" vale por construcción. El
  que sigue haciendo falta probar es la equivalencia con `category-distribution` (T3), porque son
  dos endpoints con filtros escritos por separado.
