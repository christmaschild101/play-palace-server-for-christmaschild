"""Scheduled actions for the PlayPalace server.

Schedules one-shot and recurring actions (reboots, broadcast announcements)
that are persisted in the database and run against a due-check loop on a
background asyncio task started by the server.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .server import Server

LOG = logging.getLogger("playpalace.scheduler")

# Supported action types
TYPE_REBOOT = "reboot"
TYPE_BROADCAST = "broadcast"

_POLL_INTERVAL_SECONDS = 5


@dataclass
class ScheduledAction:
    """A single persisted scheduled action."""

    id: int
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    repeat_interval_seconds: int = 0  # 0 = one-shot
    enabled: bool = True
    created_by: str = ""
    last_run_at: datetime | None = None

    @property
    def repeating(self) -> bool:
        """Whether this action repeats after running."""
        return self.repeat_interval_seconds > 0


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 datetime string into an aware UTC datetime."""
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_iso(dt: datetime) -> str:
    """Serialize an aware datetime to ISO-8601 with a Z suffix."""
    iso_value = dt.astimezone(timezone.utc).isoformat()
    if iso_value.endswith("+00:00"):
        iso_value = iso_value[:-6] + "Z"
    return iso_value


def _row_to_action(row: dict) -> ScheduledAction:
    """Convert a database row into a ScheduledAction."""
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except (TypeError, ValueError):
        payload = {}
    return ScheduledAction(
        id=int(row["id"]),
        action_type=row["action_type"],
        payload=payload,
        run_at=_parse_dt(row["run_at"]) or datetime.now(timezone.utc),
        repeat_interval_seconds=int(row["repeat_interval_seconds"] or 0),
        enabled=bool(row["enabled"]),
        created_by=row.get("created_by") or "",
        last_run_at=_parse_dt(row.get("last_run_at")),
    )


class ScheduledActionManager:
    """Manages persisted scheduled actions and executes them when due.

    The manager is driven by a background asyncio task (``run``) that polls
    the database every few seconds for due enabled actions, executes them, and
    reschedules recurring actions or disables one-shots.
    """

    def __init__(self, server: "Server"):
        self._server = server
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the due-check loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="playpalace-scheduler")

    async def stop(self) -> None:
        """Stop the due-check loop."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        """Poll for and dispatch due scheduled actions."""
        while True:
            try:
                await self.run_due_actions()
            except asyncio.CancelledError:
                raise
            except Exception:
                LOG.exception("Scheduled action loop failed")
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    # ------------------------------------------------------------------
    # Scheduling helpers
    # ------------------------------------------------------------------

    def create_action(
        self,
        *,
        action_type: str,
        run_at: datetime,
        repeat_interval_seconds: int = 0,
        payload: dict[str, Any] | None = None,
        created_by: str = "",
    ) -> int:
        """Persist a new scheduled action and return its id."""
        return self._server._db.save_scheduled_action(
            action_type=action_type,
            payload_json=json.dumps(payload or {}),
            run_at=_to_iso(run_at),
            repeat_interval_seconds=repeat_interval_seconds,
            created_by=created_by,
        )

    def list_actions(self) -> list[ScheduledAction]:
        """Return all persisted scheduled actions."""
        return [_row_to_action(row) for row in self._server._db.list_scheduled_actions()]

    def delete_action(self, action_id: int) -> None:
        """Delete a scheduled action."""
        self._server._db.delete_scheduled_action(action_id)

    def set_enabled(self, action_id: int, enabled: bool) -> None:
        """Enable or disable a scheduled action."""
        self._server._db.update_scheduled_action(action_id, enabled=1 if enabled else 0)

    @staticmethod
    def run_at_from_minutes_from_now(minutes: int) -> datetime:
        """Compute an absolute UTC run_at from now + ``minutes``."""
        return datetime.now(timezone.utc) + timedelta(minutes=minutes)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_due_actions(self) -> int:
        """Execute all due enabled actions.

        Returns the number of actions dispatched.
        """
        db = self._server._db
        now = datetime.now(timezone.utc)
        due = db.get_due_scheduled_actions(_to_iso(now))
        count = 0
        for row in due:
            action = _row_to_action(row)
            try:
                await self._execute(action)
            except Exception:
                LOG.exception(
                    "Scheduled action #%s (%s) failed",
                    action.id,
                    action.action_type,
                )
                continue
            self._mark_run(db, action, now)
            count += 1
        return count

    def _mark_run(self, db, action: ScheduledAction, now: datetime) -> None:
        """Record that an action ran; reschedule or disable it."""
        last_run_iso = _to_iso(now)
        if action.repeating:
            next_run = _to_iso(now + timedelta(seconds=action.repeat_interval_seconds))
            db.update_scheduled_action(
                action.id, last_run_at=last_run_iso, run_at=next_run
            )
        else:
            db.update_scheduled_action(
                action.id, last_run_at=last_run_iso, enabled=0
            )

    async def _execute(self, action: ScheduledAction) -> None:
        """Run a single scheduled action.

        Raises:
            ValueError: If the action type is unknown, so the caller keeps the
                action unmarked instead of silently consuming it.
        """
        if action.action_type == TYPE_BROADCAST:
            await self._do_broadcast(action)
        elif action.action_type == TYPE_REBOOT:
            await self._do_reboot(action)
        else:
            raise ValueError(f"Unknown scheduled action type: {action.action_type}")

    async def _do_broadcast(self, action: ScheduledAction) -> None:
        """Send a free-text announcement to every approved online user."""
        message = str(action.payload.get("message") or "").strip()
        if not message:
            LOG.warning("Scheduled broadcast #%s had empty message", action.id)
            return
        recipients = 0
        for _username, online_user in self._server._iter_approved_users():
            online_user.speak(message, buffer="activity")
            online_user.play_sound("accountactionnotify.ogg")
            recipients += 1
        LOG.info("Scheduled broadcast #%s sent to %d users", action.id, recipients)

    async def _do_reboot(self, action: ScheduledAction) -> None:
        """Reboot the server (disconnecting virtual bots first)."""
        self._server._virtual_bots.disconnect_all_bots()
        await self._server._execute_reboot()