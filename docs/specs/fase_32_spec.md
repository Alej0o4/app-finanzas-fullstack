# Spec — Fase 32: suite de tests sobre Postgres por defecto

> Sintetiza el `/grilling` del 2026-09-27, registrado en `docs/ROADMAP.md` §"Fase 32"
> (decisiones **Q1–Q10** y 6 supuestos aceptados), y el inventario de `docs/TODO.md`
> §"Deuda nueva consciente de la Fase 31" (el ítem "Insumo de la Fase 32"). Esas decisiones
> las tomó el dueño y esta spec no las reabre: las cita por su número y las baja a decisiones
> implementables **B** (backend/conftest y tests), **I** (infra/dependencias), **T** (testing) y
> **D** (docs), con la misma convención que `fase_29_spec.md`, `fase_30_spec.md` y
> `fase_31_spec.md`.
>
> Antes de escribirla se midió y se ejecutó el terreno contra un `postgres:16-alpine` desechable
> (2026-09-27, `main`): se reprodujo el único fallo de la suite en Postgres, se validó el
> mecanismo de Q4, el aislamiento del test de drift y el de `test_seed.py`, y se corrigieron
> seis referencias/cifras desactualizadas del registro del grilling. Ver "Hallazgos de
> exploración".
>
> **No implementa nada.** Solo se agregó este archivo (y las correcciones de referencia del
> ROADMAP que se listan abajo, que no cambian ninguna decisión).

**Estado:** spec escrita el 2026-09-28, con el único marcador `[NEEDS CLARIFICATION]` (B6)
resuelto con el dueño ese mismo día: opción (A), marcar `TestUpdatedAt` con
`@pytest.mark.concurrencia` y **asumir** que ese test no corre en el opt-in de SQLite (10 skips
en ese modo, en vez de 9). Sin marcadores vivos y con `/analyze-spec` en modo
pre-implementación sin hallazgos ALTO/MEDIO, la spec está **lista para implementar**
(`docs/WORKFLOW.md` paso 4).

---

## Problem Statement

La suite corre contra SQLite en memoria mientras producción corre en Postgres 16, y esa
diferencia ya mordió dos veces: QA-003 (SQLite serializa las escrituras, no aplica
`FOR UPDATE` — los tests de concurrencia real no podían existir) y QA-015 (SQLite no aplica
`Numeric(14,2)` — el desborde de saldo no se podía reproducir). La Fase 31 abrió la puerta
(`TEST_DATABASE_URL` + marker `postgres`) y midió que la suite completa da **349 pasan, 1
falla** contra Postgres, pero dejó el default en SQLite: correr la suite "de verdad" sigue
significando correrla en el motor equivocado, y el motor equivocado es el que no detecta la
mayoría de los bugs que importan.

Pequeño pero real: hoy `pytest` **no necesita Docker**, y esa es la mitad de su valor — es el
sustituto manual de CI (`/run-tests`), y si "no levanté la DB" es un paso extra, el gate se
deja de correr. Al revés también: si el default fuera "una base larga de compose", un
`pytest` sin pensar apuntaría a la base real — que es exactamente el accidente de QA-002/QA-001.

Y hay un agujero de verificación que esta fase cierra de paso: **nada** comprueba que la
cadena de migraciones de Alembic coincida con `models.py`. Hoy un modelo editado sin migración
pasa los 350 tests en verde y revienta en el `CMD` de Docker.

## Solution

- **Postgres por default, sin fricción.** `pytest` levanta y destruye un `postgres:16-alpine`
  desechable por sesión con `testcontainers`; una `TEST_DATABASE_URL` explícita tiene
  prioridad. El argumento es la fricción, no la velocidad: Postgres es ~10 % más lento que
  SQLite y eso es irrelevante contra los ~2,5 min de suite, mientras que "no levanté la DB" sí
  desincentiva.
- **SQLite sobrevive como opt-in explícito** (`TEST_DATABASE_URL=sqlite://`), nunca como
  fallback automático. Un `pytest` "verde" en SQLite cuando se pidió Postgres es la clase de
  bug que esta fase viene a matar.
- **Sin Docker, un mensaje accionable y exit code 2** — nunca un fallback silencioso ni un
  skip que deje la suite "verde" con 350 saltados.
- **El marker deja de ser de motor y pasa a ser de aislamiento**: `postgres` → `concurrencia`,
  fixtures `pg_*` → `real_*`, `test_concurrency_pg.py` → `test_concurrency.py`. En SQLite se
  autoskippea por "requiere sesiones reales por request", no por "no hay Postgres".
- **Una guardia de drift**: `alembic check` como test de sesión, contra una base migrada a
  `head` propia (la base de la suite la deja `create_all`, sin `alembic_version`, y contra esa
  el chequeo no sirve).
- **Un test arreglado, no producción**: el `PUT` de `TestUpdatedAt` sale de la transacción
  externa de `db_session` por el seam de sesión real por request, que es donde `now()` puede
  avanzar. Al usar el seam, el test queda marcado `concurrencia`: corre en el default de
  Postgres y se salta en el opt-in de SQLite —consecuencia asumida, ver B6.
- **`test_seed.py` conserva su motor propio**, parametrizado por dialecto, y en Postgres se
  aísla en un esquema propio: se verificó que un commit real en la base compartida rompe otro
  test de la suite.

## User Stories

**Correr la suite**

1. Como dueño-desarrollador, quiero que `cd backend && pytest` levante solo su Postgres
   desechable, para que el gate no dependa de que me acuerde de levantar una base.
2. Como dueño-desarrollador, quiero que el contenedor se destruya al terminar la sesión, para
   no dejar imágenes de Docker ni puertos ocupados en mi máquina.
3. Como dueño-desarrollador, quiero que el default sea el motor de producción (Postgres 16 con
   la misma imagen que `docker-compose.yml`), para que la suite mida lo que producción corre.
4. Como dueño-desarrollador, quiero `TEST_DATABASE_URL=postgresql://…` con prioridad sobre
   testcontainers, para poder apuntar la suite a un Postgres propio cuando estoy depurando
   justo el tema de la conexión.
5. Como dueño-desarrollador, quiero `TEST_DATABASE_URL=sqlite://` para correr la suite sin
   Docker, para tener un camino offline que además ejercita la rama SQLite de
   `engine_kwargs_for_url` (que es código de producción).
6. Como dueño-desarrollador, quiero que la suite **aborte** si `TEST_DATABASE_URL` apunta a una
   base sin "test" en el nombre, para no hacer `drop_all` sobre la base real por un typo.
