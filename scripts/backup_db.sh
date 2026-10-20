#!/usr/bin/env sh
# Saves a compressed copy of the staging database and deletes copies older
# than KEEP_DAYS. Safe to run by hand or from cron.
#
#   sh scripts/backup_db.sh
#
# Optional settings (environment variables):
#   BACKUP_DIR   where copies go            (default: $HOME/spc-backups)
#   KEEP_DAYS    how long to keep copies    (default: 14)
#
# A copy is only kept if the dump is not empty, so a failed run never leaves a
# file that looks like a good backup. Copy the folder off the server as well:
# a backup on the same disk does not survive losing the server.
set -eu
cd "$(dirname "$0")/.."

backup_dir="${BACKUP_DIR:-$HOME/spc-backups}"
keep_days="${KEEP_DAYS:-14}"
stamp="$(date +%Y-%m-%d_%H%M)"
target="$backup_dir/spc-$stamp.dump"
partial="$target.partial"

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

trap 'rm -f "$partial"' EXIT

sh scripts/staging.sh exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$partial"

if [ ! -s "$partial" ]; then
  echo "Backup failed: the dump is empty." >&2
  exit 1
fi

mv "$partial" "$target"
echo "Backup saved: $target ($(du -h "$target" | cut -f1))"

find "$backup_dir" -name 'spc-*.dump' -mtime +"$keep_days" -delete
echo "Deleted backups older than $keep_days days."
