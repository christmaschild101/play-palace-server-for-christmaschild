"""Tests for the server freeze feature.

Covers the admin-menu freeze/unfreeze items, the confirm flow, the
broadcast to players, the dispatch gate that blocks non-admin packets
while frozen, ping keepalive while frozen, and the in-memory reset
semantics.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.core.server import Server
from server.core.users.base import TrustLevel
from server.network.websocket_server import ClientConnection


class DummyUser:
    def __init__(self, username: str, trust_level: TrustLevel = TrustLevel.USER):
        self.username = username
        self.locale = "en"
        self.trust_level = trust_level
        self.approved = True
        self.is_virtual_bot = False
        self.spoken: list[tuple[str, dict]] = []
        self.sounds: list[str] = []
        self.menus: list[dict] = []

    def speak_l(self, message_id: str, **kwargs) -> None:
        self.spoken.append((message_id, kwargs))

    def speak(self, text: str, buffer: str = "misc") -> None:
        self.spoken.append(("__raw__", {"text": text, "buffer": buffer}))

    def play_sound(self, sound: str) -> None:
        self.sounds.append(sound)

    def show_menu(self, menu_id: str, items, **kwargs) -> None:
        self.menus.append({"menu_id": menu_id, "items": items})


class DummyWebSocket:
    def __init__(self):
        self.sent = []

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        pass

    @property
    def remote_address(self):
        return ("127.0.0.1", 1234)


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = Server(
        host="127.0.0.1",
        port=0,
        db_path=tmp_path / "db.sqlite",
        preload_locales=True,
    )
    monkeypatch.setattr(
        "server.messages.localization.Localization.get",
        lambda _locale, key, **kwargs: key,
    )
    return srv


def _menu_item_ids(user: DummyUser) -> list[str]:
    return [item.id for item in user.menus[-1]["items"]]


def _conn(username: str) -> ClientConnection:
    conn = ClientConnection(DummyWebSocket(), f"{username}:1")
    conn.authenticated = True
    conn.username = username
    return conn


# ---------- Admin menu items ----------


def test_admin_menu_has_freeze_item(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    server._users["boss"] = admin

    server._show_admin_menu(admin)

    ids = _menu_item_ids(admin)
    assert "freeze_server" in ids
    assert "unfreeze_server" not in ids


def test_admin_menu_flips_to_unfreeze_when_frozen(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    server._users["boss"] = admin
    server._set_frozen(True)

    server._show_admin_menu(admin)

    ids = _menu_item_ids(admin)
    assert "unfreeze_server" in ids
    assert "freeze_server" not in ids


def test_new_server_starts_unfrozen(server):
    assert not server._is_frozen()


# ---------- Confirm flow ----------


@pytest.mark.asyncio
async def test_freeze_menu_selection_opens_confirm(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    server._users["boss"] = admin

    await server._handle_admin_menu_selection(admin, "freeze_server")

    assert admin.menus[-1]["menu_id"] == "freeze_confirm_menu"
    assert not server._is_frozen()


@pytest.mark.asyncio
async def test_freeze_confirm_yes_freezes_and_broadcasts(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    alice = DummyUser("alice", TrustLevel.USER)
    bot = DummyUser("bot1", TrustLevel.USER)
    bot.is_virtual_bot = True
    newbie = DummyUser("newbie", TrustLevel.USER)
    newbie.approved = False
    server._users.update(
        {"boss": admin, "alice": alice, "bot1": bot, "newbie": newbie}
    )

    await server._handle_freeze_confirm_selection(admin, "yes")

    assert server._is_frozen()
    # Broadcast reaches approved human users only
    assert alice.spoken[-1][0] == "server-frozen"
    assert alice.sounds[-1] == "accountactionnotify.ogg"
    assert bot.spoken == []
    assert newbie.spoken == []
    # Admin menu reshown with the flipped item
    assert admin.menus[-1]["menu_id"] == "admin_menu"
    assert "unfreeze_server" in _menu_item_ids(admin)


@pytest.mark.asyncio
async def test_freeze_confirm_no_cancels(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    server._users["boss"] = admin
    server._set_frozen(False)

    await server._handle_freeze_confirm_selection(admin, "no")

    assert not server._is_frozen()
    assert admin.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_unfreeze_selection_unfreezes_and_broadcasts(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    alice = DummyUser("alice", TrustLevel.USER)
    server._users.update({"boss": admin, "alice": alice})
    server._set_frozen(True)

    await server._handle_admin_menu_selection(admin, "unfreeze_server")

    assert not server._is_frozen()
    assert alice.spoken[-1][0] == "server-unfrozen"


# ---------- Dispatch gate ----------


@pytest.mark.asyncio
async def test_frozen_dispatch_blocks_player_packets(server):
    player = DummyUser("alice", TrustLevel.USER)
    server._users["alice"] = player
    server._user_states["alice"] = {"menu": "main_menu"}
    server._set_frozen(True)

    calls = {"menu": 0, "chat": 0, "editbox": 0, "keybind": 0}

    async def fake_menu(client, packet):
        calls["menu"] += 1

    async def fake_chat(client, packet):
        calls["chat"] += 1

    async def fake_editbox(client, packet):
        calls["editbox"] += 1

    async def fake_keybind(client, packet):
        calls["keybind"] += 1

    server._handle_menu = fake_menu
    server._handle_chat = fake_chat
    server._handle_editbox = fake_editbox
    server._handle_keybind = fake_keybind

    conn = _conn("alice")
    await server._dispatch_client_message(conn, {"type": "menu", "selection_id": "x"})
    await server._dispatch_client_message(conn, {"type": "chat", "message": "hi"})
    await server._dispatch_client_message(conn, {"type": "editbox", "text": "t"})
    await server._dispatch_client_message(conn, {"type": "keybind", "key": "k"})

    assert calls == {"menu": 0, "chat": 0, "editbox": 0, "keybind": 0}
    assert player.spoken[-1][0] == "server-frozen-notice"


@pytest.mark.asyncio
async def test_frozen_dispatch_allows_admins(server):
    admin = DummyUser("boss", TrustLevel.ADMIN)
    server._users["boss"] = admin
    server._user_states["boss"] = {"menu": "admin_menu"}
    server._set_frozen(True)

    calls = {}
    async def fake_menu(client, packet):
        calls["menu"] = True

    server._handle_menu = fake_menu
    conn = _conn("boss")

    await server._dispatch_client_message(conn, {"type": "menu", "selection_id": "x"})

    assert calls.get("menu")
    assert admin.spoken == []


@pytest.mark.asyncio
async def test_frozen_dispatch_still_allows_ping(server):
    player = DummyUser("alice", TrustLevel.USER)
    server._users["alice"] = player
    server._set_frozen(True)

    calls = {}
    async def fake_ping(client):
        calls["ping"] = True

    server._handle_ping = fake_ping
    conn = _conn("alice")

    await server._dispatch_client_message(conn, {"type": "ping"})

    assert calls.get("ping")
    assert player.spoken == []


# ---------- Toggle helper ----------


def test_toggle_freeze_flips_state(server):
    assert not server._is_frozen()
    server._set_frozen(True)
    assert server._is_frozen()
    server._set_frozen(False)
    assert not server._is_frozen()