7. Como dueño-desarrollador, quiero que la suite **no** haga `drop_all` sobre una `sqlite://`,
   porque una SQLite en memoria no tiene nombre de base que proteger y la guarda no aplica.
8. Como dueño-desarrollador sin Docker quiero un mensaje que me diga las tres salidas
   (levantar Docker / `TEST_DATABASE_URL` / `sqlite://`) y un exit code distinto de cero, para
   no leer "todo verde" cuando en realidad no corrió nada.
9. Como dueño-desarrollador, quiero que el arranque fallido por imagen o permisos salga como un
   error de una línea, no como una cadena de tracebacks de testcontainers.
10. Como dueño-desarrollador, quiero que `pytest --collect-only` no levante un contenedor, para
    poder listar tests sin pagar los ~9 s de arranque.
11. Como dueño-desarrollador, quiero saber con qué motor corrió la suite, para no confundir un
    verde de SQLite con uno de Postgres.

**Lo que el cambio de motor debe proteger**

12. Como dueño-desarrollador, quiero que los tests de concurrencia real sigan siendo
    autoskip en SQLite, para no creer que probé `FOR UPDATE` cuando el motor no lo soporta.
13. Como dueño-desarrollador, quiero que el motivo del skip sea "requiere sesiones reales por
    request" y no "no hay Postgres", para no pensar que un marker opcional se puede apagar.
14. Como dueño-desarrollador, quiero que el test de `updated_at` vuelva a pasar en Postgres, para
    que una suite verde signifique algo.
15. Como dueño-desarrollador, quiero que el test de `updated_at` siga siendo **un** test, para
    que la garantía ("leer no mueve `updated_at`, escribir sí") se lea de un vistazo y no en
    dos piezas que podrían desincronizarse.
16. Como dueño-desarrollador, quiero que el teardown del seam real siga limpiando **todas** las
    tablas, incluidas las que no están en su lista (`budgets`, `notifications`,
    `push_subscriptions`…), para que un test de sesiones reales no ensucie el resto de la sesión.
17. Como dueño-desarrollador, quiero que `test_seed.py` siga detectando el borrado incompleto de
    usuario, para que la cascada de `delete_user_cascade` no vuelva a perder una tabla hija.
18. Como dueño-desarrollador, quiero que ese test siga teniendo FKs aplicadas en los dos
    motores, para que no sea el falso verde que su propio docstring dice evitar.
19. Como dueño-desarrollador, quiero que `test_seed.py` no deje filas comprometidas en la base
    de la suite, para no romper tests posteriores que cuentan filas globalmente.

**La nueva guardia de drift**

20. Como dueño-desarrollador, quiero que la suite falle si edité `models.py` sin escribir la
    migración, para que no descubra el problema en el `CMD` de Docker.
21. Como dueño-desarrollador, quiero que esa guardia corra en los dos motores, para que el opt-in
    de SQLite no se convierta en un modo donde el drift no se ve.
22. Como dueño-desarrollador, quiero que el mensaje de drift diga qué hacer (`/alembic-migration`)
    y pegue la salida de alembic, para no tener que reproducirlo a mano.
23. Como dueño-desarrollador, quiero que la guardia use su propia base, para que no dependa del
    estado que dejó la suite con `create_all`.

**Cierre y documentación**

24. Como dueño, quiero que la suite se corra completa en **los dos** motores antes de cerrar la
    fase, para no dejar el modo SQLite sin ejercitar justo en el cambio de default.
25. Como dueño, quiero que `AGENTS.md` y la skill `run-tests` digan cómo correr la suite hoy, para
    que ni yo ni un agente futuro corran el comando viejo.
26. Como dueño, quiero que la receta `docker run` sobreviva reducida a una línea como override,
    porque es el camino cuando el problema **es** testcontainers.
27. Como dueño, quiero que el item de `docs/TODO.md` que inventarió el fallo de `updated_at`
    quede marcado como resuelto con su fecha, para que el backlog no vuelva a sacar ese ítem a la cabeza.
28. Como dueño, quiero que quede anotado por qué **no** hay `pytest-xdist` todavía, para no
    re-litigar el paralelismo sin leer el bloqueo.

## Hallazgos de exploración

Todo verificado contra `main` el 2026-09-27/28 con un `postgres:16-alpine` desechable en
tmpfs (puerto 5433, base `oikos_test`) y con la receta de `AGENTS.md`. Los primeros cuatro
puntos son correcciones al registro del grilling en `docs/ROADMAP.md` (esas correcciones ya
están aplicadas al roadmap; ninguna cambia una decisión).

**Referencias y mediciones del roadmap que hubo que corregir**

1. **`alembic/env.py:31` no es `engine_from_config`** — la línea 31 es un comentario; la llamada
   está en `env.py:66-70`. La observación (que usa `engine_from_config` sin el
   `options: -c timezone=UTC` de `engine_kwargs_for_url`) es correcta; la referencia no.
2. **"las 13 migraciones" son 12** (`alembic/versions/*.py` = 12, y `alembic history` = 12
   revisiones). El resto de la afirmación del roadmap (aplican limpio, sin drift) se verificó;
   lo que se le agregó es la salvedad de que ese `check` solo vale contra una base **migrada**
   (hallazgo 15): contra la que arma `create_all` da un falso positivo.
3. **`.agents/skills/run-tests/SKILL.md:16` no "nombra la base de test"**: la línea 16 es
   `cd backend && ./venv/bin/pytest -v`. El punto correcto es el paso 1 de la skill
   (líneas 14-17), que es lo que hay que actualizar.
4. **`test_seed.py:1-8` → `1-9`**: el docstring cierra en la línea 9. En el mismo ítem,
   `test_seed.py:45-56` → `46-55` (45 es el `def` del test y 56 el `sessionmaker`; el engine con
   el `PRAGMA` está en 46-55).
5. **`AGENTS.md:139,144-154` → `138,143-154`**: el bloque §Tests arranca en 138 (`pytest` pelado)
   y el párrafo de Postgres en 143.
6. **El arranque del contenedor cuesta ~8,6 s, no 1-3 s.** Medido con
   `PostgresContainer("postgres:16-alpine")`: incluye el contenedor *reaper* (Ryuk) que
   testcontainers levanta para la limpieza, la espera de readiness y la primera conexión. Es
   ~6 % de los ~150 s de suite: no cambia el argumento de Q1 (que era fricción, no velocidad),
   pero el número del roadmap era optimista.

**Hechos nuevos que el roadmap no registraba**

7. **`TEST_DATABASE_URL=sqlite://` hoy no arranca.** Reproducido: la guarda de `conftest.py:42-53`
   exige "test" en el nombre de la base y el path de una `sqlite://` en memoria es vacío →
   `RuntimeError` al importar el conftest. Es la prueba directa de por qué Q7 necesita la
   guarda "solo para Postgres".
