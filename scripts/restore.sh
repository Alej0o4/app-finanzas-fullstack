#!/usr/bin/env bash
# Restaura un backup generado por scripts/backup.sh contra el servicio postgres
# de docker-compose. Uso:
#   ./scripts/restore.sh backups/oikos_20260822_030000.sql.gz
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Uso: $0 <ruta-al-backup.sql.gz>" >&2
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "No existe el archivo: ${BACKUP_FILE}" >&2
    exit 1
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T postgres psql -U oikos oikos

echo "Restauración completada desde: ${BACKUP_FILE}"
