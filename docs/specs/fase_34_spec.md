# Spec — Fase 34: zona horaria por usuario

> Sintetiza el `/grilling` del 2026-10-04 (decisiones **Q1–Q14**, todas aceptadas por el dueño) y lo
> que dejó escrito `docs/ROADMAP.md` ("Fase 34: zona horaria por usuario"). Esas decisiones no se
> reabren aquí: se citan por su número y se bajan a decisiones implementables **B** (backend), **F**
> (frontend), **X** (operativa), **T** (testing) y **D** (docs).
>
> Antes de escribirla se leyó el código afectado (ver "Hallazgos de exploración"); varios hallazgos
> corrigen o precisan premisas del grilling y quedan registrados abajo — en particular uno que
> **ajusta el criterio de aceptación 4 de Q14** (ver H9).
>
> **No implementa nada.** Solo se agrega este archivo.

**Estado:** spec escrita el 2026-10-04. Sin marcadores `[NEEDS CLARIFICATION]` vivos. El dueño
confirmó ese mismo día los **seams de testing** y el ajuste del criterio 4 (H9). `/analyze-spec`
(pre-implementación) corrido el 2026-10-04: un hallazgo ALTO (H13) y cuatro MEDIO, todos aplicados a
esta spec; queda lista para implementar en la rama `feat/fase-34-zona-horaria`.

---

## Problem Statement

Oikos guarda cada transacción como un instante (`timestamptz`, UTC) pero el dueño piensa en días de
calendario de **su** zona (Bogotá, UTC−5). Hoy no hay una zona de usuario: cada módulo decide la suya
y el resultado es que las horas no cuadran entre pantallas.

- **Un gasto cargado "de hoy" aparece corrido.** El modal manda `YYYY-MM-DD` y el backend lo guarda
  a las `00:00 UTC`, que en Bogotá son las 19:00 del día anterior: la lista lo muestra el día
  anterior y el modal de edición muestra la fecha UTC. Después de las 19:00 el modal propone el día
  siguiente (QA-032).
