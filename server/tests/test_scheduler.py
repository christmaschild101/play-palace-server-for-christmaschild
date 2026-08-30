"""Tests for the scheduled actions manager."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from server.core.scheduler import (
    TYPE_BROADCAST,
    TYPE_REBOOT,
    ScheduledAction,
    ScheduledActionManager,
    _row_to_action,
)


def _row(
    action_id=1,
    action_type=TYPE_BROADCAST,
    run_at=None,
    repeat=0,
    enabled=1,
    payload='{"message": "hi"}',
    last_run_at=None,
):
    return {
        "id": action_id,
        "action_type": action_type,
        "payload_json": payload,
        "run_at": (run_at or datetime.now(timezone.utc)).isoformat(),
        "repeat_interval_seconds": repeat,
        "enabled": enabled,
        "created_by": "owner",
        "last_run_at": last_run_at,
    }


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.saved = []
        self.updates = []
        self.deleted = []

    def get_due_scheduled_actions(self, now_iso):
        return [r for r in self.rows if r["enabled"] and r["run_at"] <= now_iso]

    def update_scheduled_action(self, action_id, **kwargs):
        self.updates.append((action_id, kwargs))

    def save_scheduled_action(self, **kwargs):
        self.saved.append(kwargs)
        return len(self.saved)

    def delete_scheduled_action(self, action_id):
        self.deleted.append(action_id)

    def list_scheduled_actions(self):
        return self.rows


class FakeUser:
    def __init__(self, username="alice"):
        self.username = username
        self.spoken = []
        self.sounds = []

    def speak(self, text, buffer="misc"):
        self.spoken.append((text, buffer))

    def play_sound(self, sound):
        self.sounds.append(sound)


class FakeServer:
    def __init__(self, db=None, users=None):
        self._db = db or FakeDB()
        self._users = users or {}
        self._virtual_bots = SimpleNamespace(disconnect_all_bots=lambda: [])
        self._iter_approved_users = lambda: self._users.items()
        self.rebooted = 0

    async def _execute_reboot(self):
        self.rebooted += 1


def _make_manager(server=None):
    server = server or FakeServer()
    return ScheduledActionManager(server), server


def test_row_to_action_parses_fields():
    row = _row(action_id=5, repeat=600, enabled=0)
    action = _row_to_action(row)
    assert action.id == 5
    assert action.action_type == TYPE_BROADCAST
    assert action.payload == {"message": "hi"}
    assert action.repeat_interval_seconds == 600
    assert not action.enabled
    assert action.repeating


def test_row_to_action_survives_corrupt_payload():
    row = _row(payload="not json")
    action = _row_to_action(row)
    assert action.payload == {}


@pytest.mark.asyncio
async def test_run_due_actions_broadcast_and_reschedule_one_shot():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(run_at=past, enabled=1)]
    user = FakeUser()
    server._users = {"alice": user}

    count = await manager.run_due_actions()

    assert count == 1
    assert user.spoken == [("hi", "activity")]
    assert user.sounds == ["accountactionnotify.ogg"]
    # One-shot: disabled and last_run recorded
    updates = dict(server._db.updates[0][1])
    assert updates["enabled"] == 0
    assert updates["last_run_at"] is not None


@pytest.mark.asyncio
async def test_run_due_actions_repeating_reschedules():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(run_at=past, repeat=600)]
    server._users = {"alice": FakeUser()}

    await manager.run_due_actions()

    updates = dict(server._db.updates[0][1])
    assert updates.get("enabled", 1) == 1  # repeating actions stay enabled
    assert updates["run_at"] > updates["last_run_at"]  # rescheduled forward


@pytest.mark.asyncio
async def test_run_due_actions_reboot_disconnects_bots_and_reboots():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(action_type=TYPE_REBOOT, run_at=past, payload="{}")]

    count = await manager.run_due_actions()

    assert count == 1
    assert server.rebooted == 1


@pytest.mark.asyncio
async def test_run_due_actions_skips_not_due():
    manager, server = _make_manager()
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    server._db.rows = [_row(run_at=future)]

    count = await manager.run_due_actions()
    assert count == 0


@pytest.mark.asyncio
async def test_run_due_actions_skips_disabled():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(run_at=past, enabled=0)]

    count = await manager.run_due_actions()
    assert count == 0


@pytest.mark.asyncio
async def test_run_due_actions_unknown_type_logged_not_marked():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(action_type="dance", run_at=past)]

    count = await manager.run_due_actions()
    assert count == 0
    assert server._db.updates == []


@pytest.mark.asyncio
async def test_run_due_actions_empty_broadcast_still_marks_run():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(payload='{"message": ""}', run_at=past)]

    count = await manager.run_due_actions()
    assert count == 1
    assert server._db.updates  # marked as run (disabled)


@pytest.mark.asyncio
async def test_execution_error_does_not_mark_run():
    manager, server = _make_manager()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    server._db.rows = [_row(action_type=TYPE_REBOOT, run_at=past, payload="{}")]

    async def failing_reboot():
        raise RuntimeError("boom")

    server._execute_reboot = failing_reboot

    count = await manager.run_due_actions()
    assert count == 0
    assert server._db.updates == []


@pytest.mark.asyncio
async def test_create_action_persists():
    manager, server = _make_manager()
    run_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    manager.create_action(
        action_type=TYPE_BROADCAST,
        run_at=run_at,
        repeat_interval_seconds=0,
        payload={"message": "hi"},
        created_by="owner",
    )

    saved = server._db.saved[0]
    assert saved["action_type"] == TYPE_BROADCAST
    assert "hi" in saved["payload_json"]
    assert saved["created_by"] == "owner"


@pytest.mark.asyncio
async def test_start_stop_lifecycle():
    manager, _server = _make_manager()
    await manager.start()
    assert manager._task is not None
    await manager.stop()
    assert manager._task is None
    # Double stop is safe
    await manager.stop()


def test_run_at_from_minutes():
    manager, _server = _make_manager()
    before = datetime.now(timezone.utc)
    result = manager.run_at_from_minutes_from_now(10)
    after = datetime.now(timezone.utc)
    assert before + timedelta(minutes=10) <= result <= after + timedelta(minutes=10)
