# Spec — Flujo corto: apagar la recurrencia de un presupuesto

> Sintetiza el `/grilling` corto del 2026-10-03 (decisiones **Q1–Q4**, todas con la opción
> recomendada) sobre el pendiente "Apagar la recurrencia de un presupuesto desde la UI" de
> `docs/ROADMAP.md` (hallado al revisar el PR #11, relacionado con QA-024).
>
> Sin número de fase a propósito: el 33 está reservado a ingresos/gastos recurrentes. Es spec
> (flujo completo de `docs/WORKFLOW.md`) y no flujo corto puro porque cambia una regla de
> `BUSINESS_RULES.md` y toca backend y frontend, aunque el cambio de frontend sea solo copy.
>
> **No implementa nada.** Solo se agregó este archivo.

**Estado:** implementada el 2026-10-03 (rama `feat/corto-recurrencia-presupuestos`); spec escrita el 2026-10-03. Sin marcadores abiertos. `/analyze-spec` (2026-10-03):
2 ALTO, 3 MEDIO y 2 BAJO; los dos ALTO se resolvieron con el dueño el mismo día (ver "Decisiones
resueltas con el usuario") y todos los hallazgos se aplicaron a esta spec.

---

## Problem Statement

Un presupuesto con "Repetir cada mes" no se puede apagar. Si en el mes actual se desmarca la
casilla, esa fila queda en `is_recurring=False`, pero `ensure_recurring_budgets_for_period`
elige como plantilla "la fila recurrente más reciente de **otro** período" y entonces encuentra
la del mes anterior. El mes siguiente se genera con el monto viejo y vuelve a ser recurrente: la
serie nunca se corta y el usuario ni siquiera ve la plantilla que la mantiene viva. Hoy la única
salida es editar a mano una fila de un mes pasado.

Mismo problema si ya se visitó un mes futuro: esa fila generada es recurrente y alimenta a las
siguientes.

## Solution

Desmarcar "Repetir cada mes" en un presupuesto significa **"de aquí en adelante no repitas"**:

- Los meses anteriores no cambian y conservan su marca "recurrente".
- El mes editado queda como presupuesto normal, con su monto.
- Los meses posteriores que ya existían de esa categoría siguen existiendo con su monto, pero
  dejan de ser recurrentes.
- Los meses posteriores que no existían no se generan.
- Volver a marcar la casilla en cualquier mes reinicia la serie desde ese mes.
- La serie se identifica por **categoría y moneda**: desmarcar la de COP no toca la de USD de la
  misma categoría.
- Consecuencia que se acepta: un presupuesto manual **no recurrente** de la misma categoría y
  moneda en un mes posterior a la serie también la corta desde ese mes (la fila más reciente
  decide).

Borrar un presupuesto sigue siendo "saltar solo este mes" (QA-024); desmarcar y borrar son
acciones distintas. En el modal, debajo de la casilla, un texto aclara qué pasa al desmarcar.

## User Stories

1. Como dueño, quiero desmarcar "Repetir cada mes" en el presupuesto de este mes, para que el
   mes siguiente no aparezca solo.
2. Como dueño, quiero que desmarcar no toque los meses pasados, para que el historial conserve
   su marca de recurrente.
3. Como dueño, quiero que el presupuesto del mes en que desmarqué conserve su monto, para no
   perder el límite de ese mes.
4. Como dueño, quiero que desmarcar corte también los meses futuros que ya se habían generado,
   para no tener que desmarcarlos uno por uno.
5. Como dueño, quiero que esos meses futuros conserven su monto aunque dejen de ser recurrentes,
   para no perder presupuestos que quizá edité a mano.
6. Como dueño, quiero que desmarcar afecte solo a la categoría editada, para que mis otros
   presupuestos recurrentes sigan funcionando.
7. Como dueño, quiero poder volver a marcar la casilla meses después y que la serie reinicie
   desde ahí, para retomar la recurrencia sin pasos extra.
8. Como dueño, quiero que borrar un presupuesto siga saltando solo ese mes, para distinguirlo de
   "dejar de repetir".
9. Como dueño, quiero leer en el modal qué pasa al desmarcar, para no tener que adivinarlo.
10. Como dueño, quiero que desmarcar el presupuesto en una moneda no toque el de otra moneda de
    la misma categoría, para cortar solo la serie que quise.
11. Como dueño, quiero saber que crear a mano un presupuesto no recurrente en un mes posterior
    termina la serie desde ahí, para que no me sorprenda.

## Implementation Decisions

**B1 — Regla de plantilla (Q3 a).** Una **serie** es el conjunto de presupuestos de un usuario
con la misma categoría **y la misma moneda** (D4). En la generación perezosa, la plantilla de una
serie es su fila **activa** más reciente en un período **estrictamente anterior** al pedido, y se
clona **solo si esa fila es recurrente**. La fila más reciente decide: si no es recurrente, no se
genera nada. Como el índice único es `(user, category, month, year, currency)`, hay a lo sumo una
fila activa por serie y período, así que no hay empates. No hay columna ni migración. Reemplaza
la regla vigente "fila recurrente más reciente de la categoría en cualquier otro período".
Consecuencia aceptada (D3): cualquier fila no recurrente de la serie, creada a mano o por
desmarcar, es la que decide si es la más reciente.

**B2 — Solo períodos anteriores.** Una fila de un período posterior ya no puede servir de
plantilla. Aplica a los tres llamadores de `ensure_recurring_budgets_for_period`, que heredan B1
y B2: `GET /budgets/` (`api/budgets.py`), `GET /dashboard/budgets-progress` (`api/dashboard.py`)
y el motor de alertas (`core/budget_alerts.py`). Efecto lateral buscado: pedir un mes anterior al inicio de la serie deja de generar
filas hacia atrás (reduce el efecto de escritura de `GET /budgets/` en meses cerrados, ítem
abierto en `docs/TODO.md`). No lo cierra: sigue habiendo escritura al pedir meses posteriores.

**B3 — La lápida no cambia (QA-024), salvo la clave.** La fila soft-deleted del período pedido
sigue bloqueando la generación de ese período (consulta Core vía `db.connection()`). Como la
serie ahora es categoría + moneda (B1), el chequeo "ya hay fila o lápida en el período" pasa de
ser por categoría a ser por `(categoría, moneda)`; si no, la fila en USD bloquearía la
generación de la serie en COP. Las filas soft-deleted de
períodos anteriores no cuentan como plantilla (filtro global de borrado lógico), así que borrar
el mes M deja a M-1 como "la más reciente activa" y la serie sigue.

**B4 — Corte hacia adelante en `PUT /budgets/{id}` (Q1 a, Q4 a).** Cuando el `PUT` cambia
`is_recurring` de `True` a `False`, en la misma transacción de base de datos se ponen en
`is_recurring=False` las filas de la misma **serie** (categoría y moneda **resultantes** tras
aplicar el `PUT`) con período estrictamente posterior al de la fila editada (también el
resultante). Sin tocar montos ni borrar. Detalles:

- El filtro incluye `deleted_at IS NULL` **explícito** (precedente: el `update()` de
  `services/ledger.py`, Decisión 6.1). Las lápidas no se tocan.
- `updated_at` de las filas afectadas se actualiza como en cualquier edición.
- No se tocan períodos anteriores, otras categorías ni otras monedas de la misma categoría.
- Si el mismo `PUT` cambia la categoría o la moneda, el corte aplica a la serie resultante; la
  serie de origen no se corta (la fila editada simplemente salió de ella).
- Solo se dispara en la transición `True → False`, no cuando la fila ya llegaba en `False`.

**B5 — Sin cambio de contrato.** Mismo endpoint, mismo schema, mismos códigos. Solo cambia el
efecto de `is_recurring: false`. `POST` con `is_recurring: true` reinicia la serie sin lógica
extra (la fila nueva pasa a ser la más reciente).

**F1 — Copy (Q2 a).** En `budgets/page.tsx`, el texto bajo la casilla "Repetir cada mes" se
reemplaza por uno que cubra los dos estados: seguirá creándose cada mes con el mismo monto, y al
desmarcar no se generará en los meses siguientes. Sin cambio de lógica ni de componentes. Texto
exacto a definir al implementar, sin prometer cosas que el backend no hace (por ejemplo, no
decir que borra los meses futuros).

**D1 — Docs.** Ambos contratos en el mismo cambio (convención transversal de `AGENTS.md`):
`backend/docs/API_REFERENCE.md` (descripción de `is_recurring` en `POST`/`PUT /budgets`, que hoy
dice que apagar es editar con `false` sin aclarar el alcance) y `frontend/docs/API_CONTRACT.md`
(líneas ~212, 485 y 486: la de 485 afirma que `GET /budgets/?month=&year=` genera en períodos
cerrados, y B2 lo cambia en parte). `backend/docs/BUSINESS_RULES.md`: editar la sección
"Presupuestos" (regla de serie, generación, corte y la consecuencia de D3). `docs/TODO.md` y
`docs/ROADMAP.md`: marcar el pendiente resuelto y anotar B2 sobre el ítem de meses cerrados.

**D3 — Un presupuesto manual no recurrente corta la serie (resuelto con el dueño).** Crear a
mano, o volver a crear tras borrar, un presupuesto no recurrente de la misma serie en un mes
posterior a la serie la termina desde ese mes. Es la misma regla de B1, no un caso aparte, pero se
nombra porque el modal de crear arranca con la casilla desmarcada y el dueño lo notaría.

**D4 — La serie es categoría + moneda (resuelto con el dueño).** Se aplica en B1, B3 y B4.

## Testing Decisions

Buen test: ejercita el comportamiento externo (qué filas existen o no después de un `PUT` y de
una lectura de período), no la forma de la consulta.

Seam principal: `GET`/`PUT /budgets/` por HTTP (`test_budgets.py`). Seam secundario:
`ensure_recurring_budgets_for_period` directa (`test_budget_recurrence.py`), donde ya viven los
tests de la lápida y de plantilla con gap. Precedente: los tests de QA-024.

Casos:

1. **Aceptación del ROADMAP:** serie de 3 meses recurrentes → desmarcar el actual → el mes
   siguiente no se genera.
2. Los meses anteriores conservan `is_recurring=True` y su monto.
3. El mes editado conserva su monto con `is_recurring=False`.
4. Mes futuro ya generado: pasa a `False`, conserva monto, y el mes que le sigue no se genera.
5. Otra categoría recurrente del mismo usuario no se afecta.
6. Re-marcar meses después reinicia la serie desde ese mes, por ambos caminos: `PUT` con
   `is_recurring=true` sobre una fila posterior, y `POST` de una fila nueva recurrente.
7. Borrar (lápida) sigue saltando solo ese mes y la serie continúa desde el mes anterior.
8. Pedir un mes anterior al inicio de la serie no genera filas (B2).
9. Un `PUT` que ya llega con `is_recurring=False` no toca filas posteriores.
10. Los presupuestos de otro usuario no se tocan.
11. **D3:** una fila manual no recurrente en un mes posterior a la serie corta la generación
    desde ahí; y borrar el mes M (lápida) y volver a crearlo sin marcar la casilla también.
12. **D4:** una categoría con la misma serie en COP y en USD; desmarcar la de COP deja la de
    USD generando, y viceversa. La fila de USD de un período no bloquea la generación de la
    serie en COP (B3).
13. **B2 / llamadores:** `GET /dashboard/budgets-progress` del mes actual y el motor de alertas
    siguen generando desde la fila del mes anterior (los tres llamadores heredan B1).
14. **B4:** una lápida posterior no cambia ni se toca; `updated_at` de las filas cortadas se
    actualiza; un `PUT` que cambia la categoría o la moneda al desmarcar corta la serie
    resultante y no la de origen.

## Out of Scope

- Un botón o acción explícita "Dejar de repetir" (Q2 b).
- Columna nueva para marcar el fin de la serie (Q3 c).
- Soft-delete de los meses futuros al desmarcar (Q4 b).
- Frontend de pruebas automáticas (fuera de scope en el roadmap): la verificación de F1 es
  manual en el navegador.

## Further Notes

- Una consecuencia a tener presente: desmarcar un presupuesto **antiguo** (por ejemplo, el de
  hace tres meses con filas posteriores recurrentes) corta también todas las posteriores, por
  Q1 "desde ese mes en adelante". Es el comportamiento acordado.
- Los tests existentes de `test_budget_recurrence.py` (lápida, plantilla con gap, rollover de
  año) y el de `test_dashboard.py` del mes actual generado desde el mes pasado son compatibles
  con B1; el cambio de la clave a `(categoría, moneda)` en B3 hay que revalidarlo contra ellos.
- Las filas que B4 deja en `False` pierden el badge "recurrente" en la lista; los meses
  anteriores lo conservan.

## Orden de ejecución

1. [backend] Regla de plantilla y generación en `core/budget_recurrence.py` — B1, B2, B3, D4.
   Depende de: —
2. [backend] Corte hacia adelante en `PUT /budgets/{id}` (`api/budgets.py`) — B4, B5, D4.
   Depende de: 1 (la regla de generación define qué cuenta como "serie")
3. [verif] Tests de los casos 1–14 en `test_budget_recurrence.py` y `test_budgets.py`.
   Depende de: 1, 2
4. [frontend] [P] Copy bajo la casilla en `budgets/page.tsx` — F1.
   Depende de: —
5. [docs] BUSINESS_RULES, API_REFERENCE, API_CONTRACT (frontend), TODO y ROADMAP — D1, D3.
   Depende de: 1, 2
6. [verif] Prueba manual en el navegador (stack `-p oikos-dev`, nunca producción): serie de
   3 meses, desmarcar, navegar al mes siguiente.
   Depende de: 1, 2, 4

## Decisiones resueltas con el usuario (2026-10-03)

- **Q1 a** — desmarcar corta la serie hacia adelante desde ese mes.
- **Q2 a** — se deja la casilla y se agrega copy que explique qué pasa al desmarcar.
- **Q3 a** — la plantilla es la fila activa más reciente en un período anterior, y solo se
  genera si es recurrente; sin columna nueva.
- **Q4 a** — los meses futuros ya generados pasan a no recurrentes y conservan su monto.
- **D3** (hallazgo ALTO de `/analyze-spec`) — se acepta que un presupuesto manual no recurrente
  posterior corte la serie.
- **D4** (hallazgo ALTO de `/analyze-spec`) — la serie se identifica por categoría y moneda.