- **El "mes actual" y la "semana actual" dependen de dónde se calculen.** El dashboard, los
  presupuestos y las alertas resuelven el mes en UTC (desde las 19:00 Bogotá del último día ya es el
  mes siguiente); Analítica y `/transactions` resuelven la semana en UTC; el resumen semanal la
  resuelve en Bogotá. Los totales del mismo período pueden diferir según la pantalla (TODO, "Mes UTC
  contra hora Bogotá").
- **Las horas visibles dependen del dispositivo, no de una zona elegida:** fechas en el feed, hora de
  las notificaciones, "último uso" de las API keys y hasta el saludo "buenos días" usan la zona del
  navegador, mientras el backend agrega con otra.
- **No se puede arreglar solo en el frontend:** el backend agrega por día, semana y mes (dashboard,
  Analítica, presupuestos, alertas) y el resumen semanal corre en un cron sin dispositivo, así que la
  zona tiene que estar **guardada**.

## Solution

- Cada usuario tiene una **zona horaria guardada** (IANA, `America/Bogota` por defecto), detectada del
  dispositivo al registrarse y editable en Ajustes. Es la **única** fuente: todo cálculo de día,
  semana y mes del backend la usa, y reemplaza la constante de Bogotá del resumen semanal.
- Un gasto cargado con un día elegido aparece **ese día** en la lista y en el modal de edición, a
  cualquier hora; "hoy" conserva la hora real del registro.
- El dashboard, Analítica, `/transactions`, los presupuestos, las alertas y el resumen semanal
  cuentan el mismo mes y la misma semana para el mismo usuario, y los totales coinciden entre
  pantallas.
- El frontend deja de calcular instantes de límite: manda **días** (`YYYY-MM-DD`) y el backend los
  interpreta en la zona del usuario. Las horas visibles (feed, notificaciones, Ajustes, saludo) se
  muestran en esa zona.
- Los gastos históricos cargados solo con día (guardados a `00:00 UTC`) se migran a las 12:00 locales
  del mismo día, para que no se vean corridos.

## User Stories

**Zona guardada y su detección (Q1, Q2, Q12)**

1. Como dueño, quiero que mi cuenta tenga una zona horaria guardada, para que todos los cálculos
   usen la misma sin depender del dispositivo desde el que mire.
2. Como dueño, quiero que mi zona se detecte del navegador al registrarme con email, para no tener que
   elegirla a mano.
3. Como dueño, quiero que también se detecte al registrarme con Google, para que ese camino no quede
   con una zona distinta por defecto.
4. Como dueño, quiero que si la detección falla o trae un valor inválido el registro siga funcionando
   con `America/Bogota`, para que un detalle de zona nunca bloquee crear la cuenta.
5. Como dueño existente, quiero que mi cuenta quede en `America/Bogota` sin hacer nada, para que la
   app siga comportándose como hoy donde ya estaba bien.
6. Como dueño, quiero cambiar mi zona en Ajustes con un selector de zonas válidas, para corregirla si
   viajo o si la detección se equivocó.
7. Como dueño, quiero un error claro si mando una zona inexistente por API, para no guardar basura.
8. Como dueño, quiero ver mi zona actual en Ajustes, para saber con cuál se están contando mis días.
9. Como dueño, quiero una nota en el selector que diga que cambiar la zona reagrupa mis períodos pero
   no modifica mis movimientos, para no asustarme si un gasto de borde cambia de mes.
10. Como dueño, quiero que al cambiar la zona la app refresque todo lo que depende de ella, para no
    ver datos de la zona anterior.

**Fecha de una transacción (Q3, Q11)**

11. Como dueño, quiero que un gasto cargado con el día de hoy quede con la hora real en que lo
    registré, para que el orden dentro del día sea el natural.
12. Como dueño, quiero que un gasto cargado con un día pasado aparezca en ese día en la lista, sin
    importar a qué hora lo cargue.
13. Como dueño, quiero que al editar un gasto el modal muestre el día en mi zona y no el día UTC,
    para que lo que veo al editar sea lo que veo en la lista.
14. Como dueño, quiero que el modal proponga "hoy" según mi zona y no el día siguiente después de las
    19:00, para no corregir la fecha cada noche.
15. Como dueño, quiero que editar un gasto sin tocar la fecha no le cambie la hora, para que un
    cambio de monto o categoría no mueva el movimiento.
16. Como dueño, quiero que los atajos con API key que manden solo el día reciban el mismo trato que el
    modal, para que no haya dos reglas de fecha.
17. Como dueño, quiero que un cliente que mande un instante completo con zona lo vea guardado tal
    cual, para no romper integraciones existentes (curl).

**Coherencia entre pantallas (Q4, Q5, Q6)**

18. Como dueño, quiero que un gasto del último día del mes a las 22:00 cuente en ese mes en el
    dashboard, Analítica, presupuestos y alertas, para que los totales cuadren entre sí.
19. Como dueño, quiero que la semana del resumen semanal, la de Analítica y la de `/transactions`
    sean la misma, para que el total semanal no cambie según dónde lo mire.
20. Como dueño, quiero que el gráfico de flujo agrupe por días de mi zona, para que un gasto de la
    noche no aparezca en el día siguiente.
21. Como dueño, quiero que "este mes" del dashboard y de la tarjeta de la cuenta sean el mismo mes,
    para que ambas cifras cuadren.
22. Como dueño, quiero que el límite inferior del `◀` del dashboard sea el mes de mi primera
    transacción en mi zona, para no poder navegar a un mes vacío ni perder el primero.
23. Como dueño, quiero que los presupuestos y las alertas de umbral miren el mes en mi zona, para que
    el aviso del 80 % no se dispare por un gasto que en mi calendario es del mes siguiente.
24. Como dueño, quiero que los presupuestos recurrentes se generen según el mes de mi zona, para que
    el mes nuevo empiece cuando empieza para mí.
25. Como dueño, quiero que el resumen semanal diga la semana lunes–domingo en mi zona, para que un
    gasto del domingo por la noche cuente en su semana.
26. Como dueño, quiero que filtrar `/transactions` "hasta el día X" incluya todo ese día, hasta el
    último segundo, para no perder movimientos de fin de día (cierra el H11 de la Fase 29, el del desfase de fin de día en `core/periods.py`).
27. Como dueño, quiero que una consulta con solo-día y una con instante completo no se contradigan,
    para entender qué estoy pidiendo.

**Horas visibles (Q5)**

28. Como dueño, quiero que las fechas del feed (cuentas, categorías, últimas transacciones) se
    muestren en mi zona, para que coincidan con lo que filtro y agrego.
29. Como dueño, quiero que la hora de las notificaciones y de "último uso" de las API keys se
    muestre en mi zona.
30. Como dueño, quiero que el saludo del dashboard use la hora de mi zona, para que no diga "buenas
    noches" con el sol arriba si cambié de zona.
31. Como dueño, quiero que la pantalla de presupuestos abra en el mes de mi zona, para no ver el mes
    siguiente por la noche.

**Datos históricos (Q8)**

32. Como dueño, quiero que mis gastos viejos cargados solo con día aparezcan en el día que tecleé,
    para que mi historial no se vea corrido.
33. Como dueño, quiero que esa corrección se pueda deshacer, para poder volver atrás si algo sale
    mal.
34. Como dueño, quiero que los gastos de primer día de mes cargados a medianoche UTC queden en su
    mes correcto, aunque eso cambie algunos totales históricos de borde.
35. Como dueño, quiero probar esa corrección contra una copia y comparar totales antes y después,
    para no tocar datos reales a ciegas.

**Robustez (Q7, Q9, Q10)**

36. Como dueño, quiero que el stack siga funcionando en el modo SQLite offline, con el bucketing en
    UTC documentado, para no perder mi flujo de desarrollo sin Docker.
37. Como dueño, quiero que la lógica de límites esté probada en una zona al este de UTC, una al oeste
    y una con horario de verano, para que no dependa de que mi zona sea Bogotá.
38. Como dueño, quiero que la lógica de límites viva en un solo lugar, para no volver a tener tres
    interpretaciones de "mes" y "semana".
39. Como dueño, quiero que cambiar la zona no recalcule ni toque los movimientos guardados, para que
    sea una acción segura y reversible.
40. Como dueño, quiero que el resumen semanal siga llegando el lunes 07:00 hora de Bogotá aunque mi
    zona cambie, para no depender de un cron por zona (fuera de scope).

## Implementation Decisions

### Backend — modelo y contrato de zona (Q1, Q2, Q9, Q12)

- **B1.** `User.timezone`: `String(64)`, `NOT NULL`, `server_default 'America/Bogota'`. Migración de
  Alembic (skill `alembic-migration`) que agrega la columna con el default, lo que hace el backfill
  de los usuarios existentes a Bogotá sin paso extra. Revisada a mano antes de commitear.
- **B2.** Validación centralizada de zona en un único helper (`zoneinfo.available_timezones()`), que
  usan los tres puntos de entrada (B4, B5). La zona se valida solo contra el set IANA del runtime: si
  el contenedor no trae base `tzdata` el helper falla en el arranque de los tests, no en producción
  (verificar en la imagen de Docker; el resumen semanal ya depende de `ZoneInfo("America/Bogota")`).
- **B3.** `UserResponse` expone `timezone`. `GET /users/me` ya es el camino que lee el frontend
  (`useCurrentUser`); no se agrega endpoint.
- **B4.** El cambio de zona viaja por el mismo camino que `preferred_currency`:
  `GET`/`PATCH /users/me/preferences`. `PreferencesUpdate.timezone` es opcional; si viene y no es
  válida → `422` de dominio con `detail` string (mismo patrón que QA-025). Sin cascada a otras
  tablas y sin recálculo (Q9): los instantes guardados no se tocan.
- **B5.** Registro: `UserCreate.timezone` opcional (email) y `GoogleLoginRequest.timezone` opcional.
  **Si falta o es inválida, se usa el default y el registro NO falla** — distinto del `422` de B4,
  a propósito (Q2). En el flujo de Google la zona solo se aplica cuando se **crea** el usuario; un
  login de un usuario existente no la sobrescribe.

### Backend — módulo de límites (Q6, Q10)

- **B6.** Un único módulo puro concentra toda la aritmética de calendario con zona, extendiendo
  `core/periods.py` (o un módulo hermano si crece): `ahora` inyectado como parámetro, sin leer el
  reloj. Funciones mínimas: resolver el mes pedido o actual **en la zona** (`resolver_mes(year,
  month, ahora, tz)`), rango de mes `[inicio, fin)`, límites de semana (lunes–domingo) que contiene
  un instante, rango de días `[00:00 local del inicio, 00:00 local del día siguiente al fin)`,
  "día local" de un instante, e instante de un día (B9). **Todos devuelven datetimes aware en UTC**
  (ver H5): comparar contra `timestamptz` en Postgres y contra el UTC naive que guarda SQLite da el
  mismo resultado en los dos motores.
- **B6b.** Convención heredada (Fase 31 B6): el límite superior es **siempre exclusivo** y todo
  consumidor compara con `< fin`, nunca `<=`. Como se cambia la firma, `rango_mes_utc` se **renombra**
  (un consumidor olvidado es `ImportError`, no una medianoche contada dos veces).
- **B6c.** Prohibido construir `datetime(...)` naive o resolver "mes/semana actual" desde UTC fuera de
  este módulo (criterio 4, Q14; verificable con `grep` al cierre).

### Backend — rangos y períodos en los endpoints (Q6)

- **B7.** Parámetros de rango `start_date`/`end_date` de `/transactions`, `cashflow-series` y
  `category-distribution` aceptan **ambos formatos con los mismos nombres**:
  - solo-día `YYYY-MM-DD` → se interpreta en la zona del usuario: inicio = 00:00 local del día,
    fin = 00:00 local del **día siguiente**, exclusivo;
  - datetime completo con zona → instante tal cual; un `end_date` datetime se trata como inclusivo
    (`< end + 1 µs`, equivalente a `<=`), para no cambiar el contrato de los clientes curl/API key.
  La resolución vive en un helper compartido (una dependencia o función), no copiada por router. El
  `422`/`400` de "fecha inicial mayor que la final" se conserva. Cierra el H11 de la Fase 29 y QA-019 por el camino
  solo-día. [Implementación a verificar: si FastAPI no resuelve bien una unión `date | datetime` en
  query params, el helper recibe `str` y parsea; el contrato externo no cambia.]
- **B8.** Períodos mensuales del dashboard (`GET /dashboard/summary`, `/budgets-progress` y los
  `?year=&month=`), `GET /accounts/{id}/monthly-summary` y `_first_transaction_month` pasan a la zona
  del usuario: el "mes actual" es el de su zona, "no se puede consultar un mes futuro" se evalúa
  contra ese mes, y el techo del mes en curso es `ahora` (semántica de Fase 29/30 sin cambios).
- **B8b.** `core/budget_alerts` y la generación de presupuestos recurrentes (el guard de B5/Fase 29
  `(year, month) >= mes actual`) resuelven el mes en la zona del usuario. La función que calcula el
  "gastado" recibe la zona (o el usuario) en vez de asumir UTC. **Presupuestos anticipados (mes
  futuro) siguen evaluándose completos**, como exige la docstring actual.
- **B8c.** `cashflow-series`: en Postgres el bucket por día/mes agrupa por `date AT TIME ZONE <tz>`
  (Q7); en SQLite la rama existente (`strftime`) sigue en UTC y se **documenta como "solo UTC"** (el
  opt-in offline no ejercita zonas). La sesión Postgres sigue forzada a UTC (`database.py`, QA-022).
- **B8d.** `category-distribution` y los agregados de `dashboard` usan los mismos límites (B6) que las
  listas, para que los totales coincidan (criterio 1).

### Backend — fecha de la transacción (Q3, Q11)

- **B9.** `TransactionCreate.date` y `TransactionUpdate.date` aceptan `YYYY-MM-DD` **o** datetime
  completo. Conversión en el backend:
  - solo-día **igual a hoy** en la zona del usuario → `now()` (hora real);
  - solo-día de **otro día** → las 12:00 locales de ese día;
  - datetime completo con zona → se guarda tal cual; un datetime naive conserva el comportamiento
    actual (UTC), sin cambios.
  Sin `date` se conserva `datetime.now(UTC)` (captura, atajos). El mediodía local hace el día
  robusto a un cambio de zona de ±12 h (Q3b).
  **Tipo del campo:** hoy `date: datetime | None` (`schemas/transactions.py`) convierte `2026-10-04`
  en `00:00` naive, idéntico a un `2026-10-04T00:00:00` naive, así que con ese tipo el solo-día no se
  distingue. El campo pasa a `date | datetime | None` (Pydantic v2 en modo smart resuelve `YYYY-MM-DD`
  como `date` y un ISO con hora como `datetime`); si no se comporta así, el campo recibe `str` y un
  validador lo parsea. El contrato externo no cambia. Mismo criterio que la nota de B7.
- **B9b.** Los avisos de presupuesto que dispara crear/editar/borrar una transacción usan la fecha ya
  convertida (B9) y el mes en la zona del usuario (B8b); la categoría/fecha "vieja" de `PUT` se
  captura antes de mutar, como hoy.

### Backend — resumen semanal (Q4)

- **B10.** `build_weekly_summary` calcula la semana lunes–domingo en `User.timezone`. Se **elimina
  `SUMMARY_TIMEZONE`**. `_limites_semana` pasa a ser el límite de semana de B6 (aware, exclusivo al
  final; hoy devuelve `domingo 23:59:59`). El **cron sigue único**: lunes 07:00 `America/Bogota`
  (`main.py`), como decidió Q4: la zona del usuario define *qué semana* se resume, no *cuándo* llega.
  La referencia del job sigue siendo `ahora − 7 días` (Fase 33 §B1). Consecuencia aceptada: ver H8.

### Backend — seed

- **B11.** `core/seed.py` genera sus fechas coherentes con B9 (mediodía de la zona del usuario seed,
  Bogotá) en vez de `datetime` naive a `00:00`, y sus tests se ajustan. Es solo dev.

### Operativa — datos existentes (Q8)

- **X1.** **Migración de datos de Alembic, separada de B1 y como último commit de código de la fase** (revertible
  sin tocar el resto). Para toda fila de `transactions` (incluidas las borradas lógicamente) cuya hora
  UTC sea **exactamente `00:00:00.000`**, la mueve a las `17:00:00Z` **del mismo día UTC** (= 12:00
  `America/Bogota`). El día que el usuario tecleó se conserva, que es la razón de elegir esa
  conversión. Los saldos de cuenta no cambian (no depende de la hora). `downgrade` simétrico: filas a
  `17:00:00.000Z` exactas → `00:00:00Z`. Ramas por dialecto (Postgres y SQLite, esta última para que
  `alembic check`/los tests migren). Una fila real registrada exactamente a las 17:00:00.000Z sería un
  falso positivo del `downgrade`; se acepta (prácticamente imposible con `now()`).
- **X2.** **Efecto conocido y aceptado:** un gasto del primer día de un mes cargado a medianoche UTC
  hoy cuenta en el mes anterior en hora Bogotá; tras el backfill cuenta en su mes. Algunos totales
  históricos de borde cambian a su valor correcto.
- **X3.** **Cómo se prueba (nunca directo en producción):** se aplica sobre una **copia** (o el Postgres
  desechable de `AGENTS.md`), con un reporte de totales por mes y por cuenta **antes y después**, y la
  lista de filas que cruzan de mes. El dueño revisa el reporte antes de que corra en producción. Antes
  del despliegue en producción: copia de seguridad (`pg_dump` / servicio `backup`) — el `CMD` de Docker
  corre `alembic upgrade head` solo.

### Frontend (Q2, Q5, Q6, Q11)

- **F1.** Tipo `UserResponse.timezone` y acceso único a la zona: un hook/helper (`useTimezone`) que
  devuelve `user.timezone`. Mientras el usuario no cargó, **las queries que dependen de la zona no
  se disparan** (no mandar un rango calculado con la zona equivocada); el display puro cae a la zona
  del dispositivo.
- **F2.** Un módulo de fechas basado solo en `Intl` (sin librería nueva — H3): "hoy en zona",
  "día de un instante en zona", "mes actual en zona", hora local en zona. Reemplaza el cálculo de
  límites de `lib/dateRanges.ts`, que pasa a construir **días `YYYY-MM-DD`** y **no instantes UTC**.
  La aritmética de calendario puro (sumar días, primer/último día de mes) puede seguir usando
  `Date.UTC` como motor de calendario sobre `y/m/d`, documentado (ver H9).
- **F3.** Los consumidores de rango mandan días: Analítica (semana/mes/año, `?ref=`), `/transactions`
  (presets, rango personalizado y chip "Esta semana"), detalle de cuenta (`utcMonthRange`) y el
  dashboard (`?month=YYYY-MM`). El `?month=` / `?ref=` de la URL conserva su semántica de etiqueta de
  calendario; lo que cambia es dónde se resuelve el "actual" (zona del usuario, F2).
- **F4.** Modales de transacción (`TransactionModal`, **`EditTransactionModal`**, el modal propio de
  `/accounts/[id]` y el de `/categories/[id]`) y `/capture` (H13): la fecha inicial es **hoy en la zona del usuario** (no `toISOString().split('T')[0]`);
  se manda el string del `<input type="date">` sin convertir (B9). Al **editar**, el campo muestra el
  día del instante en la zona (con `Intl`, nunca `split('T')[0]`) y se manda la fecha **solo si el
  usuario la cambió** (así editar el monto no re-estampa la hora de un gasto de hoy, historia 15).
- **F5.** Registro: el formulario de email y `GoogleAuthButton` mandan
  `Intl.DateTimeFormat().resolvedOptions().timeZone` como `timezone` (B5). Nada más de UI en el registro.
- **F6.** Ajustes: selector de zona (lista de `Intl.supportedValuesOf('timeZone')` incluyendo la
  guardada) que hace `PATCH /users/me/preferences` con la nueva zona, con la nota "Cambiar la zona
  reagrupa tus períodos; no modifica tus movimientos" (Q9). Al guardar se **invalidan todas las queries
  que dependen de fechas** (dashboard, analítica, transacciones, presupuestos, cuentas); actualizar
  `frontend/docs/STATE_AND_FETCHING.md`.
- **F7.** Formateo en zona: `formatDate`/`formatDateLabel` aceptan `timeZone` y los llamadores
  (`TransactionList`, `RecentTransactionsSection`, `accounts/[id]`, `categories/[id]`) la pasan; los
  "hace N min"/fechas absolutas de `NotificationBell` y de Ajustes (último uso de API keys, fechas)
  también. El saludo del dashboard usa la **hora en la zona** (`Intl`), no `getHours()` del
  dispositivo. La pantalla de presupuestos abre en el mes de la zona, no en el del dispositivo.

### Docs

- **D1.** Contrato compartido: `backend/docs/API_REFERENCE.md` **y** `frontend/docs/API_CONTRACT.md`
  en el mismo cambio (campo `timezone`, `start_date`/`end_date` con ambos formatos, `date` de la
  transacción, `GoogleLoginRequest.timezone`, `UserCreate.timezone`).
- **D2.** `backend/docs/BUSINESS_RULES.md`: semántica de zona (mes/semana en la zona del usuario,
  límite superior exclusivo, conversión de fecha solo-día, "cambiar la zona no recalcula", SQLite solo
  UTC). `ARCHITECTURE.md` de ambos lados y `STATE_AND_FETCHING.md` según F6.
- **D3.** Cierre: `docs/CHANGELOG.md`, `docs/ROADMAP.md` (la fase pasa a completa; Recurrentes sigue
  como Fase 35), `docs/TODO.md` (cerrar **QA-032** en `ROADMAP.md`/`CHANGELOG.md` — no tiene fila propia en `TODO.md` —, la fila "Mes UTC contra hora Bogotá…" y las notas
  de la deuda de mes/semana UTC de las Fases 29–31; el H11 de la Fase 29 queda cerrado por B7), `AGENTS.md` (la línea de
  fases y `core/periods`/zona), y `graphify update .`.

## Testing Decisions

**Qué es un buen test aquí.** Prueba comportamiento observable desde el punto más alto posible: lo que
el dueño ve o recibe (totales, listas, avisos, el día de un movimiento), no cómo está armado el
código. La lógica de zona se prueba con **zonas distintas de UTC y de Bogotá** (Bogotá es −5 y sin
horario de verano, así que esconde dos clases de bug).

**Seams (confirmados por el dueño el 2026-10-04 — skill `to-spec`):**

1. **Backend: la API HTTP con `TestClient`** (endpoints de rangos, dashboard, cuentas, transacciones,
   preferencias, registro) y **`run_weekly_summary_job`** para el cron. Es el seam más alto y ya existe
   en la suite; los tests entran por la frontera pública con un usuario de zona X y fechas de borde, y
   no por funciones internas.
2. **Backend: el módulo puro de límites (B6)** con `ahora` inyectado, como único seam nuevo, a propósito:
   centraliza toda la aritmética de zona y es donde viven los bordes de DST. Prior art:
   `tests/test_periods.py`.
3. **Frontend: el navegador (Playwright) contra el stack dev aislado.** El repo no tiene tests de
   frontend y Vitest/RTL está explícitamente fuera de scope (ROADMAP), así que la verificación es una
   pasada guiada de Playwright, escrita como lista de pasos en esta spec (paso `[verif]`).

**Backend (T1–T6):**

- **T1.** Límites puros (B6) en `America/Bogota`, `Asia/Tokyo` (+9: el día local va *adelantado* al
  UTC) y `America/New_York` (DST, con el cambio de marzo 2026-03-08 y el de noviembre 2026-11-01):
  mes, semana, rango de días, día local de un instante, y las funciones que reciben `ahora`.
- **T2.** Borde por zona vía HTTP: una transacción en el último/primer instante del día, de la semana y
  del mes de la zona del usuario cae en el bucket correcto en `transactions` (lista),
  `cashflow-series`, `category-distribution`, `dashboard/summary`, `budgets-progress` y
  `accounts/{id}/monthly-summary`; **los totales coinciden entre endpoints** (criterio 1). El caso de
  `cashflow-series` por día necesita Postgres: se salta en el opt-in SQLite con `skipif` y motivo
  explícito. **No** se agrega un marker de motor (el marker `postgres` se retiró en la Fase 32 a
  propósito; `concurrencia` es de aislamiento).
- **T3.** Contrato de rango (B7): solo-día interpretado en la zona (fin exclusivo, incluye el último
  segundo del día); datetime completo como instante; inicio mayor que fin → error; mezcla de formatos.
- **T4.** Fecha de transacción (B9): solo-día de hoy → hora real; solo-día pasado → 12:00 locales y se
  lista ese día en Tokyo y en New York; datetime completo tal cual; `2026-10-04` (solo-día) frente a `2026-10-04T00:00:00`
  (naive) se tratan distinto; `PUT` sin `date` conserva la
  anterior; sin `date` en `POST` → `now()`.
- **T5.** Zona del usuario (B1–B5): default `America/Bogota`; `PATCH` con zona inválida → `422`;
  registro con zona inválida o ausente **no falla** y queda en el default; Google solo aplica la zona
  en la creación; `GET /users/me` la devuelve.
- **T6.** Resumen semanal (B10): `run_weekly_summary_job` con un usuario en Tokyo y otro en Bogotá, mismo
  instante: cada uno resume la semana de **su** zona; el borde domingo/lunes entra a la semana
  correcta; sin `SUMMARY_TIMEZONE`. Alertas de presupuesto (B8b): un gasto del último día del mes a las
  22:00 hora del usuario evalúa umbrales del mes correcto.
- **T7.** Se actualizan los tests existentes que construían límites naive/UTC o asumían la constante de
  Bogotá (`test_weekly_summary.py`, `test_periods.py`, `test_dashboard.py`, `test_budget_alerts.py`,
  `test_transactions.py`, `test_seed.py`); la guarda `TestSessionTimezoneIsAlwaysUtc` queda intacta.
- **T8 (X1/X3).** Prueba de la migración de datos contra copia/Postgres desechable: sembrar filas a
  `00:00:00Z`, aplicar, comprobar `17:00:00Z` del mismo día, aplicar `downgrade` y comprobar el
  retorno; reporte de totales antes/después. Es un script de verificación (como T5 de la Fase 33), no
  un test de la suite.
- **Prior art.** `tests/test_periods.py` (funciones puras con `ahora` inyectado), `test_weekly_summary.py`
  (`freeze_time` + job), `test_concurrency.py` (guarda de sesión UTC), `test_migrations.py` (`alembic
  check`), `test_dashboard.py` (endpoints con `TestClient`).

**Frontend (verificación Playwright, paso `[verif]`)**, en 390×844 y 1280×800, con el usuario dev
cambiado a `Asia/Tokyo` y a `America/Bogota`:

- Cargar un gasto con fecha de ayer y de hoy: se lista ese día; el modal de edición (también desde
  `/transactions` y `/categories/[id]`) muestra el mismo día; editar solo el monto no cambia su hora.
- El modal propone "hoy" de la zona del usuario también después de las 19:00 Bogotá.
- Dashboard, Analítica y `/transactions` con el mismo gasto de borde de mes/semana: mismos totales.
- Cambiar la zona en Ajustes refresca todo y muestra la nota; el selector solo ofrece zonas válidas.
- Las horas de notificaciones y de "último uso" de API keys corresponden a la zona elegida.
- `grep` de cierre (criterio 4): sin `datetime(...)` naive ni resolución UTC de "actual" en backend
  fuera del módulo de límites, y sin instantes UTC de límite enviados al backend desde
  `dateRanges.ts`.
- `/run-tests` (pytest, ruff, eslint, prettier) en verde; `alembic check` limpio.

## Out of Scope

- **Un job de resumen semanal por zona** (Q4b): sigue un solo cron Bogotá. Evolución anotada, no
  planificada.
- **Ingresos y gastos recurrentes** — Fase 35.
- **Aviso "tu dispositivo está en otra zona"** (Q2): sin banner.
- **Recalcular o migrar movimientos al cambiar la zona** (Q9).
- **Columna de "día de calendario" separada del instante** (Q3c), descartada por el costo de migración.
- **Librería de zonas horarias en el frontend** (Q6): solo `Intl`.
- **i18n/locale por usuario más allá de `preferred_locale` existente**, y los formatos de moneda.
- **Hardening de seguridad/auth:** sin cambios; esta fase no toca el modelo de amenazas.

## Further Notes

- **Un solo PR** con los pasos de "Orden de ejecución" (Q13). Si se prefiere partir, el corte natural
  es entre los pasos de backend (1–6) y los de frontend (7–8); la migración de datos va siempre al
  final.
- **Despliegue:** `alembic upgrade head` corre solo en el `CMD` y aplicará X1 junto con B1. Por eso X3
  exige probar antes y tener copia de seguridad: el dueño no debería enterarse de X1 por primera vez en
  producción.
- **Orden de aplicación:** la columna (B1) debe estar antes de cualquier código que lea
  `user.timezone`; X1 es independiente del código nuevo pero cambia lo que ese código muestra.

## Hallazgos de exploración

- **H1.** Las preferencias del usuario se cambian por **`PATCH /users/me/preferences`**
  (`preferred_currency`, `preferred_locale`, `preferred_theme`, `weekly_summary_enabled`), no por
  `PATCH /users/me` (ese es el perfil: `monthly_income`). La zona sigue el patrón de preferencias (B4).
- **H2.** El endpoint se llama `category-distribution` (no "breakdown"); los de rango con
  `start_date`/`end_date` son `transactions` (lista), `cashflow-series` y `category-distribution`. El
  dashboard (`summary`, `budgets-progress`) resuelve período con `?year=&month=`, no con rango.
- **H3.** El frontend no tiene librería de zonas ni runner de tests; calcular "medianoche local de una
  zona IANA" en JS a mano es frágil con DST. Por eso Q6 mueve la interpretación al backend y el cliente
  solo extrae año/mes/día con `Intl` (que sí es exacto).
- **H4.** El frontend hoy calcula instantes de límite en varios sitios: `dateRanges.ts` (`Date.UTC`,
  `T23:59:59Z`, `toISOString`), el detalle de cuenta (`utcMonthRange`, `split('T')[0]`), el modal de
  transacción (`toISOString().split('T')[0]`), la pantalla de presupuestos (mes del dispositivo con
  `new Date()`) y el saludo (`getHours()`). Todos pasan a la zona del usuario.
- **H5.** SQLite guarda y compara datetimes **sin zona**: un límite aware no UTC se serializaría como
  hora local y compararía mal. Todos los límites de B6 se normalizan a UTC aware antes de ejecutar la
  query, así Postgres (`timestamptz`) y SQLite dan lo mismo.
- **H6.** `cashflow-series` agrupa con `to_char(timestamptz)`, que usa la zona de la **sesión**
  (forzada a UTC por QA-022); para agrupar en la zona del usuario hay que usar `AT TIME ZONE` explícito.
  `strftime` de SQLite no tiene zonas: de ahí la decisión Q7a.
- **H7.** `_limites_semana` (Fase 33) devuelve `domingo 23:59:59` (inclusivo); B6/B10 lo unifican al
  límite exclusivo del lunes siguiente, igual que el mes.
- **H8.** El job semanal resume `ahora − 7 días`. Para un usuario en una zona **bastante detrás** de
  Bogotá (p. ej. −10 h), el lunes 07:00 Bogotá todavía es domingo allí y esa referencia cae en la
  semana *antes* de la recién cerrada para él. Es una consecuencia aceptada de Q4a (cron único) y no
  afecta al dueño; queda como argumento para el job por zona si algún día hay usuarios en otras zonas.
- **H9.** **Ajuste al criterio de aceptación 4 de Q14.** Q14 decía "sin `getUTC*`/`Date.UTC` de
  calendario en `dateRanges.ts`". `Date.UTC` también se usa como motor de aritmética de calendario sobre
  `y/m/d` (sumar días, último día del mes), que es correcto e independiente de la zona. El criterio se
  precisa como: **ningún instante UTC de límite sale hacia el backend**; `Date.UTC` queda permitido solo
  como aritmética de calendario puro, documentado. **Confirmado por el dueño (2026-10-04).**
- **H10.** El registro con Google recibe solo `id_token`; para pasar la zona se agrega un campo opcional
  al request (B5). Un login de un usuario ya existente no debe sobrescribir su zona.
- **H12.** `useDialogCounter`, `QueryErrorState` y demás piezas de la Fase 33 ya existen; esta fase no
  los toca.

## Hallazgos del `/analyze-spec` (2026-10-04)

- **H13.** (ALTO) F4 omitía dos sitios con el patrón `split('T')[0]` / `toISOString().split('T')[0]`:
  `components/modals/EditTransactionModal.tsx` (el modal de edición de la historia 13, también usado
  desde `/transactions`) y el modal propio de `app/(dashboard)/categories/[id]/page.tsx`. Incorporados
  a F4, al paso 10 y a la verificación Playwright.
- Los otros hallazgos (tipo de `date` en B9, orden de los tests existentes, `gen:types`, QA-032 sin
  fila en `TODO.md`, nombre duplicado H11, criterios de Q14, "último commit") están aplicados en B9/T4,
  Orden de ejecución, D3, H12 y "Criterios de aceptación (Q14)".

## Criterios de aceptación (Q14)

Los seis criterios del grilling no estaban transcritos en la spec; esta es su consolidación a partir de
lo que la spec ya exige. Los números 1 y 4 son los que cita el texto (el 4 con el ajuste de H9); el
resto no tenía número en la spec, así que su numeración es de esta consolidación.

1. **Totales coherentes:** el mismo mes/semana da los mismos totales en dashboard, Analítica,
   `/transactions`, presupuestos, alertas y resumen semanal (B8d, T2).
2. **Día respetado:** un gasto cargado con un día aparece en ese día en la lista y en el modal de
   edición, a cualquier hora; "hoy" conserva la hora real (B9, F4, T4).
3. **Zona guardada y validada:** `User.timezone` con default `America/Bogota`, detectada en el
   registro (email y Google), editable en Ajustes, `422` si es inválida por API (B1–B5, F5–F6, T5).
4. **Sin instantes UTC de límite desde el frontend** (H9) y sin `datetime(...)` naive ni resolución
   UTC de "actual" en el backend fuera del módulo de límites (B6c, F2; `grep` de cierre).
5. **Histórico corregido y reversible:** la migración X1 se prueba contra una copia con reporte de
   totales antes/después y su `downgrade` vuelve al estado anterior (X1–X3, T8).
6. **Límites probados en varias zonas:** Bogotá, Tokyo y New York (DST), con el módulo puro único (B6,
   T1, T6).

## Decisiones resueltas con el usuario (2026-10-04)

| # | Decisión |
|---|---|
| Q1 | Una sola fuente de zona: `User.timezone` guardada. El dispositivo solo la detecta/propone. Reemplaza `SUMMARY_TIMEZONE`. |
| Q2 | Detección en registro (email y Google), fallback `America/Bogota` sin fallar el registro, backfill Bogotá, selector en Ajustes validado con `zoneinfo`, **sin** banner de zona distinta. |
| Q3 | La fecha sigue siendo un instante; día pasado → 12:00 locales, hoy → `now()`. |
| Q4 | Cron único Bogotá; la zona del usuario define qué semana se resume. |
| Q5 | Entran: QA-032 y el modal, mes/semana del dashboard, Analítica, `/transactions`, presupuestos, alertas, `monthly-summary`, semana del resumen, horas visibles, saludo, seed y sus tests. Recurrentes fuera. |
| Q6 | Rangos: solo-día interpretado en la zona del usuario **o** datetime completo como instante; mismos nombres de parámetro; frontend manda días; "hoy" con `Intl`. |
| Q7 | `cashflow-series` por día con `AT TIME ZONE` en Postgres; SQLite solo UTC; tests tz-aware se saltan allí. |
| Q8 | Migración de datos con Alembic (`00:00Z` exacto → `17:00Z` mismo día), `downgrade` simétrico, último commit, probada en copia con totales antes/después. |
| Q9 | Cambiar la zona no recalcula ni toca instantes; se documenta y el selector lo avisa. |
| Q10 | Tests con Bogotá, Tokyo y New York (DST marzo y noviembre); módulo puro único de límites; sesión Postgres sigue en UTC. |
| Q11 | El backend convierte solo-día en `POST`/`PUT`; el frontend manda el string del `<input>` y extrae el día con `Intl`. |
| Q12 | `String(64) NOT NULL` default `America/Bogota`, en `GET /users/me` y `PATCH /users/me/preferences`, `422` si es inválida; registro con zona inválida usa el default. |
| Q13 | Un solo PR con cuatro bloques; migración de datos última. |
| Q14 | Seis criterios de aceptación (el 4 precisado en H9, confirmado). |
| Seams | API HTTP + `run_weekly_summary_job`, módulo puro de límites (único seam nuevo) y Playwright para el frontend. Confirmados. |

## Orden de ejecución

1. [backend] `models.py` + migración de la columna `users.timezone` + `UserResponse` + validación de
   zona (helper) — Decisiones B1, B2, B3.
   Depende de: —
2. [backend] [P] Módulo puro de límites con zona (`core/periods.py`, renombre de `rango_mes_utc`) y
   sus tests unitarios — Decisiones B6, B6b, B6c, T1.
   Depende de: —
3. [backend] Preferencias, registro y Google: `timezone` en `PreferencesUpdate`, `UserCreate`,
   `GoogleLoginRequest` — Decisiones B4, B5.
   Depende de: 1
4. [backend] Dashboard, cuentas y alertas en la zona del usuario; `cashflow-series` con `AT TIME ZONE`;
   helper compartido de rango y `/transactions` (lista) y `category-distribution` — Decisiones B7,
   B8, B8b, B8c, B8d.
   Depende de: 1, 2
5. [backend] [P] Resumen semanal por zona del usuario; eliminar `SUMMARY_TIMEZONE` — Decisión B10.
   Depende de: 1, 2
6. [backend] Conversión de fecha en `POST`/`PUT /transactions` — Decisiones B9, B9b.
   Depende de: 2, 4  (comparte `transactions.py` con el paso 4)
7. [backend] [P] Seed coherente con B9 — Decisión B11.
   Depende de: 2
8. [docs] Contrato compartido (`API_REFERENCE.md` y `API_CONTRACT.md`) — Decisión D1.
   Depende de: 3, 4, 6
9. [frontend] Tipos (regenerar `frontend/types/generated/api.ts` con `pnpm gen:types` contra el backend
   de dev `:8001`), hook de zona, módulo de fechas con `Intl` y `dateRanges.ts` sobre días — Decisiones
   F1, F2, F3.
   Depende de: 8  (contrato fijado; verificable solo con 3–6 corriendo)
10. [frontend] Modales de transacción (incl. `EditTransactionModal` y el de `/categories/[id]`) y
    `/capture`, registro/Google, selector en Ajustes, formateo en
    zona, saludo y presupuestos — Decisiones F4, F5, F6, F7.
    Depende de: 9
11. [backend] Tests de integración por zona (HTTP, job semanal, conversión de fecha, registro) — Decisiones
    T2–T6. **Los tests existentes (T7) se ajustan en el mismo paso que cambia su comportamiento** (4, 5,
    6 o 7), para que la suite no quede en rojo entre pasos; este paso solo agrega los tests nuevos.
    Depende de: 4, 5, 6, 7
12. [backend] Migración de datos de fechas históricas (`00:00Z` → `17:00Z`), como **último commit de
    código** (los docs de cierre del paso 14 van después) —
    Decisiones X1, X2.
    Depende de: 4, 5, 6, 11
13. [verif] Prueba de X1 contra copia con reporte antes/después (T8); pasada Playwright; `grep` de
    cierre; `/run-tests`; `alembic check` — Decisiones X3, T8 y la lista de verificación.
    Depende de: 10, 11, 12
14. [docs] Docs de dominio y de cierre (`BUSINESS_RULES`, `ARCHITECTURE`, `STATE_AND_FETCHING`,
    CHANGELOG, ROADMAP, TODO, `AGENTS.md`) y `graphify update .` — Decisiones D2, D3.
    Depende de: 13
