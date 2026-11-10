#!/usr/bin/env bash
# Backs up the calendar from the running Agenda container, on the home server.
#
# It asks SQLite itself for a copy (its "backup API"), which is safe while the
# app is running: copying agenda.db with cp mid-write could give a broken file.
# The copy goes to /data/backups/agenda-YYYY-MM-DD.db inside the volume, only
# the newest KEEP copies are kept (14 by default), and they are then copied to
# the folder you give, so a copy also lives outside Docker (ideally on another
# disk, a NAS or a synced folder).
#
# Usage:
#   scripts/backup.sh /path/to/backup/folder [KEEP]
#
# Every day at 3:15 with cron: run `crontab -e` on the server and add this line
# (with your real paths; the log shows what the last runs said):
#   15 3 * * * /home/me/agenda/scripts/backup.sh /mnt/backups/agenda >> /home/me/agenda-backup.log 2>&1
#
# Restoring one is in docs/safety.md.
set -euo pipefail

DEST="${1:-}"
KEEP="${2:-14}"
# The container's name, from container_name in docker-compose.yml.
CONTAINER="${AGENDA_CONTAINER:-agenda}"

if [ -z "$DEST" ]; then
  echo "Usage: $0 /path/to/backup/folder [KEEP]" >&2
  exit 1
fi
case "$KEEP" in
  '' | *[!0-9]* | 0) echo "KEEP must be a number of 1 or more (got '$KEEP')." >&2; exit 1 ;;
esac
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
  echo "The container '$CONTAINER' isn't running: start the stack in Portainer first." >&2
  exit 1
fi

# The Python runs inside the container, where Python and the database already
# are, so the server needs nothing but Docker. It writes to a temporary name
# first, so a backup cut short never replaces a good one.
docker exec -i -e KEEP="$KEEP" "$CONTAINER" python - <<'PY'
import datetime
import os
import sqlite3

folder = "/data/backups"
os.makedirs(folder, exist_ok=True)
name = f"agenda-{datetime.date.today().isoformat()}.db"
final = os.path.join(folder, name)
partial = final + ".part"

source = sqlite3.connect("/data/agenda.db")
target = sqlite3.connect(partial)
with target:
    source.backup(target)
target.close()
source.close()

# Check the copy opens and reads before trusting it.
check = sqlite3.connect(partial)
ok = check.execute("PRAGMA integrity_check").fetchone()[0]
check.close()
if ok != "ok":
    os.remove(partial)
    raise SystemExit(f"The backup failed its check ({ok}); the old backups are untouched.")
os.replace(partial, final)

# The names sort by date, so the oldest come first.
backups = sorted(f for f in os.listdir(folder) if f.startswith("agenda-") and f.endswith(".db"))
keep = int(os.environ["KEEP"])
for old in backups[:-keep]:
    os.remove(os.path.join(folder, old))
print(f"Backed up to {final} ({len(backups[-keep:])} kept in the volume).")
PY

# Copy them out of the volume, then keep the same number in the folder.
mkdir -p "$DEST"
docker cp "$CONTAINER:/data/backups/." "$DEST/"
rm -f "$DEST"/*.part
# Lists all but the newest KEEP (awk, because `head -n -N` isn't on every system).
ls -1 "$DEST"/agenda-*.db | sort | awk -v keep="$KEEP" '{ f[NR] = $0 } END { for (i = 1; i <= NR - keep; i++) print f[i] }' \
  | while read -r old; do rm -f "$old"; done
echo "$(date '+%Y-%m-%d %H:%M') copied to $DEST: $(ls -1 "$DEST"/agenda-*.db | wc -l | tr -d ' ') backups."
