#!/usr/bin/env bash
# Backup de la base de datos PostgreSQL de Oikos vía pg_dump, comprimido y con
# rotación de 7 días. Pensado para correr desde la raíz del repo (donde vive
# docker-compose.yml), vía cron del host:
#   0 3 * * * cd /ruta/al/repo && ./scripts/backup.sh >> /var/log/oikos-backup.log 2>&1
#
# Restaurar un backup: ver scripts/restore.sh.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS=7
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="oikos_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

docker compose exec -T postgres pg_dump -U oikos oikos | gzip > "${BACKUP_DIR}/${FILENAME}"

find "$BACKUP_DIR" -name "oikos_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Backup creado: ${BACKUP_DIR}/${FILENAME}"