8. **Blast radius del renombre, más amplio que los 5 archivos que lista el roadmap.** Además de
   `conftest.py`, `test_concurrency_pg.py` y `test_money_limits.py`, quedan referencias al
   marker y al nombre del archivo en: `test_money_limits.py:6-7` y `:211-212` (docstrings),
   `test_transactions.py:182` (docstring), `test_database.py:2,5` (docstring),
   `docs/TODO.md:79` y `docs/CHANGELOG.md:20`. La línea de corte es **vivo vs. registro**: los
   cuatro docstrings de tests describen el seam *actual* y hay que corregirlos (los de
   `test_money_limits.py` los cubre B7), mientras que `docs/TODO.md:79` y `docs/CHANGELOG.md:20`
   son la resolución de QA-003 tal como quedó en su día —"intercalado determinista en SQLite +
   `tests/test_concurrency_pg.py` (marker `postgres`)"— y quedan como historia, igual que las
   specs de las Fases 7/20/29. Lo que sí cambia de verdad en `docs/TODO.md` son los dos agregados
   de D1 (marcar el ítem de Q4, dar de alta `pytest-xdist`).
9. **El esquema de URL que devuelve testcontainers (`postgresql+psycopg2://`) no rompe nada.**
   `engine_kwargs_for_url` corta por prefijo `"postgresql"`, así que el `options: -c
   timezone=UTC` sigue aplicándose. Verificado corriendo `test_soft_delete.py`,
   `test_money_limits.py` y `test_database.py` con ese esquema: 27 pasan, 1 falla (el fallo
   conocido de Q4).
10. **`testcontainers.postgres` está deprecado** en 4.15.0 (`DeprecationWarning: use
   testcontainers.community.postgres`). La URL de `postgres:16-alpine` con credenciales
   explícitas queda `postgresql+psycopg2://oikos:oikos_test@localhost:<puerto>/oikos_test`.
   Transitivos nuevos: `docker` (7.2.0) y `wrapt`; ni `requests` ni `urllib3` chocan con los
   pines actuales.
11. **`testcontainers` lee `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` del entorno** como
    defaults. Si el shell del dueño tiene esas variables exportadas, el contenedor de tests
    nace con otro usuario y otra base → hay que pasar las credenciales explícitas.
12. **`ContainerStartException` NO hereda de `DockerException`** (es `RuntimeError`): hay que
    capturar las dos para que "no hay Docker" y "la imagen no arrancó" den el mismo mensaje
    accionable.
13. **El teardown del seam real (`TRUNCATE … CASCADE`) limpia las 13 tablas**, verificado con un
    conteo tabla por tabla: `CASCADE` alcanza `budgets`, `notifications`, `push_subscriptions`,
    `api_keys`, `hidden_categories` y los tres tipos de token, que no están en la lista
    explícita. El aislamiento del seam es "borrar la base entera", no "borrar 6 tablas".
14. **Un commit real en la base compartida rompe la suite.** Verificado: un test previo que
    commitea filas hace fallar
    `test_soft_delete.py::TestGlobalFilterMechanism::test_create_transaction_against_soft_deleted_account_returns_404`,
    que afirma `SELECT COUNT(*) FROM transactions == 0` (`test_soft_delete.py:85`).
    `test_seed.py` se recolecta justo antes de `test_soft_delete.py` (orden alfabético), así que
    la lectura ingenua de Q8 ("engine propio sobre la base de la suite") rompería la suite en
    el modo nuevo. De ahí el esquema dedicado de B8. Es la única aserción de conteo global de
    toda la suite (`grep -rn "COUNT(\*)" tests/` → una).
15. **`alembic check` no sirve contra la base de la suite.** Reproducido: con la base creada por
    `create_all` (sin `alembic_version`) responde `FAILED: Target database is not up to date`.
    El aislamiento de B9 no es higiene, es requisito.
16. **`alembic check` sí funciona en SQLite**: contra un archivo temporal pasa las 12
    migraciones y responde `No new upgrade operations detected`. El test de drift puede correr en
    los dos motores sin markers extra. Costo medido: 1,5 s en Postgres, 1,2 s en SQLite.
17. **El cuerpo del test de `updated_at` funciona en SQLite** (validado: pasa); lo que revienta
    en SQLite es el `TRUNCATE` del teardown (`sqlite3.OperationalError: near "TRUNCATE": syntax
    error`). Ese detalle es el que abrió el marcador de B6, ya resuelto (ver B6).
18. **Conteos esperados al cerrar**: Postgres 351 pasan / 0 skip; SQLite 341 pasan / 10 skip
    (350 actuales + 1 test de drift, con `TestUpdatedAt` moviéndose de "pasa" a "skip" en
    SQLite). El marker `postgres` marca hoy 9 tests (6 en concurrencia + 3 de overflow de
    saldo); con B6 y B7 el marker `concurrencia` marca **10** (los 9 de hoy más
    `TestUpdatedAt`).

## Implementation Decisions

### Infra — dependencias

**I1. `testcontainers-python` levanta el Postgres de la sesión (Q1).**

Se agrega `testcontainers` a la sección de tests de `requirements.txt` (la que abre
`# --- Tests (Fase 7, §4.2) ---`, después de `freezegun`), pineado a la versión contra la que
se validó esta spec. La distribución en PyPI se llama `testcontainers`; el proyecto es
"testcontainers-python". El import va por **`testcontainers.community.postgres`**, no por
`testcontainers.postgres` (deprecado en 4.15). La imagen es `postgres:16-alpine`, la misma que
`docker-compose.yml`.

El fixture de sesión pasa credenciales explícitas en vez de aceptar las del entorno, y solo
toca el contenedor cuando no hay `TEST_DATABASE_URL` (si la hay, no se levanta nada):

```python
IMAGEN_TEST = "postgres:16-alpine"

@pytest.fixture(scope="session")
def postgres_ephemeral():
    """Postgres 16 desechable de la sesión (Q1). `None` cuando hay `TEST_DATABASE_URL`:
    en ese modo no se levanta ningún contenedor."""
    if TEST_DATABASE_URL:
        yield None
        return
    try:
        contenedor = PostgresContainer(
            IMAGEN_TEST, username="oikos", password="oikos_test", dbname="oikos_test"
        ).start()
    except (DockerException, ContainerStartException) as exc:
        pytest.exit(_MENSAJE_SIN_DOCKER.format(detalle=str(exc).splitlines()[0]), returncode=2)
    try:
        _exigir_nombre_de_test(contenedor.get_connection_url())
        yield contenedor
    finally:
        contenedor.stop()
```

