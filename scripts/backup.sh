#!/bin/sh
# Нічний бекап: дамп PostgreSQL + архів фото (media), ротація — 3 останні копії кожного.
set -eu

STAMP=$(date +%Y-%m-%d_%H%M%S)
DB_FILE="/backups/veloro_db_${STAMP}.sql.gz"
MEDIA_FILE="/backups/veloro_media_${STAMP}.tar.gz"

pg_dump -h "${POSTGRES_HOST:-db}" -p "${POSTGRES_PORT:-5432}" \
        -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$DB_FILE"
echo "$(date '+%F %T') db backup ok: $DB_FILE ($(du -h "$DB_FILE" | cut -f1))"

if [ -d /media ]; then
    tar -czf "$MEDIA_FILE" -C /media .
    echo "$(date '+%F %T') media backup ok: $MEDIA_FILE ($(du -h "$MEDIA_FILE" | cut -f1))"
fi

# залишити лише 3 найновіші копії кожного типу
ls -1t /backups/veloro_db_*.sql.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
ls -1t /backups/veloro_media_*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm -f
