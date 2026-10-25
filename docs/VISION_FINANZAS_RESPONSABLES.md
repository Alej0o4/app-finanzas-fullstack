# Visión — de "anotar gastos" a "finanzas responsables"

> Documento de dirección de producto (2026-10-17). Explica **qué se va a construir y por qué**.
> El orden y el estado de las fases viven en `docs/ROADMAP.md`; el detalle de implementación de
> cada una irá en `docs/specs/fase_NN_spec.md` cuando le toque su `/grilling`.
>
> **Estado: dirección acordada. La Fase 35 (§2.1 y §2.2: sobres + disponible real) está implementada
> (2026-10-17, `docs/specs/fase_35_spec.md`); el resto sigue sin implementar.** Los nombres de tablas y columnas de este
> documento son un punto de partida, **no están verificados contra `models.py`**: la spec de cada
> fase los fija. Lo marcado como *Pendiente de `/grilling`* no está decidido.

---

## 1. Por qué un nuevo enfoque

Oikos ya responde bien dos preguntas:

- **Stock** — *¿cuánto tengo?* (saldos de cuentas, vista secundaria).
- **Flujo** — *¿cuánto gasté este mes y cuánto me queda?* (dashboard, presupuestos, alertas).

Lo que no responde es: ***¿cuánto de lo que me queda ya tiene dueño?*** Casi todo lo que hace
irresponsable un mes "bueno" es plata que todavía no se gastó pero ya está comprometida: la prima
del seguro de diciembre, los regalos, la ropa, el computador que se quiere renovar, el colchón de
emergencia. Hoy la app ve esos $2M en la cuenta como disponibles, y el golpe llega cuando se
vencen.

**La primitiva nueva es el dinero comprometido pero no gastado.** Con ella la pregunta pasa a ser:

> **Disponible real = saldo de las cuentas − lo comprometido en sobres.**

Es una tercera capa que **convive** con las otras dos (no las reemplaza):

| Capa | Pregunta | Estado |
|---|---|---|
| Stock | ¿Cuánto tengo? | Existe (cuentas) |
| Flujo | ¿Cuánto gasté y cuánto me queda este mes? | Existe (dashboard, presupuestos) |
| **Compromiso** | **¿Cuánto de lo que tengo ya está apartado para algo?** | **Nueva** |

**Qué NO cambia.** Sigue siendo una herramienta personal de un solo dueño (ver el cambio de
enfoque del 2026-09-19 en el ROADMAP): nada de esto abre trabajo de seguridad, auth ni
multi-usuario. Tampoco cambia el listón de calidad (Alembic, tests, capa de servicios,
`DomainError`), ni la regla de que **el backend es la fuente de verdad de todo cálculo
financiero**: aportes requeridos, estados, runway y disponible real se calculan en el servidor y el
frontend no los recalcula.

**Principio de fricción.** Más planeación significa más fricción de uso; si configurar todo cuesta
una hora, la app se deja de usar. Cada feature debe tener un **valor por defecto sensato** (por
ejemplo, sugerir sobres a partir del historial de gasto anual) para que empezar tome minutos.

---

## 2. Las features, con su justificación

Orden = orden de construcción propuesto (ver §4). Numeración de fases tentativa.

### 2.1 Sobres virtuales (provisiones, fondo de emergencia y metas) — *Fase 35*

**Qué es.** Una capa de asignación sobre las cuentas existentes: el dinero apartado en un sobre
**no es una cuenta ni se mueve de verdad**, solo se reserva. Un mismo concepto cubre tres usos
(`kind`): gasto anual/periódico (*sinking fund*: seguro, impuestos, Navidad, cumpleaños, ropa,
viajes), **fondo de emergencia** y **meta** de mediano plazo (el computador en 14 meses).

**Por qué.**
- Es la **primitiva** de la que cuelga todo lo demás de este documento; sin ella no hay disponible
  real, ni gasto contra sobre, ni págate primero.
- Convierte "tengo que acordarme de que en diciembre pago el seguro" en un aporte mensual
  calculado: `(meta − saldo del sobre) / meses restantes`. El golpe de caja desaparece.
- El fondo de emergencia deja de ser un número inventado: la meta se expresa en **meses de gasto
  esencial real** (N × promedio de los últimos meses), con progreso y *runway* visibles.
- Las metas pasan de deseo a compromiso con ritmo: la app dice si vas **al día, atrasado o
  cumplido**.
- Es **aditivo**: tablas nuevas, sin tocar `Transaction` ni `ledger.py`, así que el riesgo sobre lo
  que ya funciona es bajo.

