"""Tests for active table selection, auto-join, and saved tables flows."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from server.core.server import Server
from server.core.users.base import TrustLevel


class DummyUser:
    def __init__(self, username: str, uuid: str | None = None):
        self.username = username
        self.uuid = uuid or f"uuid-{username}"
        self.locale = "en"
        self.trust_level = TrustLevel.USER
        self.approved = True
        self.spoken: list[tuple[str, dict]] = []
        self.menu_shown: list[str] = []
        self.music_played: list[str] = []

    def speak_l(self, message_id: str, buffer: str = "misc", **kwargs) -> None:
        self.spoken.append((message_id, kwargs))

    def speak(self, text: str, buffer: str = "activity") -> None:
        self.spoken.append((text, {}))

    def show_menu(self, menu_id: str, *args, **kwargs) -> None:
        self.menu_shown.append(menu_id)

    def play_music(self, name: str, looping: bool = True) -> None:
        self.music_played.append(name)

    def play_sound(self, name: str) -> None:
        self.music_played.append(name)

    def stop_ambience(self):
        return None


class DummyGame:
    def __init__(self, status="waiting", players=None, max_players=4):
        self.status = status
        self.players = players or []
        self.max_players = max_players
        self.broadcasts: list[tuple[str, dict]] = []
        self.sounds: list[str] = []
        self._users = {}

    def get_max_players(self):
        return self.max_players

    def add_player(self, username, user):
        self.players.append(SimpleNamespace(id=user.uuid, name=username, is_bot=False))
        self._users[user.uuid] = user

    def add_spectator(self, username, user):
        self._users[user.uuid] = user

    def broadcast_l(self, message_id: str, **kwargs):
        self.broadcasts.append((message_id, kwargs))

    def broadcast_sound(self, name: str):
        self.sounds.append(name)

    def rebuild_all_menus(self):
        return None

    def get_player_by_id(self, pid):
        for p in self.players:
            if p.id == pid:
                return p
        return None

    def to_json(self):
        return "{}"


class DummyTable:
    def __init__(self, table_id="t1", game=None, host="hosty"):
        self.table_id = table_id
        self.game_type = "mock"
        self.members = []
        self.game = game or DummyGame()
        self.host = host

    def add_member(self, username, user, as_spectator=False):
        self.members.append(SimpleNamespace(username=username, is_spectator=as_spectator))


class DummyDB:
    def __init__(self, saved=None):
        self.saved = saved or []
        self.deleted = []

    def get_user_saved_tables(self, username):
        return self.saved

    def delete_saved_table(self, save_id):
        self.deleted.append(save_id)

    def get_saved_table(self, save_id):
        for rec in self.saved:
            if rec.id == save_id:
                return rec
        return None

    def get_game_stats(self, game_type, limit=1):
        return []


@pytest.fixture
def server(tmp_path, monkeypatch):
    srv = Server(host="127.0.0.1", port=0, db_path=tmp_path / "db.sqlite", preload_locales=True)
    monkeypatch.setattr(
        "server.messages.localization.Localization.get",
        lambda _locale, key, **kwargs: key,
    )
    monkeypatch.setattr(
        "server.messages.localization.Localization.format_list_and",
        lambda _locale, names: " and ".join(names),
    )
    return srv


class StubGameClass:
    @staticmethod
    def from_json(game_json):
        # Create game with two players: alice human, bot bot.
        players = [
            SimpleNamespace(id="p-alice", name="alice", is_bot=False),
            SimpleNamespace(id="p-bot", name="bot", is_bot=True),
        ]
        return StubGameInstance(players)

    @staticmethod
    def get_name_key():
        return "stub"

    @staticmethod
    def get_leaderboard_types():
        return []

    @staticmethod
    def get_type():
        return "stub"


class StubGameInstance:
    def __init__(self, players):
        self.players = players
        self._users = {}
        self.broadcasts: list[tuple[str, dict]] = []
        self.host = None

    def rebuild_runtime_state(self):
        return None

    def get_player_by_name(self, name):
        for p in self.players:
            if getattr(p, "name", None) == name:
                return p
        return None

    def attach_user(self, pid, user):
        self._users[pid] = user

    def setup_keybinds(self):
        return None

    def rebuild_all_menus(self):
        return None

    def broadcast_l(self, message_id, **kwargs):
        self.broadcasts.append((message_id, kwargs))


def test_handle_active_tables_selection_missing_table_speaks(server):
    user = DummyUser("alice")
    server._users = {"alice": user}
    server._tables.get_table = lambda _tid: None  # type: ignore[attr-defined]

    asyncio.run(server._handle_active_tables_selection(user, "table_missing"))

    assert ("table-not-exists", {}) in user.spoken
    # No active tables left, so it speaks "no-active-tables" and falls back to main menu
    assert ("no-active-tables", {}) in user.spoken
    assert user.menu_shown[-1] == "main_menu"


def test_handle_active_tables_selection_back(server):
    user = DummyUser("alice")
    server._users = {"alice": user}

    asyncio.run(server._handle_active_tables_selection(user, "back"))

    assert user.menu_shown[-1] == "main_menu"


def test_auto_join_player_when_waiting(server):
    user = DummyUser("alice")
    game = DummyGame(status="waiting", players=[])
    table = DummyTable(game=game)

    server._auto_join_table(user, table, "mock")

    assert any(msg[0] == "table-joined" for msg in game.broadcasts)
    assert "join.ogg" in game.sounds
    assert server._user_states[user.username]["menu"] == "in_game"


def test_auto_join_spectator_when_full(server):
    user = DummyUser("alice")
    existing = [SimpleNamespace(id="p1", is_bot=False), SimpleNamespace(id="p2", is_bot=False)]
    game = DummyGame(status="playing", players=existing, max_players=2)
    table = DummyTable(game=game)

    server._auto_join_table(user, table, "mock")

    assert any(msg[0] == "now-spectating" for msg in game.broadcasts)
    assert "join_spectator.ogg" in game.sounds
    assert server._user_states[user.username]["menu"] == "in_game"


def test_handle_saved_tables_selection_routes(server):
    user = DummyUser("alice")
    server._users = {"alice": user}
    state = {}

    asyncio.run(server._handle_saved_tables_selection(user, "saved_5", state))
    assert user.menu_shown[-1] == "saved_table_actions_menu"

    asyncio.run(server._handle_saved_tables_selection(user, "back", state))
    assert user.menu_shown[-1] == "main_menu"


def test_handle_saved_table_actions_delete(server):
    user = DummyUser("alice")
    server._users = {"alice": user}
    db = DummyDB(
        saved=[
            SimpleNamespace(
                id=1, save_name="Test", game_type="mock", members_json="[]", game_json="{}"
            )
        ]
    )
    server._db = db
    state = {"save_id": 1}

    asyncio.run(server._handle_saved_table_actions_selection(user, "delete", state))

    assert db.deleted == [1]
    assert user.menu_shown[-1] == "saved_tables_menu"


def test_restore_saved_table_missing_record(server, monkeypatch):
    user = DummyUser("alice")
    server._users = {"alice": user}
    server._db = DummyDB(saved=[])
    called = {}
    monkeypatch.setattr(server, "_show_main_menu", lambda u: called.setdefault("main", True))

    asyncio.run(server._restore_saved_table(user, 99))

    assert ("table-not-exists", {}) in user.spoken
    assert called.get("main")


def test_restore_saved_table_missing_game_class(server, monkeypatch):
    user = DummyUser("alice")
    server._users = {"alice": user}
    record = SimpleNamespace(id=1, game_type="missing", members_json="[]", game_json="{}")
    db = DummyDB(saved=[record])
    server._db = db
    monkeypatch.setattr("server.core.server.get_game_class", lambda _gt: None)
    called = {}
    monkeypatch.setattr(server, "_show_main_menu", lambda u: called.setdefault("main", True))

    asyncio.run(server._restore_saved_table(user, 1))

    assert ("game-type-not-found", {}) in user.spoken
    assert called.get("main")


def test_restore_saved_table_missing_players(server, monkeypatch):
    user = DummyUser("alice")
    server._users = {"alice": user}  # missing 'bob'
    record = SimpleNamespace(
        id=2,
        game_type="stub",
        members_json='[{"username": "alice", "is_bot": false}, {"username": "bob", "is_bot": false}]',
        game_json="{}",
    )
    db = DummyDB(saved=[record])
    server._db = db
    monkeypatch.setattr("server.core.server.get_game_class", lambda _gt: StubGameClass)
    # ensure find_user_table returns something for bob to simulate missing/occupied
    server._tables.find_user_table = lambda name: SimpleNamespace() if name == "bob" else None  # type: ignore[attr-defined]
    called = {}
    monkeypatch.setattr(
        server, "_show_saved_tables_menu", lambda u: called.setdefault("saved", True)
    )

    asyncio.run(server._restore_saved_table(user, 2))

    assert any(msg[0] == "missing-players" for msg in user.spoken)
    assert called.get("saved")


def test_restore_saved_table_success(server, monkeypatch):
    user = DummyUser("alice")
    bot_user = DummyUser("bot")
    server._users = {"alice": user, "bot": bot_user}
    record = SimpleNamespace(
        id=3,
        game_type="stub",
        members_json='[{"username": "alice", "is_bot": false}, {"username": "bot", "is_bot": true}]',
        game_json="{}",
    )
    db = DummyDB(saved=[record])
    server._db = db
    monkeypatch.setattr("server.core.server.get_game_class", lambda _gt: StubGameClass)

    created_tables = []

    class FakeTables:
        def create_table(self, game_type, host, host_user):
            tbl = DummyTable(table_id="restored", game=StubGameInstance([]), host=host)
            created_tables.append(tbl)
            return tbl

        def find_user_table(self, username):
            return None

    server._tables = FakeTables()  # type: ignore[assignment]

    asyncio.run(server._restore_saved_table(user, 3))

    assert created_tables, "table should be created"
    game = created_tables[0].game
    assert isinstance(game, StubGameInstance)
    assert ("table-restored", {}) in game.broadcasts
    assert db.deleted == [3]
    assert server._user_states["alice"]["menu"] == "in_game"
    # bot user should be attached via Bot recreation (is_bot True path)
    assert any(u.username == "bot" for u in game._users.values())


def _cah_pending_state(server, user, action="create", return_menu="tables_menu", table_id=None):
    pending = {"action": action, "return_menu": return_menu, "game_type": "humanitycards"}
    if table_id:
        pending["table_id"] = table_id
    server._user_states[user.username] = {"menu": "cah_content_notice_menu", "pending": pending}
    return server._user_states[user.username]


def test_create_cah_table_shows_notice_first(server, monkeypatch):
    user = DummyUser("alice")
    server._users = {"alice": user}
    monkeypatch.setattr(
        "server.core.server.get_game_class", lambda _gt: CahStubGameClass
    )

    asyncio.run(
        server._handle_tables_selection(user, "create_table", {"game_type": "humanitycards"})
    )

    assert user.menu_shown[-1] == "cah_content_notice_menu"
    state = server._user_states["alice"]
    assert state["menu"] == "cah_content_notice_menu"
    assert state["pending"]["action"] == "create"
    # Table must not be created yet.
    assert server._tables.get_all_tables() == []


def test_cah_notice_keep_playing_creates_table(server, monkeypatch):
    user = DummyUser("alice")
    server._users = {"alice": user}
    monkeypatch.setattr(
        "server.core.server.get_game_class", lambda _gt: CahStubGameClass
    )
    state = _cah_pending_state(server, user, action="create")

    asyncio.run(server._handle_cah_notice_selection(user, "keep_playing", state))

    tables = server._tables.get_all_tables()
    assert len(tables) == 1
    assert tables[0].game_type == "humanitycards"
    assert server._user_states["alice"]["menu"] == "in_game"


def test_cah_notice_go_back_returns_to_tables_menu(server):
    user = DummyUser("alice")
    server._users = {"alice": user}
    state = _cah_pending_state(server, user, action="create")

    asyncio.run(server._handle_cah_notice_selection(user, "back", state))

    assert user.menu_shown[-1] == "tables_menu"
    assert server._tables.get_all_tables() == []


def test_join_cah_table_from_tables_menu_shows_notice(server):
    user = DummyUser("alice")
    host = DummyUser("hosty")
    server._users = {"alice": user, "hosty": host}
    table = server._tables.create_table("humanitycards", "hosty", host)
    table.game = DummyGame(status="waiting", players=[])

    asyncio.run(
        server._handle_tables_selection(user, f"table_{table.table_id}", {"game_type": "humanitycards"})
    )

    assert user.menu_shown[-1] == "cah_content_notice_menu"
    state = server._user_states["alice"]
    assert state["pending"]["action"] == "join"
    assert state["pending"]["table_id"] == table.table_id
    # User must not have joined yet.
    assert server._user_states.get("alice", {}).get("menu") == "cah_content_notice_menu"


def test_cah_notice_keep_playing_joins_table(server):
    user = DummyUser("alice")
    host = DummyUser("hosty")
    server._users = {"alice": user, "hosty": host}
    table = server._tables.create_table("humanitycards", "hosty", host)
    game = DummyGame(status="waiting", players=[])
    table.game = game
    state = _cah_pending_state(
        server, user, action="join", table_id=table.table_id
    )

    asyncio.run(server._handle_cah_notice_selection(user, "keep_playing", state))

    assert any(msg[0] == "table-joined" for msg in game.broadcasts)
    assert "join.ogg" in game.sounds
    assert server._user_states["alice"]["menu"] == "in_game"


def test_join_cah_table_from_active_tables_shows_notice(server):
    user = DummyUser("alice")
    host = DummyUser("hosty")
    server._users = {"alice": user, "hosty": host}
    table = server._tables.create_table("humanitycards", "hosty", host)
    table.game = DummyGame(status="waiting", players=[])

    asyncio.run(server._handle_active_tables_selection(user, f"table_{table.table_id}"))

    assert user.menu_shown[-1] == "cah_content_notice_menu"
    state = server._user_states["alice"]
    assert state["pending"]["action"] == "join"
    assert state["pending"]["return_menu"] == "active_tables_menu"


def test_cah_notice_go_back_from_active_tables_returns_to_active_tables(server):
    user = DummyUser("alice")
    host = DummyUser("hosty")
    server._users = {"alice": user, "hosty": host}
    table = server._tables.create_table("humanitycards", "hosty", host)
    table.game = DummyGame(status="waiting", players=[])
    state = _cah_pending_state(
        server, user, action="join", return_menu="active_tables_menu", table_id=table.table_id
    )

    asyncio.run(server._handle_cah_notice_selection(user, "back", state))

    assert user.menu_shown[-1] == "active_tables_menu"


def test_cah_notice_join_missing_table_speaks(server):
    user = DummyUser("alice")
    server._users = {"alice": user}
    state = _cah_pending_state(server, user, action="join", table_id="missing")

    asyncio.run(server._handle_cah_notice_selection(user, "keep_playing", state))

    assert ("table-not-exists", {}) in user.spoken
    assert user.menu_shown[-1] == "tables_menu"


def test_non_cah_create_does_not_show_notice(server):
    user = DummyUser("alice")
    server._users = {"alice": user}

    asyncio.run(
        server._handle_tables_selection(user, "create_table", {"game_type": "stub"})
    )

    assert "cah_content_notice_menu" not in user.menu_shown
    assert server._user_states["alice"]["menu"] == "in_game"


class CahStubGameClass:
    """Minimal stand-in for the real humanitycards game class."""

    @staticmethod
    def get_name_key():
        return "game-name-humanitycards"

    @staticmethod
    def get_min_players():
        return 3

    @staticmethod
    def get_max_players():
        return 10

    @staticmethod
    def get_type():
        return "humanitycards"

    def __init__(self):
        self.players = []

    def initialize_lobby(self, host_name, user):
        self.players.append(SimpleNamespace(id=user.uuid, name=user.username, is_bot=False))

    def to_json(self):
        return "{}"
