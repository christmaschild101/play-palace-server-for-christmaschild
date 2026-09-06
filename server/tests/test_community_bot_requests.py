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
    def __init__(self):
        self.approved = True
        self.spoken = []

    def speak_l(self, key, buffer="misc", **kwargs):
        self.spoken.append((key, buffer, kwargs))


def _make_mixin(manager, db):
    mixin = GameManagerMixin()
    mixin._virtual_bots = manager
    mixin._db = db
    mixin._users = {"carol": FakeUser()}
    # Provided by AdministrationMixin in the real composition; stub it here.
    mixin._validate_bot_name = lambda name, exclude=None: None
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
