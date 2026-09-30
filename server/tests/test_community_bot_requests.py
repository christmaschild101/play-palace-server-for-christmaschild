"""Tests for community bot-request acceptance wiring.

The key regression guard: accepting a request must call
``VirtualBotManager.save_state()`` (like the admin add-bot flow) so the
new bot is restored into the login rotation after a server restart.
"""

import asyncio

from server.core.community import GameManagerMixin


class FakeManager:
    def __init__(self, add_result=True):
        self.add_result = add_result
        self.added = []
        self.saved = 0

    def add_bot(self, name):
        if not self.add_result:
            return False
        self.added.append(name)
        return True

    def save_state(self):
        self.saved += 1


class FakeDB:
    def __init__(self):
        self.statuses = {}

    def set_bot_request_status(self, request_id, status):
        self.statuses[request_id] = status
        return True

    def get_bot_request(self, request_id):
        return {
            "id": request_id,
            "name": " Speedy ",
            "description": "fast racer bot",
            "requester": "carol",
            "created_at": "2026-09-06 18:00:00",
        }


class FakeUser:
    def __init__(self, approved=True):
        self.approved = approved
        self.spoken = []

    def speak_l(self, key, buffer="misc", **kwargs):
        self.spoken.append((key, buffer, kwargs))


def _make_mixin(manager, db, users=None):
    mixin = GameManagerMixin()
    mixin._virtual_bots = manager
    mixin._db = db
    mixin._users = users if users is not None else {"carol": FakeUser()}
    # Provided by the other mixins in the real Server composition; stub them here.
    mixin._validate_bot_name = lambda name, exclude=None: None
    mixin._iter_approved_users = lambda: (
        (name, u) for name, u in mixin._users.items() if u.approved
    )
    return mixin


def _req():
    return {
        "id": 1,
        "name": " Speedy ",
        "description": "fast racer bot",
        "requester": "carol",
        "created_at": "2026-09-06 18:00:00",
    }


def test_accept_creates_bot_and_persists_state():
    manager, db = FakeManager(), FakeDB()
    mixin = _make_mixin(manager, db)

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))

    assert manager.added == ["Speedy"]  # stripped name
    assert manager.saved == 1  # restart-safe: state row written immediately
    assert db.statuses == {1: "accepted"}


def test_accept_name_taken_does_not_persist():
    manager, db = FakeManager(add_result=False), FakeDB()
    mixin = _make_mixin(manager, db)

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))

    assert manager.saved == 0
    assert db.statuses == {}  # request stays pending


def test_accept_invalid_name_does_not_create_or_persist():
    manager, db = FakeManager(), FakeDB()
    mixin = _make_mixin(manager, db)
    mixin._validate_bot_name = lambda name, exclude=None: "virtual-bots-name-invalid"

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))

    assert manager.added == []
    assert manager.saved == 0
    assert db.statuses == {}


def test_accept_without_manager_is_a_noop():
    mixin = GameManagerMixin()
    mixin._virtual_bots = None
    mixin._db = FakeDB()
    mixin._users = {}

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))  # must not raise


def _activity_lines(user):
    return [s for s in user.spoken if s[0] == "bot-request-accepted-activity"]


def test_accept_broadcasts_activity_to_approved_users():
    """Everyone online sees who the new bot came from in the activity feed."""
    carol, dave, dev = FakeUser(), FakeUser(), FakeUser(approved=False)
    mixin = _make_mixin(
        FakeManager(),
        FakeDB(),
        users={"carol": carol, "dave": dave, "dev": dev},
    )

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))

    for user in (carol, dave):
        lines = _activity_lines(user)
        assert lines == [
            ("bot-request-accepted-activity", "activity", {"name": "Speedy", "requester": "carol"})
        ]
    # The approving developer is unapproved=False here only as a fixture:
    # the broadcast iterates _iter_approved_users, so they get none from it.
    assert _activity_lines(dev) == []


def test_accept_name_taken_does_not_broadcast_activity():
    carol, dave = FakeUser(), FakeUser()
    mixin = _make_mixin(
        FakeManager(add_result=False),
        FakeDB(),
        users={"carol": carol, "dave": dave},
    )

    asyncio.run(mixin._accept_bot_request(FakeUser(), _req()))

    assert _activity_lines(carol) == []
    assert _activity_lines(dave) == []
