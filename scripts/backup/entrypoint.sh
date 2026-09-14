#!/usr/bin/env bash
# Corre dentro del servicio `backup` de docker-compose.yml, disparado automáticamente en
# cada `docker compose up` (en vez de un cron de host, que no sirve si la máquina no está
# prendida 24/7 — ver docs/BACKUPS.md). Se conecta a `postgres` por red de compose, genera
# el dump si el último backup local ya tiene más de BACKUP_MIN_INTERVAL_HOURS, lo comprime,
# rota los locales viejos, y si hay un remoto rclone configurado (cifrado vía crypt), lo sube.
#
# Sin rclone.conf configurado todavía, corre igual: backups solo locales + warning. Ver
# docs/BACKUPS.md para el setup de una sola vez de Google Drive + cifrado.
set -euo pipefail

BACKUP_DIR="/backups"
RCLONE_CONFIG="/config/rclone.conf"
REMOTE="${BACKUP_REMOTE:-oikos-crypt:oikos-backups}"
REMOTE_NAME="${REMOTE%%:*}"
MIN_INTERVAL_HOURS="${BACKUP_MIN_INTERVAL_HOURS:-20}"
RETENTION_DAYS_LOCAL="${BACKUP_RETENTION_DAYS_LOCAL:-7}"
RETENTION_DAYS_REMOTE="${BACKUP_RETENTION_DAYS_REMOTE:-30}"

mkdir -p "$BACKUP_DIR"

LATEST_FILE="$(ls -t "${BACKUP_DIR}"/oikos_*.sql.gz 2>/dev/null | head -n1 || true)"
if [ -n "$LATEST_FILE" ]; then
    LATEST_EPOCH="$(stat -c %Y "$LATEST_FILE")"
    NOW_EPOCH="$(date +%s)"
    AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))
    if [ "$AGE_HOURS" -lt "$MIN_INTERVAL_HOURS" ]; then
        echo "Último backup local tiene ${AGE_HOURS}h (mínimo configurado: ${MIN_INTERVAL_HOURS}h) — no hace falta otro todavía."
        exit 0
    fi
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="oikos_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "Generando backup: ${FILENAME}"
pg_dump -h postgres -U oikos oikos | gzip > "$FILEPATH"

find "$BACKUP_DIR" -name "oikos_*.sql.gz" -mtime "+${RETENTION_DAYS_LOCAL}" -delete

if [ -f "$RCLONE_CONFIG" ] && rclone listremotes --config "$RCLONE_CONFIG" | grep -qx "${REMOTE_NAME}:"; then
    echo "Subiendo a ${REMOTE} (cifrado por rclone crypt)..."
    rclone --config "$RCLONE_CONFIG" copy "$FILEPATH" "$REMOTE"
    rclone --config "$RCLONE_CONFIG" delete "$REMOTE" --min-age "${RETENTION_DAYS_REMOTE}d" || true
    echo "Backup subido a la nube."
else
    echo "ADVERTENCIA: remoto rclone '${REMOTE_NAME}' no configurado todavía — este backup quedó SOLO local (${FILEPATH})." >&2
    echo "Ver docs/BACKUPS.md para configurar la subida cifrada a Google Drive." >&2
fi

echo "Listo: ${FILEPATH}"
