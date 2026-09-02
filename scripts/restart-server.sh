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

# 1) Wait for the server unit's main process to exit.
#    We wait on the unit's own MainPID (never a broad pgrep pattern), so
#    stray or manually-started server instances can't deadlock the reboot.
#    A hard cap guarantees we always reach the restart step below even if
#    the unit state is somehow inconsistent.
stop_wait_seconds=60
waited=0
while [ "$waited" -lt "$stop_wait_seconds" ]; do
    main_pid="$(systemctl --user show -p MainPID --value playpalace 2>/dev/null || echo 0)"
    if [ "${main_pid:-0}" = "0" ] || ! kill -0 "$main_pid" 2>/dev/null; then
        break
    fi
    sleep 1
    waited=$((waited + 1))
done
if [ "$waited" -ge "$stop_wait_seconds" ]; then
    echo "$(date -Is) restart-server.sh: timed out waiting for server to exit; proceeding." \
        >> "$RESTART_LOG"
fi

cd "$APP_DIR"

# 2) Pull the latest code. A failed pull must not strand the server; log it
#    and continue so the service still restarts on the current code.
if ! git pull --ff-only; then
    echo "$(date -Is) restart-server.sh: git pull failed; restarting with current code." \
        >> "$RESTART_LOG"
fi

# 3) Restart the PlayPalace user service.
systemctl --user restart playpalace