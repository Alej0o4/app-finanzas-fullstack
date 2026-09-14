#!/usr/bin/env bash
# Restaura un backup generado por scripts/backup.sh o por el servicio `backup` de
# docker-compose.yml, contra el servicio postgres de docker-compose. Uso:
#   ./scripts/restore.sh backups/oikos_20260822_030000.sql.gz
#
# Para restaurar uno que solo existe en la nube (no en ./backups local), bajalo primero:
#   ./scripts/restore.sh --remote oikos_20260822_030000.sql.gz
# (usa el remoto BACKUP_REMOTE de .env / docker-compose.yml, default oikos-crypt:oikos-backups)
set -euo pipefail

if [ "${1:-}" = "--remote" ]; then
    if [ $# -ne 2 ]; then
        echo "Uso: $0 --remote <nombre-del-archivo.sql.gz>" >&2
        exit 1
    fi
    REMOTE="${BACKUP_REMOTE:-oikos-crypt:oikos-backups}"
    RCLONE_CONFIG="${RCLONE_CONFIG_PATH:-./rclone.conf}"
    FILENAME="$2"
    BACKUP_FILE="./backups/${FILENAME}"

    if [ ! -f "$RCLONE_CONFIG" ]; then
        echo "No existe ${RCLONE_CONFIG} — configurá rclone primero (ver docs/BACKUPS.md)." >&2
        exit 1
    fi

    echo "Descargando ${FILENAME} desde ${REMOTE}..."
    mkdir -p ./backups
    rclone --config "$RCLONE_CONFIG" copy "${REMOTE}/${FILENAME}" ./backups/
else
    if [ $# -ne 1 ]; then
        echo "Uso: $0 <ruta-al-backup.sql.gz>" >&2
        echo "      $0 --remote <nombre-del-archivo.sql.gz>  (para bajar de la nube primero)" >&2
        exit 1
    fi
    BACKUP_FILE="$1"
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "No existe el archivo: ${BACKUP_FILE}" >&2
    exit 1
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T postgres psql -U oikos oikos

echo "Restauración completada desde: ${BACKUP_FILE}"