El `try` cubre **solo** el arranque: un fallo de un test no entra en ese `except`, y el
`pytest.exit` no puede tragarse un error de teardown.

### Backend — resolución del motor de la suite (`conftest.py`)

**B2. Una sola variable, dos precedencias, y la guarda solo para Postgres (Q7).**

`TEST_DATABASE_URL` se reusa tal cual (cero conceptos nuevos). Regla final: **si está
definida, se usa tal cual; si no, testcontainers.** La guarda de nombre de base se reduce a
un helper que se aplica a la **URL resuelta** en los dos ramos Postgres (el del operador y el
del contenedor) y **no** a las URLs SQLite — una `sqlite://` en memoria no tiene nombre de
base que proteger, y hoy `TEST_DATABASE_URL=sqlite://` ni siquiera llega a collection
(hallazgo 7). La comprobación para el ramo del operador sigue siendo a nivel de módulo
(antes de abrir cualquier conexión); la del contenedor, dentro del fixture.

**B1. Sin Docker: `pytest.exit(..., returncode=2)` con las tres salidas, nunca fallback
automático (Q1 + Q2).**

Decisión propia sobre la *forma* (el "qué" ya estaba decidido): la suite **aborta**. Se
descartaron las dos alternativas con nombre:

- *Fallback automático a SQLite*: prohibido por Q2 — un verde en el motor que no es el de
  producción es exactamente el bug que esta fase viene a matar.
- *`pytest.skip` de la suite entera*: deja exit code 0 con 350 saltados. Un gate que pasa sin
  correr nada es peor que uno que falla.
- *`pytest.UsageError` en `pytest_sessionstart`*: el mensaje es más limpio, pero obliga a
  arrancar el contenedor en `sessionstart`, que también dispara con `pytest --collect-only`
  (pagar ~9 s para listar tests no).

`pytest.exit` desde un fixture de sesión corta la corrida en el primer test que necesita la
base, imprime el mensaje y sale con código 2. El detalle cosmético —el prefijo `!` de pytest y
una línea "N passed" de una corrida parcial— no cambia lo que importa: **el código de salida
es distinto de cero**, así que cualquier gate falla igual. Verificado con un experimento
aislado de tres tests: 1 corrió, la sesión cortó, `EXIT=2`.

**B3. El fixture `engine` resuelve los tres casos sin duplicar construcción.**

Hoy tiene dos ramas (con `TEST_DATABASE_URL` → `create_engine` pelado; sin ella → `sqlite://` +
`StaticPool`). Con la variable reutilizada como opt-in de SQLite, la rama de la variable no
puedearse a la de Postgres: `create_engine("sqlite://")` sin `StaticPool` cambia la
configuración de la suite. El fixture queda con un caso explícito por dialecto, y **la rama
SQLite conserva exactamente lo de hoy** (`sqlite://` + `StaticPool` +
`check_same_thread=False`, `create_all` y **sin** `drop_all`): una base en memoria está vacía
igual, y no hacer `drop_all` evita que un `sqlite:///ruta/a/algo.db` tocado a mano pierda sus
tablas. Se agrega `test_db_url` (fixture de sesión) como fuente única de la URL resuelta, que
consumen `engine`, `test_seed.py` y el test de drift.

**B4. El marker `postgres` se llama `concurrencia` y se autoskippea por dialecto (Q6).**

`backend/pyproject.toml` registra el marker nuevo y saca el viejo. El skip en
`pytest_collection_modifyitems` cambia la condición de "no hay `TEST_DATABASE_URL`" a "el
motor activo es SQLite" — que es lo que significa el marker — y el motivo pasa a "requiere
sesiones reales por request; el opt-in SQLite no las soporta". Es el mismo hook, con la
condición y el texto cambiados.

### Backend — el seam de sesiones reales

**B5. `pg_*` → `real_*`, más dos fixtures que el seam ya necesitaba (Q6).**

Se renombran los cuatro fixtures, el archivo `test_concurrency_pg.py` pasa a
`test_concurrency.py` (con `git mv`, para no perder el historial), y su module docstring y el
de `test_money_limits.py` se actualizan.

Los dos tests de timezone dejan de leer `os.environ["TEST_DATABASE_URL"]` y de duplicar
`create_engine` + `engine_kwargs_for_url` (hoy 4 `create_engine` en el archivo). Pero el
fixture `engine` de la suite **no les sirve** para el `ALTER DATABASE`, por dos razones que
importan: `ALTER DATABASE` no puede correr dentro de una transacción (hace falta
`AUTOCOMMIT`), y para el `SHOW timezone` de control hace falta una conexión **nueva de verdad**
—una del pool de la suite se creó antes del `ALTER` y su `timezone` de sesión ya estaba
fijado, así que la comprobación pasaría sin probar nada—. Por eso se agrega un fixture
**`admin_engine`** (función) con `NullPool` + `AUTOCOMMIT` + los `kwargs` de producción: con
`NullPool` cada `connect()` es una sesión nueva de verdad, así que "conexión nueva" queda
garantizado por construcción en vez de por casualidad, y además el pool queda vacío al
terminar (no se filtra `AUTOCOMMIT` a la suite). Los dos tests pasan a usar `test_db_url` para
el nombre de la base y `admin_engine` para hablar con ella.

El rename de fixtures también destapa que el seam repite `sessionmaker(bind=engine, …)` en
tres lugares. Se agrega:

- `real_session_factory` (sesión): el `sessionmaker` bound al `engine` de la suite. Lo usan
  `real_client`, `real_register_and_login` y el test de B6.
- `real_session` (función): una sesión de esa factory, cerrada en el teardown. Para tests que
  necesitan leer o escribir **fuera** de HTTP.
- `admin_engine` (función): engine de administración para lo que la transacción de la suite no
  puede hacer (`ALTER DATABASE` con `AUTOCOMMIT`, y conexión nueva garantizada por `NullPool`).
  Solo lo usan los dos tests de timezone.

Esto no cuesta nada y evita tres copias: sin `real_session` el test de B6 tiene que armar
el `sessionmaker` inline (como hice en el experimento), y `real_client` y
`real_register_and_login` ya lo copiaban.

**B6. `TestUpdatedAt` pasa al seam real y se marca `concurrencia` (Q4).**

Q4 decidió el *qué*: se arregla el test, no producción. `updated_at` se queda con `now()`
(producción abre una transacción por request, así que el comportamiento real es correcto) y
el `time.sleep(1.1)` se queda. Lo que la decisión ataba es el *dónde*: `now()` en Postgres es
`transaction_timestamp()`, no avanza dentro de una transacción, y el `PUT` tiene que salir de
la transacción externa de `db_session`.