**Diseño base (a verificar en la spec).**
- `funds`: `user_id`, `name`, `kind` (`annual_expense` / `emergency` / `goal`), `account_id`
  (dónde vive físicamente el dinero), `currency` (igual a la de la cuenta, validado en el
  servicio), `target_amount` **o** `target_months` (CHECK: uno solo), `target_date` (aware UTC),
  `status` (`active` / `completed` / `archived`).
- `fund_entries`: libro **append-only**: `fund_id`, `user_id`, `amount` con signo (aporte > 0,
  retiro < 0), `type` (`contribution` / `withdrawal` / `adjustment`), `occurred_at`, `period`
  (`YYYY-MM` calculado con `core/periods.py` en la zona del usuario), `transaction_id` nullable
  (queda en `NULL` en esta fase; lo usa §2.2), `note`.
- **Saldo del sobre = `SUM(amount)` de sus entradas**; no se guarda columna `balance` (a esta
  escala la suma es barata y no se desincroniza).
- Aportar y retirar toman **row-lock** sobre el sobre (mismo patrón que la Fase 31), con test
  `concurrencia`.
- **Sin cron en v1**: el aporte es una acción explícita ("Aportar $X este mes", con el monto
  sugerido). Servicio propio `app/services/funds.py`, errores con `DomainError`.
- **Fondo de emergencia respaldado solo por una cuenta líquida.** Si el dueño quiere inmovilizar
  parte en un CDT, esa parte deja de contar en el fondo (ver §2.5).

**Resuelto en la Fase 35** (sin `/grilling`, decisiones del agente a revisar por el dueño: spec D1–D10): sin
`UNIQUE (fund_id, period)` y sin idempotencia por header; moneda del sobre = la de su cuenta; no se borra
una cuenta con sobres activos y la alerta "sin respaldo" es `backing_shortfall`; la meta del fondo de
emergencia usa el gasto promedio total de 3 meses (el "gasto esencial" quedó como deuda en
`docs/TODO.md`). **Ajustado tras la primera prueba (2026-10-17, implementado):** los sobres
se pueden borrar además de archivar; el gasto anual exige fecha (es lo que lo distingue de la meta);
el sugerido de aporte explica cuándo la cuota del mes ya está cubierta; y "Disponible real" desglosa
cada moneda (spec, "Ajustes post-uso"). El texto de abajo es el original.

**Pendiente de `/grilling` (original).**
- ¿Una restricción `UNIQUE (fund_id, period)` para aportes? **Se recomienda no ponerla**: impide
  un aporte extra en el mes o dos si se cobra quincenal. La idempotencia se resuelve mejor con la
  clave de idempotencia por request que Oikos ya tiene (`IdempotencyKey`).
- Varios sobres en una cuenta, moneda del sobre = moneda de la cuenta (se propone prohibir el
  resto).
- Qué hacer si la cuenta del sobre se borra o el sobre queda "sin respaldo" (saldos del sobre
  mayores que el de la cuenta): alerta de "sobres sin respaldo".
- Cuánto del "gasto esencial" se define a mano y cuánto se infiere (hoy no hay clasificación
  necesidad/deseo; ver §3).

### 2.2 Disponible real — *Fase 35, junto a los sobres*

**Qué es.** `free_to_spend = saldo de cuentas − Σ saldos de sobres`, expuesto en
`GET /dashboard/summary` junto a `committed`.

**Por qué.**
- Es **lo que obliga**: sin esta cifra los sobres serían ahorro decorativo. Es donde el usuario
  *siente* el cambio de enfoque.
- Cuesta casi nada: es un agregado de solo lectura que depende de §2.1.
- Evita el error clásico de ver $2M en la cuenta y gastar plata que en realidad es del seguro de
  marzo.

**Reglas.** Si el resultado es negativo **no se bloquea nada**: se avisa y se explica
(*"estás gastando plata apartada para el seguro"*), no solo se pinta en rojo — es una herramienta
de un solo dueño y el objetivo es el empujón, no la restricción.

**Pendiente de `/grilling`.** Si el flujo mensual (`monthly_income − gastos`) sigue siendo la
cifra principal del dashboard con el disponible real al lado, o si el disponible real pasa a ser la
principal. **Hasta decidirlo, rige lo vigente:** la cifra principal es el flujo (regla de la
Fase 31: ingreso real − gasto real, `monthly_income` solo es referencia visual).

### 2.3 Gasto contra sobre — *Fase 36* — ✅ **implementado (2026-10-17)**

> **Resuelto en el `/grilling` del 2026-10-17** (`docs/specs/fase_36_spec.md`, D1–D17): el gasto enlazado
> **cuenta como gasto real** y se muestra aparte como **planeado** (`planned_expense`, un desglose que no
> cambia ninguna cifra); si supera el saldo se aplica `min(gasto, saldo)` y el resto es gasto normal; editar
> reajusta y borrar devuelve al sobre; borrar un sobre con gastos enlazados se permite. Las preguntas
> "Pendiente de `/grilling`" de abajo se conservan como historia.

