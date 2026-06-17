# Reglas de negocio

## Usuarios y autenticación

- El correo debe ser único.
- La contraseña se guarda hasheada con bcrypt.
- El JWT identifica al usuario mediante `sub`.

## Cuentas

- Una cuenta pertenece a un único usuario.
- `balance` puede definirse al crear la cuenta.
- En edición, `balance` no debe ser modificable por el Frontend.
- El saldo real se deriva de transacciones e impactos contables.

## Categorías

- Las categorías con `user_id = null` son categorías base del sistema.
- Las categorías personalizadas pertenecen a un usuario específico.
- Las categorías base no se pueden editar ni borrar desde la API.

## Transacciones

- Cada transacción debe pertenecer al usuario autenticado.
- La cuenta asociada debe pertenecer al mismo usuario.
- La categoría asociada debe ser propia del usuario o una categoría base.
- `income` suma al saldo de la cuenta.
- `expense` resta del saldo de la cuenta.
- Al borrar una transacción se revierte su impacto sobre la cuenta.
- Al editar una transacción se revierte el efecto anterior y se aplica el nuevo.

## Presupuestos

- Un usuario solo puede tener un presupuesto por categoría, mes y año.
- La categoría del presupuesto debe existir y estar disponible para el usuario.
- El progreso del presupuesto se calcula sobre gastos del mes actual.

## Eliminaciones

- No se puede borrar una cuenta con transacciones.
- No se puede borrar una categoría con transacciones.
- No se puede borrar una categoría con presupuestos activos.
- No se pueden borrar categorías base del sistema.

## Dashboard

- El resumen usa datos agregados del backend.
- El progreso de presupuestos ya sale calculado para uso directo del Frontend.