Diagnóstico verificado: con `TEST_DATABASE_URL`, el `INSERT` y el `PUT` del test salen con el
mismo `updated_at` **al microsegundo**
(`datetime(2026, 9, 28, 1, 21, 1, 952346, tzinfo=utc)` en ambos), porque comparten la
transacción externa que abre `db_session`.

El mecanismo, validado contra Postgres: **un solo test, sobre el seam real**. Todo lo que
necesita escribir en el mismo seam, en vez de partirlo en dos.

```python
# `concurrencia` (decidido en B6): el `PUT` tiene que salir de la transacción externa de
# `db_session`, así que este test no corre en el opt-in de SQLite — 10 skips en ese modo.
@pytest.mark.concurrencia
class TestUpdatedAt:
    def test_updated_at_changes_on_put_but_not_on_read(
        self, real_client, real_session, real_register_and_login, real_make_account, real_make_category
    ):
        user = real_register_and_login(email="updated-at@example.com")
        headers = user["headers"]
        cuenta = real_make_account(headers, name="Cuenta ts")
        categoria = real_make_category(headers, name="Categoría ts", type="expense")
        creada = real_client.post("/api/v1/transactions/", json={...}, headers=headers).json()
        presupuesto = real_client.post("/api/v1/budgets/", json={...}, headers=headers).json()

        def _updated_at(tabla: str, fila_id: int):
            # Lectura por sesión real: la de `db_session` no ve commits ajenos.
            return real_session.execute(
                sa.text(f"SELECT updated_at FROM {tabla} WHERE id = :id"), {"id": fila_id}
            ).scalar()

        recursos = {  # account / category / transaction / budget, igual que hoy
            "account": ("accounts", cuenta["id"]), ...
        }
        iniciales = {n: _updated_at(t, i) for n, (t, i) in recursos.items()}
        assert iniciales["account"] is not None
        assert _updated_at(*recursos["account"]) == iniciales["account"]   # leer no mueve updated_at

        time.sleep(1.1)

        # Los 4 PUT por `real_client` (una transacción propia cada uno).
        real_client.put(f"/api/v1/accounts/{cuenta['id']}", json={...}, headers=headers)
        ...

        finales = {n: _updated_at(t, i) for n, (t, i) in recursos.items()}
        for nombre in recursos:
            assert finales[nombre] != iniciales[nombre], f"updated_at de {nombre} no cambió tras el PUT"
```

Por qué esto y no las otras dos salidas que se descartaron:

- **Partirlo en dos tests** (uno con `db_session` que solo verifica "leer no mueve" y otro con
  el seam real para el `PUT`): rompe la garantía en dos piezas que pueden desincronizarse, y
  el primero necesita un `sleep` de 1,1 s para no hacer nada útil.
- **Un `session.begin_nested()` alrededor del `PUT`**: no sirve, un savepoint no abre una
  transacción nueva en Postgres; `transaction_timestamp()` sigue siendo el de la externa.

Dos detalles de aislamiento que el experimento dejó medidos: la sesión de lectura puede haber
empezado su transacción **antes** de los `PUT` y aun así verlos (READ COMMITTED toma un
snapshot por sentencia), y el teardown del seam real wipea las 13 tablas, así que las filas que
crea este test (incluido el presupuesto) no quedan para el resto de la sesión.

> **Resuelto con el dueño (2026-09-28): opción (A) — el test se marca `concurrencia`.** Es lo
> que dice la semántica de Q6 ("requiere sesiones reales por request"), no cuesta una línea, y
> el motor donde ese test importa es Postgres, que pasa a ser el default. La consecuencia se
> **asume**: `TestUpdatedAt` no corre en el opt-in de SQLite y ese modo queda en **341 pasan /
> 10 skip** (antes 9 skips), mientras el default queda en 351 pasan / 0 skip. El opt-in de
> SQLite existe para cubrir la rama SQLite de `engine_kwargs_for_url` (código de producción),
> no para dar paridad completa de suite.
>
> Se evaluó y se descartó **(B), teardown dialect-aware** (`TRUNCATE … CASCADE` en Postgres,
> `DELETE FROM` en SQLite) con el test sin marker, para que siguiera corriendo en los dos
> motores: el cuerpo ya funciona en SQLite (hallazgo 17) y serían ~6 líneas en `real_client`.
> En contra: el teardown del seam —que hoy es una sola sentencia, "truncá todo" con `CASCADE`—
> pasaría a depender del dialecto y, en SQLite, a exigir un orden manual de borrado por FKs
> (o apagar FKs) sobre 13 tablas que nadie va a mantener; y el marker `concurrencia` quedaría
> apoyado solo en "hilos reales", no en el motor. Se pierde a propósito la prueba de que el
> `CURRENT_TIMESTAMP` de SQLite (resolución de segundos) también mueve `updated_at`.

**B7. Los tres tests de overflow de saldo también cambian de marker (Q6).**

El roadmap nombraba solo `test_money_limits.py:206`; el cambio real es el módulo entero: el
marker, los cuatro fixtures usados en las firmas y los dos docstrings que nombran el seam
(`:6-7`) y el archivo compartido (`:211-212`).

**B8. `test_seed.py`: engine propio por dialecto, y en Postgres un esquema propio (Q8).**

El principio de Q8 es correcto y se mantiene: lo que el test necesita es una *capacidad* (FKs
aplicadas), no un motor — Postgres la da gratis, SQLite hay que pedirla — y usar el `engine` de
la suite lo volvería **vacuo en modo SQLite**. El `PRAGMA foreign_keys=ON` queda solo en el
`connect` de SQLite, en el mismo lugar del código de hoy.

Lo que el roadmap no anticipó es el aislamiento: en modo Postgres, un engine propio **sobre la
base de la suite** commitea de verdad y rompe el test de conteo global de `test_soft_delete`
(hallazgo 14, reproducido). Por eso el engine propio va a un **esquema propio** de la misma
base, con el patrón que el propio test ya usa para el `PRAGMA`:

```python
ESQUEMA_SEED = "oikos_test_seed"

# Postgres: CREATE SCHEMA + SET search_path en el evento `connect` (una sola conexión,
# después de conectar, así que no hace falta un segundo engine para crearlo).
# Teardown: DROP SCHEMA ... CASCADE sobre una conexión con el search_path por defecto.
```