**Qué es.** Al pagar un gasto planeado (el seguro, el computador) se imputa contra el sobre
correspondiente: el sobre baja y la transacción se enlaza (`fund_entries.transaction_id`).

**Por qué.**
- Es **donde las provisiones se vuelven reales**. Sin esto el saldo del sobre solo baja con
  retiros manuales: pagas el seguro, el flujo del mes se hunde y el sobre sigue lleno — justo lo
  que los sobres existen para evitar.
- Tiene su propia fase porque **toca el núcleo contable** (crear/editar/borrar transacción con
  row-lock y delta de saldo, `ledger.py`), que ya tuvo bugs de concurrencia corregidos en la
  Fase 31. Separarlo de §2.1 mantiene esa fase aditiva y de bajo riesgo.

**Pendiente de `/grilling` — la decisión más pesada de todo el plan.**
- **¿Cómo cuenta un gasto con sobre en el flujo del mes?** Inclinación inicial: cuenta en el gasto
  real (no rompe la regla de la Fase 31) pero se muestra **separado como "planeado"**, para que un
  gasto previsto no haga ver el mes como un desastre. Hay que revisar el impacto en KPI,
  presupuestos, alertas y Analítica (5–6 cálculos del backend).
- Qué pasa al editar o borrar la transacción enlazada (¿devuelve el monto al sobre?).
- Qué pasa si el gasto supera el saldo del sobre.

### 2.4 Recurrentes y calendario de cargos anuales — *Fase 37* ✅ implementada 2026-10-18

> Implementada con decisiones D1–D20 del agente, sin `/grilling` (spec `docs/specs/fase_37_spec.md`): la app propone y el dueño confirma; sobres sugeridos desde el calendario quedan para después.

**Qué es.** Ingresos y gastos que se repiten (arriendo, suscripciones, salario), más una línea de
tiempo de los próximos 12 meses con el costo mensualizado de cada obligación y detección de cargos
anuales.

**Por qué.**
- Es la **Fase 35 original** del plan, ya prevista (scheduler desde la Fase 14): reduce fricción de
  captura. Se renumera porque los sobres cambian más la conducta y no dependen de ella.
- Es la base del **pronóstico**: no se puede decir *"llego a fin de mes"* sin saber qué se repite.
- El calendario descubre **obligaciones que no se estaban provisionando** — de ahí nacen los
  sobres sugeridos (cumple el principio de fricción: la app propone, el usuario confirma). Detectar
  suscripciones olvidadas ya ahorra plata por sí solo.

**Pendiente de `/grilling`** (heredado de la Fase 35 original): ¿la regla genera la transacción
sola o propone una para confirmar?; días en que el scheduler no corrió; frecuencia (mensual,
semanal, día 31); editar o saltar una ocurrencia; cuenta y moneda de la regla.

### 2.5 CDT — *Fase 38, independiente*

**Qué es.** Módulo propio para registrar un CDT: capital, tasa E.A., fechas de apertura y
vencimiento, interés causado a hoy y aviso 15 días antes del vencimiento (decidir si se renueva,
redime o reasigna).

**Por qué.**
- Da visibilidad de dinero que está **inmovilizado** y de cuándo se libera, algo que hoy no se ve en
  ninguna parte de la app.
- Es un modelo aislado y de bajo acoplamiento: se puede hacer en cualquier hueco entre fases
  grandes, como victoria rápida.

**Decisión del dueño (2026-10-17): el CDT se mantiene aislado del fondo de emergencia.** El fondo
existe para estar disponible en horas, sin penalización; un CDT lo inmoviliza hasta el
vencimiento. Mezclarlos obligaría a modelar "respaldos con fecha de disponibilidad" y a inflar el
*runway* con dinero que no se podría tocar. Regla resultante: **el fondo solo cuenta lo líquido**.
El CDT cuenta en el patrimonio total (vista de stock), **no** en el disponible real ni en el fondo.

**Resuelto en la Fase 38** (2026-10-18, sin `/grilling`; decisiones D1–D16 del agente en
`docs/specs/fase_38_spec.md`, a revisar por el dueño): tabla propia sin vínculo con cuentas ni transacciones;
interés E.A. compuesto base 365, bruto, calculado por el backend; aviso de vencimiento solo en la UI (≤ 15 días);
**redimir solo cambia de estado** y guarda fecha y monto final (el retorno a una cuenta espera a QA-030);
`cdt_total`/`net_worth` en el dashboard, sin tocar `free_to_spend`. Lo de abajo se conserva como historia.

