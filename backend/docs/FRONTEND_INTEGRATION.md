# Guía de integración para Frontend

## Autenticación

1. Registrar usuario en `POST /api/users/`.
2. Hacer login con `POST /api/auth/login` usando formulario OAuth2.
3. Guardar el token en memoria o en cookie segura según la estrategia del Frontend.
4. Enviar el token en `Authorization: Bearer <token>` para todas las rutas protegidas.

## Campos que el Frontend debe enviar

- `full_name` al registrar usuarios.
- `username` y `password` en el login OAuth2, donde `username` representa el correo.

## Datos que el Frontend no debe recalcular

- Saldos de cuentas.
- Progreso de presupuestos.
- Totales del dashboard.
- Reglas de borrado de entidades relacionadas.

## Contratos de dinero

- Tratar saldos, montos y presupuestos como valores decimales, no como `float`.
- Mantener el porcentaje de progreso como valor de presentación.

## Contratos importantes

- No enviar `user_id` en cuentas, categorías, transacciones ni presupuestos.
- No enviar `balance` en edición de cuentas.
- No asumir que una categoría es editable si su `user_id` es `null`.
- No permitir transacciones sin cuenta y categoría válidas.

## Pantallas y endpoints de apoyo

- Usuario autenticado: `GET /api/users/me`.
- Dashboard: `GET /api/dashboard/summary`, `GET /api/dashboard/budgets-progress`, `GET /api/dashboard/cashflow-series` y `GET /api/dashboard/category-distribution`.
- Cuentas: `GET /api/accounts/` y `GET /api/accounts/{account_id}`.
- Transacciones: `GET /api/transactions/` con filtros por cuenta, categoría y fechas.
- Presupuestos: `GET /api/budgets/` con filtros por mes y año.

## Manejo de errores

- `401`: token ausente o inválido.
- `403`: credenciales inválidas o acción no permitida.
- `404`: recurso inexistente o no perteneciente al usuario.
- `400`: validación de negocio fallida, como duplicados, fechas invertidas o relaciones bloqueadas.
- `500`: fallo interno al recalcular saldos en transacciones.

## Recomendaciones para el equipo de Frontend

- Mostrar mensajes de error del backend de forma consistente.
- Deshabilitar formularios que dependan de entidades bloqueadas.
- No duplicar cálculos de saldo o progreso en el cliente.
- Tratar al dashboard como fuente de verdad para métricas agregadas.
- Prepararse para respuestas con `Decimal` serializado en JSON como número o string según el cliente.