Costo: un `engine` propio, una sesión de teardown y el `search_path`. Beneficio: el test
conserva la *capacidad* que vigila, no toca la base de la suite y no depende del orden de
recolección. La alternativa —una base descartable propia como la del test de drift— también
aisla, pero multiplica la maquinaria de provisión por un test que no necesita más que un
namespace.

**B9. `alembic check` como test de sesión, contra una base migrada propia (Q3).**

Archivo nuevo `backend/tests/test_migrations.py`. Responsabilidades separadas como decidió
Q3: `create_all` para la suite (rápido) y esta guardia para el drift.

- **Aislamiento (obligatorio, hallazgo 15):** la base de la suite queda con `create_all` y sin
  `alembic_version`; contra esa base `alembic check` responde `FAILED: Target database is not
  up to date`, que no es drift sino un falso positivo. La guardia crea su propia base
  (`DROP DATABASE IF EXISTS` + `CREATE DATABASE` con `AUTOCOMMIT` sobre el motor de la suite,
  nombre derivado del suyo con un sufijo que conserva "test") y la dropea al terminar. En modo
  SQLite usa un archivo temporal, que es lo que hace que el test sirva en los dos motores
  (hallazgo 16).
- **Por qué subprocess y no la API de Alembic:** `alembic/env.py:23` pisa
  `sqlalchemy.url` con `app.core.database.SQLALCHEMY_DATABASE_URL`, que se construye **al
  import** desde `DATABASE_URL`. Como el conftest ya importó ese módulo, una llamada
  programática apuntaría a la base equivocada y no habría forma de sobrescribirla sin tocar
  `env.py`. Un subprocess con `DATABASE_URL` en el `env` reproduce exactamente el camino del
  `CMD` de Docker —`alembic upgrade head` y nada más— y verificado: `python -m alembic
  check` desde `backend/` responde `No new upgrade operations detected` y sale con 0.
- **El resultado se asserta en el test, no en el fixture:** un fixture que falla se reporta
  como *error* de setup y deja el test en verde; devolver el `CompletedProcess` y assertar en el
  cuerpo hace que un drift se lea como un test fallido, con la salida de alembic en el mensaje y
  el puntero a `/alembic-migration`.
- **Una sola corrida por sesión** (1,5 s en Postgres, 1,2 s en SQLite, contra los ~150 s de suite).
- **Si el rol no puede crear bases** (Postgres con privilegios reducidos, caso que el
  contenedor de testcontainers y la receta de `AGENTS.md` no tienen), el test se salta con un
  motivo que nombra lo que falta, en vez de romper la corrida entera. La alternativa —esquemas
  dentro de la base de la suite, vía `?options=-c search_path=…` en la URL— se anota como
  trabajo futuro si algún día aparece ese rol.

### Docs

**D1. Lo que hay que actualizar (Q10) + lo que la fase deja atrás.**

- `AGENTS.md` §Tests: deja de decir "suite completa (SQLite en memoria, sin Docker/Postgres)",
  describe el default con testcontainers y los dos modos. La receta `docker run` sobrevive
  **reducida a una línea** y reetiquetada como override (es el camino para correr la suite sin
  que testcontainers tenga el control, que es justo cuando el problema *es* testcontainers).
- `.agents/skills/run-tests/SKILL.md`: el paso 1 de backend (líneas 14-17) deja de ser
  "solo `./venv/bin/pytest`" y nombra el requisito de Docker y el override de SQLite.
- `docs/TODO.md`: marcar `[x]` con fecha el ítem "Insumo de la Fase 32 (inventario de T10)"
  (`:424-429`, dentro de "Deuda nueva consciente de la Fase 31"), y **agregar el alta de
  `pytest-xdist`** con su bloqueo. Va en §🔵 "Solo si el proyecto crece" (`:611`), al lado de
  CI/CD y los tests de frontend, que es donde ya vive "el proyecto creció": el bloqueo es
  `ALTER DATABASE … SET timezone` en los dos tests de timezone, que es **a nivel de base** y no
  se aísla ni con esquemas por worker, más el `TRUNCATE` de tablas globales del teardown del
  seam y una sola base compartida — paralelizar obligaría a un contenedor o un
  `CREATE DATABASE` por worker, y ~2,5 min es tolerable para un gate manual.
- Las **dos referencias al marker y al nombre del archivo** que el rename deja viejas y que
  ninguna otra decisión cubre (hallazgo 8): `test_transactions.py:182` y
  `test_database.py:2,5`, ambos docstrings que hoy nombran `test_concurrency_pg.py` y el marker
  `postgres`. Describen el seam *actual*, no historia: si no se tocan, el próximo que grepee
  `test_concurrency` no encuentra nada. Las de `test_money_limits.py:6-7` y `:211-212` ya están
  en B7, y `docs/TODO.md:79` / `docs/CHANGELOG.md:20` se dejan como registro de la Fase 31.
- Al cerrar: `docs/CHANGELOG.md` (3-5 líneas) y `docs/ROADMAP.md` §Fase 32 → "completada".

## Testing Decisions

**Qué es un buen test acá.** Esta fase no cambia comportamiento de producto: sus tests son
guardas sobre la guarda. Se verifica conducta observable —el código de salida de la corrida, el
motivo del skip, la salida de `alembic check`— y no el texto de la configuración. Concreto:
nada de assertar sobre el contenido de `pyproject.toml` o sobre variables de `os.environ` leídas
a dedo (que es exactamente lo que este cambio elimina).

**Qué se prueba y cómo**

