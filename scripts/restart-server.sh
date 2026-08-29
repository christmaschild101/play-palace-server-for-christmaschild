#!/bin/sh
# PlayPalace deploy helper used by the in-game "Reboot server" admin action.
#
# Sequence (matches the requested stop -> pull -> start order):
#   1. Wait for the running server process to exit (a graceful shutdown is
#      already underway).
#   2. Pull the latest code from the configured remote.
#   3. Restart the PlayPalace user service.
#
# Runs entirely as the PlayPalace user (git + systemctl --user), so no root
# is required.
set -eu

# Resolve the repository root (this script lives in <repo>/scripts)
APP_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

# Log directory for failed pulls; matches the server's var/ runtime dir.
RESTART_LOG="$APP_DIR/var/restart.log"

# 1) Wait for the running server process to exit.
# The [ ] guards prevent pgrep from matching this script's own subshell.
while pgrep -f "[/]playpalace/.venv/bin/python.*server/main.py" >/dev/null 2>&1; do
    sleep 1
done

cd "$APP_DIR"

# 2) Pull the latest code. A failed pull must not strand the server; log it
#    and continue so the service still restarts on the current code.
if ! git pull --ff-only; then
    echo "$(date -Is) restart-server.sh: git pull failed; restarting with current code." \
        >> "$RESTART_LOG"
fi

# 3) Restart the PlayPalace user service.
systemctl --user restart playpalace