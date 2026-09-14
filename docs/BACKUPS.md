# Backups de PostgreSQL

Resuelve el bloqueante que estaba en `docs/TODO.md` ("script listo, sin programar"): en vez
de un cron de host a hora fija (no sirve si la máquina no está prendida 24/7 — es un
portátil, no un servidor dedicado), el backup se dispara automáticamente **en cada
`docker compose up`**, vía un servicio dedicado de Docker Compose. Como ya corrés ese
comando cada vez que usás la app, nunca quedás a más de una sesión de trabajo sin backup.

## Qué hace (`scripts/backup/entrypoint.sh`, servicio `backup` en `docker-compose.yml`)

1. Al levantar `docker compose up`, el servicio `backup` espera a que `postgres` esté
   healthy y corre.
2. Revisa el backup local más reciente en `./backups/`. Si tiene menos de
   `BACKUP_MIN_INTERVAL_HOURS` (default 20h), no hace nada y termina — así reiniciar varias
   veces el mismo día no genera dumps redundantes.
3. Si hace falta, corre `pg_dump` contra `postgres` (por red interna de compose, no
   `docker exec`), comprime con gzip, y lo guarda en `./backups/oikos_<timestamp>.sql.gz`.
4. Borra backups locales de más de `BACKUP_RETENTION_DAYS_LOCAL` días (default 7).
5. Si existe `./rclone.conf` con el remoto configurado, sube el backup **cifrado** a Google
   Drive (cuenta de Oikos) y borra los remotos de más de `BACKUP_RETENTION_DAYS_REMOTE` días
   (default 30). Si no está configurado todavía, imprime una advertencia y sigue —
   el backup local igual se genera.

Todas las variables (`BACKUP_REMOTE`, `BACKUP_MIN_INTERVAL_HOURS`,
`BACKUP_RETENTION_DAYS_LOCAL`, `BACKUP_RETENTION_DAYS_REMOTE`, `RCLONE_CONFIG_PATH`) están
documentadas en `.env.example` con sus defaults.

## Setup único de rclone + Google Drive (cuenta de Oikos) + cifrado

Esto **hay que hacerlo a mano, una sola vez**, porque necesita loguearte por navegador con
`oikos.notificaciones.non.eply@gmail.com` — no es algo que se pueda automatizar desde el
código. Corré esto en tu portátil (no dentro de un contenedor), con un navegador disponible.

1. **Instalar rclone en el host** (no en Docker):
   ```sh
   curl https://rclone.org/install.sh | sudo bash
   ```

2. **Crear el remoto de Google Drive**:
   ```sh
   rclone config
   ```
   - `n` (new remote) → nombre exacto: `oikos-gdrive`
   - Tipo: `drive` (Google Drive)
   - `client_id` / `client_secret`: dejar en blanco (usa las credenciales genéricas de rclone)
   - `scope`: `1` (acceso completo a Drive)
   - `root_folder_id`: en blanco
   - `service_account_file`: en blanco
   - "Edit advanced config?": `n`
   - "Use auto config?": `y` — abre el navegador. **Iniciá sesión con la cuenta de Oikos**
     (`oikos.notificaciones.non.eply@gmail.com`), no tu cuenta personal, y aceptá el permiso.
   - "Configure this as a Shared Drive?": `n`
   - Confirmar y guardar.

3. **Crear el remoto de cifrado, encadenado sobre el anterior**:
   - `n` (new remote) de nuevo → nombre exacto: `oikos-crypt`
   - Tipo: `crypt`
   - `remote`: `oikos-gdrive:oikos-backups` (esto crea/usa la carpeta `oikos-backups` dentro
     del Drive de Oikos — todo lo que se escriba a través de `oikos-crypt` queda cifrado ahí)
   - `filename_encryption`: `standard` (cifra también los nombres de archivo, no solo el
     contenido)
   - `password`: elegí una contraseña fuerte (rclone puede generarte una con `g`).
     **Guardala en un gestor de contraseñas, separada del repo.** Sin ella, los backups en
     la nube quedan permanentemente ilegibles — ni siquiera rclone puede recuperarlos.
   - `password2` (salt opcional): podés dejarlo en blanco o agregar una segunda capa.
   - Confirmar y guardar.

4. **Copiar el config al repo** (queda gitignorado, nunca se commitea):
   ```sh
   cp "$(rclone config file | tail -n1)" ./rclone.conf
   ```

5. Listo. El próximo `docker compose up -d --build` ya sube los backups a la nube
   automáticamente — no hace falta reiniciar nada más ni tocar cron.

**Si todavía no hiciste este setup**: el sistema sigue funcionando, solo que los backups
quedan únicamente locales (en `./backups/`, dentro del portátil) hasta que lo hagas — vas a
ver la advertencia en `docker compose logs backup`.

## Verificar que está funcionando

```sh
docker compose logs backup                          # ver el resultado de la última corrida
ls -la backups/                                       # backups locales
rclone ls oikos-crypt:oikos-backups --config ./rclone.conf   # backups en la nube (nombres ya descifrados)
```

## Restaurar

Desde un backup local:
```sh
./scripts/restore.sh backups/oikos_20260913_030000.sql.gz
```

Desde la nube (lo baja primero, cifrado → descifrado automáticamente por rclone):
```sh
./scripts/restore.sh --remote oikos_20260913_030000.sql.gz
```

Ambos vuelcan el `.sql.gz` directo contra el `postgres` de docker-compose — pisa los datos
actuales, así que solo usar quirúrgicamente (por ejemplo, contra un `postgres` de prueba
levantado aparte, no el de producción, salvo que realmente quieras revertir todo).

## Importante: probar la restauración de vez en cuando

Un backup nunca restaurado no es un backup confiable. Cada tanto (por ejemplo, cuando
te acuerdes, o después de un cambio grande de schema), vale la pena bajar un backup y
restaurarlo contra una base de datos descartable para confirmar que el archivo sirve de
verdad. No hay nada automatizado para esto todavía — es un chequeo manual.