| Decisión | Verificación |
|---|---|
| I1 (testcontainers) | El arranque/parada lo ejercita la suite completa en el default de T1 (351 pasan en Postgres sin `TEST_DATABASE_URL`). La API se validó contra la versión pineada en un venv aparte: import `testcontainers.community.postgres`, URL `postgresql+psycopg2://…`, arranque 8,6 s. El camino de fallo (sin Docker) es el de B1. |
| B1 (sin Docker) | Comportamiento verificado en un experimento aislado: 3 tests, el que pide la base corta la corrida, mensaje con las tres salidas, `EXIT=2`. En la fase: no hay test automatizado del propio `pytest.exit` (sería un meta-test); se verifica a mano una vez, con Docker parado. |
| B2 (guarda solo Postgres) | Verificado en el experimento: `TEST_DATABASE_URL=sqlite://` hoy aborta al importar; con la guarda nueva, la colección sigue. Smoke: `TEST_DATABASE_URL=sqlite:// pytest --collect-only` y `TEST_DATABASE_URL=postgresql://…/oikos_test pytest --collect-only` (la `…/oikos` a secas seguiría abortando, que es justo la guarda). |
| B3 (engine) | La suite completa en los dos motores (T1). Un engine mal armado se ve como `no such table` o `no such column` en las 350. |
| B4 (marker) | Conteo de skips en SQLite: 9 hoy → **10** con `concurrencia` (los 9 de hoy más `TestUpdatedAt`, que B6 mueve al seam real). El motivo del skip se lee en `-rs`. |
| B5 (rename) | La suite completa. La guarda extra es `pytest -m concurrencia` selecciona 10: si un marker quedara sin registrar, `pyproject.toml` no lo detectaría (pytest solo avisa) y `ruff` tampoco. |
| B6 (Q4) | El test **falla antes del cambio** en Postgres (verificado: `updated_at de account no cambió`) y pasa después. Es la única regresión que la fase arregla. Con el marker de B6 se cuenta entre los 10 skip del opt-in de SQLite, y `-m concurrencia` lo incluye en el default. |
| B7 (marker en `test_money_limits`) | La suite en los dos motores: los 3 de overflow corren en el default de Postgres y se saltan en el opt-in SQLite, y el conteo de `-m concurrencia` queda en 10 sin que un marker quede sin registrar (pytest solo avisa, no falla). |
| B8 (test_seed) | El test pasa en los dos motores; en Postgres, `test_seed.py` seguido de `test_soft_delete.py` en la **misma sesión** (el orden de recolección real) es la prueba de que no filtra. |
| D1 (docs) | Sin test: es documentación. La parte mecánica sí es checkable — al cerrar, `grep -rn "test_concurrency_pg\|mark.postgres" backend/ AGENTS.md .agents/` no debe devolver nada salvo los archivos de historia. |
| B9 (drift) | Un test de sesión que falla ante drift. Verificado que hoy pasa (no hay drift) y que **falla** si se lo apunta a la base de la suite (el falso "Target database is not up to date"), o sea que el aislamiento es parte de lo que el test exercise. La prueba de que detecta drift de verdad: correrlo una vez contra una `models.py` editada a mano, ver el rojo, y revertir — opcional, en el cierre. |

**Arte previo.** `test_database.py` es el precedente de un archivo que aísla una capacidad de
`engine_kwargs_for_url` como función pura, sin marker y sin conexión. `test_concurrency_pg.py`
(es decir, `test_concurrency.py`) es el precedente del marker de aislamiento y del
`reconcile.discrepancy` como invariante. `test_seed.py` es el precedente del engine propio con
`PRAGMA` en el evento `connect` — el esquema dedicado de B8 reutiliza exactamente ese patrón.

**T1. Cierre: la suite completa en los dos motores (supuestos 2 y 6).**

```sh
cd backend && ./venv/bin/pytest            # default: testcontainers → Postgres
cd backend && TEST_DATABASE_URL=sqlite:// ./venv/bin/pytest   # opt-in SQLite
cd backend && ./venv/bin/ruff check . && ./venv/bin/ruff format --check .
```

Criterio: 351 pasan en Postgres (0 skip) y 341 pasan + 10 skip en SQLite (los 10 = 9 de hoy +
`TestUpdatedAt`, que B6 marcó `concurrencia`), más el test de drift verde en los dos. El modo SQLite es el que nadie va a ejercitar si no se corre a mano en cada
cierre: por eso es parte del cierre y no un extra.

## Orden de ejecución

```
1. [infra] requirements.txt (testcontainers, sección de tests) — Decisión I1 (Q1).
   Depende de: —
2. [backend] conftest.py: resolución de la URL + postgres_ephemeral + guarda + engine +
   test_db_url + marker `concurrencia` — Decisiones I1, B1, B2, B3, B4 (Q1, Q2, Q6, Q7).
   Depende de: 1
3. [backend] conftest.py: renombre del seam `pg_*` → `real_*` + real_session_factory +
   real_session + admin_engine — Decisión B5 (Q6).
   Depende de: 2   (mismo archivo)
4. [backend] tests/test_concurrency_pg.py → test_concurrency.py (git mv + marker + fixtures
   + fin de la lectura de os.environ["TEST_DATABASE_URL"] en los dos tests de timezone) —
   Decisión B5 (Q6).
   Depende de: 3
5. [backend] [P] tests/test_money_limits.py (marker, fixtures en las 3 firmas, docstrings) —
   Decisión B7 (Q6).
   Depende de: 3
6. [backend] [P] tests/test_seed.py (engine propio por dialecto + esquema Postgres) —
   Decisión B8 (Q8).
   Depende de: 2
7. [backend] [P] tests/test_migrations.py (test de drift de la sesión) — Decisión B9 (Q3).
   Depende de: 2
8. [backend] tests/test_soft_delete.py (TestUpdatedAt al seam real, con marker
   `@pytest.mark.concurrencia`) — Decisión B6 (Q4).
   Depende de: 3
9. [docs] [P] docstrings con referencias al marker/al archivo (test_transactions.py,
   test_database.py) — Decisión D1 (Q10).
   Depende de: 4
10. [verif] Suite completa en Postgres (default) y en SQLite (opt-in) + ruff — Decisión T1.
    Depende de: 4, 5, 6, 7, 8, 9
11. [docs] AGENTS.md §Tests + .agents/skills/run-tests/SKILL.md + docs/TODO.md (marcar el
    ítem de Q4, alta de pytest-xdist) — Decisión D1 (Q10).
    Depende de: 10
12. [docs] docs/CHANGELOG.md + docs/ROADMAP.md §Fase 32 → completada — Decisión D1.
    Depende de: 10
```

## Resumen de archivos tocados

| Archivo | Qué |
|---|---|
| `backend/requirements.txt` | `testcontainers` pineado en la sección de tests (I1) |
| `backend/tests/conftest.py` | testcontainers + precedencia + guarda + `engine`/`test_db_url` + marker `concurrencia` + seam renombrado + `real_session*` + `admin_engine` (B1-B5) |
| `backend/pyproject.toml` | marker `concurrencia` registrado, `postgres` fuera (B4) — el registro no cambia por B6: es el mismo marker, con un test más |
| `backend/tests/test_concurrency.py` | (antes `test_concurrency_pg.py`) renombre, marker, fixtures, sin `os.environ` (B5) |
| `backend/tests/test_money_limits.py` | marker, fixtures, docstrings (B7) |
| `backend/tests/test_soft_delete.py` | `TestUpdatedAt` sobre el seam real, con marker `concurrencia` (B6) |
| `backend/tests/test_seed.py` | engine por dialecto + esquema Postgres (B8) |
| `backend/tests/test_migrations.py` | **nuevo**: `alembic check` como test de sesión (B9) |
| `backend/tests/test_transactions.py` | docstring: nombre del archivo y marker (D1) |
| `backend/tests/test_database.py` | docstring: marker y nombre del archivo (D1) |
| `AGENTS.md` | §Tests reescrito (D1) |
| `.agents/skills/run-tests/SKILL.md` | paso 1 de backend: requisito de Docker y los dos modos (D1) |
| `docs/TODO.md` | ítem de Q4 marcado, alta de `pytest-xdist` (D1) |
| `docs/ROADMAP.md` | §Fase 32 → completada, al cerrar (D1) |
| `docs/CHANGELOG.md` | entrada de la fase, al cerrar (D1) |
| `docs/specs/fase_32_spec.md` | este archivo |

