# Reglas de negocio

## Usuarios y autenticación

- El correo debe ser único.
- El nombre completo (`full_name`) es obligatorio al registrar un usuario.
- La contraseña se guarda hasheada con bcrypt.
- El JWT identifica al usuario mediante `sub`.
- El login usa `OAuth2PasswordRequestForm` y recibe el correo en el campo `username`.

## Cuentas

- Una cuenta pertenece a un único usuario.
- `balance` puede definirse al crear la cuenta, pero solo como saldo inicial.
- En edición, `balance` no debe ser modificable por el Frontend.
- El saldo real se deriva de transacciones e impactos contables.
- `highlighted` marca una cuenta como destacada para el dashboard. Si no hay cuentas destacadas, el dashboard muestra todas.

## Categorías

- Las categorías con `user_id = null` son categorías base del sistema.
- Las categorías personalizadas pertenecen a un usuario específico.
- Las categorías base no se pueden editar ni borrar desde la API.
- Al iniciar la aplicación se siembran categorías base y se corrigen nombres heredados de categorías base antiguas.

## Transacciones

- Cada transacción debe pertenecer al usuario autenticado.
- La cuenta asociada debe pertenecer al mismo usuario.
- La categoría asociada debe ser propia del usuario o una categoría base.
- `income` suma al saldo de la cuenta.
- `expense` resta del saldo de la cuenta.
- Al borrar una transacción se revierte su impacto sobre la cuenta.
- Al editar una transacción se revierte el efecto anterior y se aplica el nuevo.
- Las consultas de listado permiten filtrar por cuenta, categoría y rango de fechas.
- Si el rango de fechas está invertido, la API responde con error de validación.

## Presupuestos

- Un usuario solo puede tener un presupuesto por categoría, mes y año.
- La categoría del presupuesto debe existir y estar disponible para el usuario.
- El progreso del presupuesto se calcula sobre gastos del mes actual.
- Los presupuestos también pueden listarse por mes y año.

## Eliminaciones

- No se puede borrar una cuenta con transacciones.
- No se puede borrar una categoría con transacciones.
- No se puede borrar una categoría con presupuestos activos.
- No se pueden borrar categorías base del sistema.
- No se puede borrar una cuenta o categoría ajena al usuario autenticado.
- No se puede borrar ni editar una categoría base del sistema.

## Dashboard

- El resumen usa datos agregados del backend.
- El progreso de presupuestos ya sale calculado para uso directo del Frontend.
- El dashboard expone además serie temporal de flujo de caja y distribución por categoría.