**Pendiente de `/grilling` (original).**
- *(Resuelto en la Fase 39, 2026-10-24: las transferencias ya existen y el CDT puede vincularse a cuentas.)* Redención: ¿cómo vuelve el dinero a una cuenta sin inflar el flujo? Hoy **no hay transferencias
  entre cuentas** (QA-030): registrarlo como ingreso distorsionaría los KPI. Conviene resolverlo
  junto con QA-030.
- El interés causado se muestra como rendimiento **informativo** y solo se registra como ingreso al
  redimir (no se meten ingresos que todavía no existen en el flujo).

### 2.6 "Págate primero" — *Fase 41*

**Qué es.** Al registrar un ingreso, la app propone el reparto a los sobres (emergencia,
provisiones, metas) **antes** de mostrar el resto como dinero libre. Suma la **tasa de ahorro**
como KPI.

**Por qué.**
- Convierte ahorrar en la decisión por defecto y no en "lo que sobra".
- Va después de los sobres porque **engancha la creación de ingresos** (toca el flujo de
  `ledger.py`) y solo tiene sentido con sobres ya probados y en uso.
- Sin cron, el aporte manual depende de acordarse; este es el paso hacia el aporte que casi se hace
  solo, con el monto sugerido a un toque.

### 2.7 Cierre de mes con puntaje de cumplimiento — *Fase 42*

**Qué es.** Un cierre guiado de 5 minutos: cuánto se ahorró, qué sobres quedaron cortos, qué
categoría se desvió, qué ajustar. Un puntaje simple que combina tasa de ahorro, cobertura del
fondo, sobres al día y cumplimiento del presupuesto.

**Por qué.**
- Hace que el sistema **rinda cuentas** en vez de solo informar; cierra el ciclo de planear →
  ejecutar → revisar.
- Es la última porque necesita datos de todo lo anterior y **infraestructura de jobs mensual por
  zona del usuario** (hoy el único job es el resumen semanal) con snapshot histórico.

---

## 3. Ideas evaluadas y dejadas en el backlog

| Idea | Decisión | Razón |
|---|---|---|
| Simulador "¿me lo puedo permitir?" (impacto de una compra en metas y ahorro, con regla opcional de enfriamiento de 7 días) | Backlog | Es la que más cambia el comportamiento, pero necesita sobres, metas y recurrentes ya funcionando para tener datos que simular. |
| Clasificación necesidad / deseo / ahorro (50/30/20) | Backlog | Le da sentido al "gasto esencial" del fondo de emergencia y al puntaje de §2.7; podría adelantarse en versión mínima si el grilling de §2.1 la pide. |
| Pronóstico de caja a 30/60/90 días | Backlog | Sale casi gratis de recurrentes + sobres; se evalúa después de §2.4. |
| Posiciones en fondos de inversión | **Fuera por ahora** | Valorizaciones manuales y multimoneda complican el rendimiento; hoy el problema es planear gastos, no analizar inversiones. El CDT es el único instrumento que entra. |

---

## 4. Orden y dependencias

```
Fase 35  Sobres + disponible real      (aditiva; sin tocar Transaction)
   │
Fase 36  Gasto contra sobre            ✅ implementada 2026-10-17
   │
Fase 37  Recurrentes + calendario      ✅ implementada 2026-10-18 (heredada de la Fase 35 original)
   │
Fase 38  CDT                           (independiente: puede ir en cualquier hueco)
   │
Fase 39  Transferencias + CDT vinculado ✅ implementada 2026-10-24 (cierra QA-030)
   │
Fase 41  Págate primero                (necesita sobres probados)
   │
Fase 42  Cierre de mes + puntaje       (necesita jobs mensuales y datos de todo lo anterior)
```

Cada fase sigue el workflow completo de `docs/WORKFLOW.md` (`/grilling` → `/to-spec` →
`/analyze-spec` → implementar → `/run-tests` → `/code-review` → `/analyze-spec` de cierre → docs de
cierre → PR). Las fases 35 y 36 **no se fusionan** a propósito: la primera es aditiva y de bajo
riesgo, la segunda modifica el núcleo contable.

---

## 5. Glosario provisional

Hasta que exista `CONTEXT.md` (se crea cuando los términos queden resueltos, no por adelantado),
estos son los términos de la dirección:

- **Sobre** (*fund*): reserva virtual de dinero sobre una cuenta; no mueve plata real.
- **Comprometido**: suma de los saldos de todos los sobres activos.
- **Disponible real** (*free to spend*): saldo de las cuentas menos lo comprometido.
- **Aporte requerido**: `(meta − saldo) / meses restantes`, calculado por el servidor.
- **Runway**: meses de gasto que cubre la parte **líquida** del fondo de emergencia.
- **Gasto planeado**: gasto imputado contra un sobre.