**No se tocan** (y por qué): `backend/docs/API_REFERENCE.md` y
`frontend/docs/API_CONTRACT.md` (supuesto 3 — cero cambios de contrato), `app/**` (ninguna
decisión cambia producción), `alembic/**` (B9 no necesita tocar `env.py`; usa el camino real
por subprocess), `README.md` / `backend/README.md` / `backend/docs/DEPLOYMENT.md` /
`backend/docs/ARCHITECTURE.md` (hablan del fallback SQLite de la **app**, no de los tests),
`scripts/git-hooks/pre-commit` (no corre pytest), `docs/specs/fase_07_spec.md` y las specs de
Fases 7/20/29 (son historia), y las entradas previas de `docs/CHANGELOG.md` y `docs/TODO.md:79`
(la resolución de QA-003 nombra el marker `postgres` y el archivo viejo: es el registro de lo
que pasó, no de lo que hay — mismo criterio que las specs).

## Out of Scope

- **`pytest-xdist` / paralelismo (Q9).** Va a `docs/TODO.md` §🔵 con su bloqueo: `ALTER
  DATABASE … SET timezone` a nivel de base, `TRUNCATE` de tablas globales en el teardown del
  seam y una sola base compartida. Paralelizar obligaría a un contenedor o un `CREATE DATABASE`
  por worker.
- **Borrar SQLite** del conftest si el opt-in nunca llega a usarse (Q2). Es un commit chico
  posterior, y mientras tanto cubre la rama SQLite de `engine_kwargs_for_url`, que es código de
  producción.
- **Arreglar bugs que el motor nuevo destape (Q5).** Se anotan en `docs/TODO.md` con
  severidad, no se arreglan acá — salvo que descuadre un saldo o rompa el login.
- **Esquemas por worker o `search_path` global para el drift** (alternativa de B9) y cualquier
  provisionado de infraestructura de CI.
- **Tests de frontend y CI/CD** — siguen fuera de scope.
- **Tocar `alembic/env.py`** para que la URL sea programable: el subprocess de B9 lo evita.
  Queda anotado como deuda menor junto con el hecho de que `env.py:66-70` no aplica el
  `options: -c timezone=UTC` que sí usa la app (hoy inocuo: `now()` en un default se guarda
  como función, no se evalúa al migrar).
- **Tocar `.env` / `.env.example`.** Ninguna variable nueva: `TEST_DATABASE_URL` ya existe.
  Los agentes no editan `.env` (hooks), y no hace falta.

## Decisiones resueltas con el usuario (2026-09-27 / 2026-09-28)

- **Q1-Q10** las respondió el dueño en el `/grilling` del 2026-09-27, registrado en
  `docs/ROADMAP.md` §Fase 32. Esta spec no las reabre: las implementa.
- Los marcadores `[NEEDS CLARIFICATION]` que se resuelvan después van aquí, reemplazando el
  marcador en su lugar.

1. **B6 — ¿el test de `updated_at` se marca `concurrencia` y con eso deja de correr en el opt-in
   de SQLite, o se le hace un teardown dialect-aware al seam para que siga en los dos motores?**
   (2026-09-28) **Se marca `concurrencia`** — la recomendada. Se acepta explícitamente que ese
   test no corra en el opt-in de SQLite: ese modo queda en 341 pasan / 10 skip (antes 9 skips) y
   se pierde la prueba de que el `CURRENT_TIMESTAMP` de SQLite también mueva `updated_at`. Se
   descarta (B) —`TRUNCATE … CASCADE` en Postgres, `DELETE FROM` en SQLite— porque el teardown
   del seam no debe volverse dependiente del dialecto ni del orden de borrado por FKs, y porque
   el opt-in de SQLite existe para cubrir la rama SQLite de `engine_kwargs_for_url` (código de
   producción), no para dar paridad completa de suite. El marcador quedó reemplazado por la
   decisión en B6; el resto de la spec (conteos, marker, orden de ejecución) ya la asume.

## Further Notes

- **El argumento de esta fase es fricción, no velocidad.** Postgres es ~10 % más lento que
  SQLite y testcontainers agrega ~9 s de arranque. El valor es que `cd backend && pytest` sea
  el gate correcto por default: correr la suite en el motor de producción no puede depender de
  acordarse de un paso extra, porque la primera vez que se olvida, la suite "verde" es del
  motor que no importa.
- **El modo SQLite es un modo, no un fallback.** Reusa `TEST_DATABASE_URL` a propósito: si
  someday hiciera falta un tercer motor, el mismo hooking ya lo soporta.
- **Lo que esta fase deja más caro de verificar** es el aislamiento. Hoy casi toda la suite
  se aísla con un rollback de una transacción externa y no depende del orden de recolección;
  con el default en Postgres eso sigue igual, pero el seam de sesiones reales y `test_seed`
  commit de verdad, y sus teardowns son la única red. El test de conteo global de
  `test_soft_delete.py:85` es el detector de que esa red se rompió: es el primer test que
  falla si algo filtra.
- **Verificado de punta a punta antes de escribir esto**: el fallo de Q4 reproducido y
  diagnosticado, el mecanismo de B6 validado, el TRUNCATE CASCADE del teardown medido sobre las
  13 tablas, la ruptura por commit compartido reproducida, `alembic check` verificado en los
  dos motores y su falso positivo contra la base de la suite reproducido, el esquema
  `postgresql+psycopg2://` de testcontainers compatible con la suite, y el arranque sin Docker
  con su código de salida. Todo lo que la spec afirma como *hoy* —incluido lo que está roto—
  sale de esa corrida; lo que queda por delante es escribir código, no descubrir hechos.
- **Precedente de `pytest.exit` en el repo:** es nuevo. La alternativa descartada
  (`UsageError` en `pytest_sessionstart`) da un mensaje más limpio, pero obliga a arrancar el
  contenedor también con `pytest --collect-only`; si algún día recolectar tests sin Postgres
  deja de importar, esa es la variante a reconsiderar.
