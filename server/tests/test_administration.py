"""Tests for the AdministrationMixin and decorators."""

import types
from types import SimpleNamespace

import pytest

from server.core import administration
from server.core.administration import (
    AdministrationMixin,
    require_admin,
    require_developer,
    require_server_owner,
)
from server.core.users.base import TrustLevel, MenuItem


@pytest.fixture(autouse=True)
def fake_localization(monkeypatch):
    monkeypatch.setattr(
        administration.Localization,
        "get",
        lambda locale, key, **kwargs: f"{key}",
    )


class DummyUser:
    def __init__(self, username: str, trust: TrustLevel):
        self.username = username
        self.locale = "en"
        self.trust_level = trust
        self.spoken = []
        self.sounds = []
        self.menus = []
        self.editboxes = []

    def speak_l(self, message_id: str, **kwargs):
        self.spoken.append((message_id, kwargs))

    def speak(self, text: str, buffer: str = "misc"):
        self.spoken.append(("__raw__", {"text": text, "buffer": buffer}))

    def play_sound(self, sound: str):
        self.sounds.append(sound)

    def show_menu(self, menu_id: str, items: list[MenuItem], **kwargs):
        self.menus.append({"menu_id": menu_id, "items": items, "kwargs": kwargs})

    def show_editbox(self, input_id: str, prompt: str, **kwargs):
        self.editboxes.append((input_id, prompt, kwargs))


class DummyDB:
    def __init__(self):
        self.pending_users: list[str] = []
        self.non_admin_users: list[str] = []
        self.admin_users: list[str] = []
        self.developers: list[str] = []

    def get_pending_users(self):
        return [SimpleNamespace(username=name) for name in self.pending_users]

    def get_non_admin_users(self, exclude_banned=True):
        return [SimpleNamespace(username=name) for name in self.non_admin_users]

    def get_admin_users(self, include_server_owner=True):
        users = [SimpleNamespace(username=name) for name in self.admin_users]
        if not include_server_owner and self.admin_users:
            return users
        return users

    def get_developers(self):
        return [SimpleNamespace(username=name) for name in self.developers]

    def get_user(self, username):
        if username in self.non_admin_users:
            return SimpleNamespace(
                username=username, trust_level=TrustLevel.USER, approved=True
            )
        if username in self.admin_users:
            return SimpleNamespace(
                username=username, trust_level=TrustLevel.ADMIN, approved=True
            )
        if username in self.developers:
            return SimpleNamespace(
                username=username, trust_level=TrustLevel.DEVELOPER, approved=True
            )
        return None

    def get_user_count(self):
        return len(self.non_admin_users) + len(self.admin_users) + len(self.developers)

    def update_user_trust_level(self, username: str, trust_level: TrustLevel) -> None:
        for bucket in (self.non_admin_users, self.admin_users, self.developers):
            if username in bucket:
                bucket.remove(username)
        if trust_level == TrustLevel.DEVELOPER:
            self.developers.append(username)
        elif trust_level == TrustLevel.ADMIN:
            self.admin_users.append(username)
        elif trust_level == TrustLevel.USER:
            self.non_admin_users.append(username)


class DummyScheduler:
    def __init__(self):
        self.actions = []
        self.created = []
        self.deleted = []
        self.toggled = []

    def list_actions(self):
        return list(self.actions)

    def create_action(self, **kwargs):
        self.created.append(kwargs)
        return 1

    def delete_action(self, action_id):
        self.deleted.append(action_id)

    def set_enabled(self, action_id, enabled):
        self.toggled.append((action_id, enabled))

    def run_at_from_minutes_from_now(self, minutes):
        from datetime import datetime, timedelta, timezone

        return datetime.now(timezone.utc) + timedelta(minutes=minutes)


class AdminHost(AdministrationMixin):
    def __init__(self, db=None):
        self._db = db or DummyDB()
        self._users = {}
        self._user_states = {}
        self._started_at = None
        self._tables = SimpleNamespace(get_all_tables=lambda: [])
        self._virtual_bots = SimpleNamespace(
            get_status=lambda: {"total": 0, "online": 0, "offline": 0, "in_game": 0}
        )
        self._scheduler = DummyScheduler()
        self._documents = SimpleNamespace(load=lambda: 0)
        self.main_menu_calls = []
        self.warmups = 0

    def _show_main_menu(self, user: DummyUser) -> None:
        self.main_menu_calls.append(user.username)

    def _iter_approved_users(self):
        for username, u in self._users.items():
            if getattr(u, "approved", True):
                yield username, u

    def _start_localization_warmup(self) -> None:
        self.warmups += 1



@pytest.mark.asyncio
async def test_require_admin_and_server_owner_decorators():
    host = AdminHost()
    user = DummyUser("regular", TrustLevel.USER)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    calls = {"admin": 0, "owner": 0}

    class Handler(AdminHost):
        def __init__(self):
            super().__init__()

        @require_admin
        async def admin_action(self, admin):
            calls["admin"] += 1

        @require_server_owner
        async def owner_action(self, owner_user):
            calls["owner"] += 1

    handler = Handler()

    await handler.admin_action(user)
    assert calls["admin"] == 0
    assert user.spoken[0][0] == "not-admin-anymore"
    assert handler.main_menu_calls == ["regular"]

    await handler.admin_action(owner)
    assert calls["admin"] == 1

    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    await handler.owner_action(admin_user)
    assert calls["owner"] == 0
    assert handler.main_menu_calls.count("admin") == 1

    await handler.owner_action(owner)
    assert calls["owner"] == 1


@pytest.mark.asyncio
async def test_require_developer_decorator():
    host = AdminHost()
    calls = {"dev": 0, "owner": 0}

    class Handler(AdminHost):
        def __init__(self):
            super().__init__()

        @require_developer
        async def dev_action(self, user):
            calls["dev"] += 1

    handler = Handler()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    dev_user = DummyUser("dev", TrustLevel.DEVELOPER)
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)

    # Admin is below developer: blocked
    await handler.dev_action(admin_user)
    assert calls["dev"] == 0
    assert admin_user.spoken[0][0] == "not-server-owner"
    assert handler.main_menu_calls == ["admin"]

    # Developer and owner both pass
    await handler.dev_action(dev_user)
    await handler.dev_action(owner_user)
    assert calls["dev"] == 2


def test_notify_admins_and_exclusions():
    host = AdminHost()
    admin_user = DummyUser("alice", TrustLevel.ADMIN)
    regular_user = DummyUser("bob", TrustLevel.USER)
    owner_user = DummyUser("carol", TrustLevel.SERVER_OWNER)
    host._users = {
        "alice": admin_user,
        "bob": regular_user,
        "carol": owner_user,
    }

    host._notify_admins("alert", "ding", exclude_username="carol")

    assert admin_user.spoken[0][0] == "alert"
    assert admin_user.sounds == ["ding"]
    assert owner_user.spoken == []  # excluded
    assert regular_user.spoken == []  # not an admin


def _get_menu_ids(user: DummyUser) -> list[str]:
    return [item.id for item in user.menus[-1]["items"]]


def test_show_admin_menu_includes_owner_actions():
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_admin_menu(admin_user)
    admin_ids = _get_menu_ids(admin_user)
    assert admin_ids == [
        "account_approval",
        "reset_user_password",
        "ban_user",
        "unban_user",
        "server_status",
        "kick_user",
        "reboot_server",
        "freeze_server",
        "back",
    ]
    assert host._user_states["admin"]["menu"] == "admin_menu"

    host._show_admin_menu(owner_user)
    owner_ids = _get_menu_ids(owner_user)
    assert owner_ids == [
        "account_approval",
        "reset_user_password",
        "ban_user",
        "unban_user",
        "server_status",
        "kick_user",
        "reboot_server",
        "freeze_server",
        "promote_admin",
        "demote_admin",
        "virtual_bots",
        "broadcast_announcement",
        "lookup_user",
        "admin_reload_caches",
        "promote_developer",
        "demote_developer",
        "transfer_ownership",
        "scheduled_actions",
        "back",
    ]


def test_account_approval_menu_handles_pending_and_empty():
    db = DummyDB()
    host = AdminHost(db=db)
    admin_user = DummyUser("admin", TrustLevel.ADMIN)

    host._show_account_approval_menu(admin_user)
    assert admin_user.spoken[0][0] == "no-pending-accounts"
    assert admin_user.menus[-1]["menu_id"] == "admin_menu"

    db.pending_users = ["alice", "bob"]
    admin_user.spoken.clear()
    host._show_account_approval_menu(admin_user)
    ids = _get_menu_ids(admin_user)
    assert ids == ["pending_alice", "pending_bob", "back"]
    assert host._user_states["admin"]["menu"] == "account_approval_menu"


def test_virtual_bots_menu_shows_status_and_updates_state():
    host = AdminHost()
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)

    class VirtualBotManager:
        def get_status(self):
            return {"online": 2, "total": 4}

    host._virtual_bots = VirtualBotManager()
    host._show_virtual_bots_menu(owner_user)
    items = owner_user.menus[-1]["items"]
    assert items[0].id == "fill"
    assert "(2/4)" in items[0].text
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


def test_show_promote_admin_menu_handles_empty_and_entries():
    db = DummyDB()
    host = AdminHost(db=db)
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_promote_admin_menu(owner_user)
    assert owner_user.spoken[-1][0] == "no-users-to-promote"
    assert host._user_states["owner"]["menu"] == "admin_menu"

    db.non_admin_users = ["alice"]
    owner_user.spoken.clear()
    host._show_promote_admin_menu(owner_user)
    assert owner_user.menus[-1]["menu_id"] == "promote_admin_menu"
    assert _get_menu_ids(owner_user) == ["promote_alice", "back"]


def test_show_demote_admin_menu_filters_self_and_empty():
    db = DummyDB()
    host = AdminHost(db=db)
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_demote_admin_menu(owner_user)
    assert owner_user.spoken[-1][0] == "no-admins-to-demote"
    assert host._user_states["owner"]["menu"] == "admin_menu"

    db.admin_users = ["owner", "eve"]
    owner_user.spoken.clear()
    host._show_demote_admin_menu(owner_user)
    assert owner_user.menus[-1]["menu_id"] == "demote_admin_menu"
    assert _get_menu_ids(owner_user) == ["demote_eve", "back"]


def test_show_reset_password_user_menu_handles_empty_and_entries():
    db = DummyDB()
    host = AdminHost(db=db)
    admin_user = DummyUser("admin", TrustLevel.ADMIN)

    host._show_reset_password_user_menu(admin_user)
    assert admin_user.spoken[-1][0] == "no-users-to-reset-password"
    assert host._user_states["admin"]["menu"] == "admin_menu"

    db.non_admin_users = ["alice"]
    admin_user.spoken.clear()
    host._show_reset_password_user_menu(admin_user)
    assert admin_user.menus[-1]["menu_id"] == "reset_password_user_menu"
    assert _get_menu_ids(admin_user) == ["reset_password_alice", "back"]


@pytest.mark.asyncio
async def test_handle_account_approval_selection_routes(monkeypatch):
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    calls = []

    host._show_admin_menu = types.MethodType(
        lambda self, user: calls.append(("admin", user.username)), host
    )
    host._show_pending_user_actions_menu = types.MethodType(
        lambda self, user, pending: calls.append(("pending", pending)), host
    )

    await host._handle_account_approval_selection(admin_user, "back")
    await host._handle_account_approval_selection(admin_user, "pending_alice")

    assert calls == [("admin", "admin"), ("pending", "alice")]


@pytest.mark.asyncio
async def test_handle_reset_password_user_selection_routes():
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    calls = []

    host._show_admin_menu = types.MethodType(
        lambda self, user: calls.append(("admin", user.username)), host
    )
    host._show_reset_password_editbox = types.MethodType(
        lambda self, user, target: calls.append(("editbox", target)), host
    )

    await host._handle_reset_password_user_selection(admin_user, "back")
    await host._handle_reset_password_user_selection(admin_user, "reset_password_alice")

    assert calls == [("admin", "admin"), ("editbox", "alice")]


@pytest.mark.asyncio
async def test_reset_user_password_updates_auth_and_disconnects_online_user():
    db = DummyDB()
    db.non_admin_users = ["alice"]
    host = AdminHost(db=db)
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    target_user = DummyUser("alice", TrustLevel.USER)
    sent = []

    async def send(payload):
        sent.append(payload)

    target_user.connection = SimpleNamespace(send=send)
    target_user.get_queued_messages = lambda: []
    host._users = {"alice": target_user}
    calls = []
    host._auth = SimpleNamespace(
        reset_password=lambda username, password: calls.append((username, password)) or True
    )

    await host._reset_user_password(admin_user, "alice", "new-secret")

    assert calls == [("alice", "new-secret")]
    assert admin_user.spoken[-1][0] == "reset-user-password-done"
    assert target_user.spoken[-1][0] == "your-password-was-reset"
    assert sent[-1]["type"] == "disconnect"
    assert sent[-1]["return_to_login"] is True


@pytest.mark.asyncio
async def test_handle_pending_user_actions_selection_paths(monkeypatch):
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    approvals = []
    declines = []
    backs = []

    async def fake_approve(self, admin, username):
        approvals.append((admin.username, username))

    host._approve_user = types.MethodType(fake_approve, host)
    host._show_decline_reason_editbox = types.MethodType(
        lambda self, user, target: declines.append(target), host
    )
    host._show_account_approval_menu = types.MethodType(
        lambda self, user: backs.append(user.username), host
    )

    state = {"pending_username": "newbie"}
    await host._handle_pending_user_actions_selection(admin_user, "approve", state)
    await host._handle_pending_user_actions_selection(admin_user, "decline", state)
    await host._handle_pending_user_actions_selection(admin_user, "back", state)
    await host._handle_pending_user_actions_selection(admin_user, "approve", {})

    assert approvals == [("admin", "newbie")]
    assert declines == ["newbie"]
    assert backs == ["admin", "admin"]


@pytest.mark.asyncio
async def test_handle_promote_confirm_selection(monkeypatch):
    host = AdminHost()
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)
    calls = []

    host._show_broadcast_choice_menu = types.MethodType(
        lambda self, user, action, target: calls.append((action, target)), host
    )
    host._show_promote_admin_menu = types.MethodType(
        lambda self, user: calls.append(("menu", user.username)), host
    )

    await host._handle_promote_confirm_selection(owner_user, "yes", {"target_username": "bob"})
    await host._handle_promote_confirm_selection(owner_user, "no", {"target_username": "bob"})
    await host._handle_promote_confirm_selection(owner_user, "yes", {})

    assert calls == [("promote", "bob"), ("menu", "owner"), ("menu", "owner")]


@pytest.mark.asyncio
async def test_handle_broadcast_choice_selection_dispatches(monkeypatch):
    host = AdminHost()
    owner_user = DummyUser("owner", TrustLevel.SERVER_OWNER)
    promotions = []
    bans = []
    fallbacks = []

    async def fake_promote(self, user, target, scope):
        promotions.append((scope, target))

    host._promote_to_admin = types.MethodType(fake_promote, host)
    host._show_ban_reason_editbox = types.MethodType(
        lambda self, user, target, scope: bans.append((target, scope)), host
    )
    host._show_admin_menu = types.MethodType(
        lambda self, user: fallbacks.append(user.username), host
    )

    await host._handle_broadcast_choice_selection(
        owner_user,
        "admins",
        {"action": "promote", "target_username": "alice"},
    )
    await host._handle_broadcast_choice_selection(
        owner_user,
        "all",
        {"action": "ban", "target_username": "eve"},
    )
    await host._handle_broadcast_choice_selection(owner_user, "all", {})

    assert promotions == [("admins", "alice")]
    assert bans == [("eve", "all")]
    assert fallbacks == ["owner"]


@pytest.mark.asyncio
async def test_handle_admin_menu_selection_routes_correctly(monkeypatch):
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    called = []

    def tracker(name):
        def _inner(self, user):
            called.append((name, user.username))

        return _inner

    monkeypatch.setattr(
        host,
        "_show_virtual_bots_menu",
        types.MethodType(tracker("virtual"), host),
    )

    await host._handle_admin_menu_selection(admin_user, "virtual_bots")
    assert called == [("virtual", "admin")]


@pytest.mark.asyncio
async def test_admin_menu_reboot_server_routes_to_confirm(monkeypatch):
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    shown = []
    monkeypatch.setattr(
        host,
        "_show_reboot_server_confirm_menu",
        types.MethodType(lambda self, user: shown.append(user.username), host),
    )

    await host._handle_admin_menu_selection(admin_user, "reboot_server")
    assert shown == ["admin"]


@pytest.mark.asyncio
async def test_reboot_confirm_menu_yes_triggers_reboot(monkeypatch):
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    rebooted = []

    async def fake_reboot(self, user):
        rebooted.append(user.username)

    monkeypatch.setattr(host, "_reboot_server", types.MethodType(fake_reboot, host))

    await host._handle_reboot_server_confirm_selection(admin_user, "yes")
    assert rebooted == ["admin"]

    # "no" returns the admin to the main menu instead of rebooting
    await host._handle_reboot_server_confirm_selection(admin_user, "no")
    assert rebooted == ["admin"]
    assert host._user_states["admin"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_reboot_spawn_failure_aborts_safely(monkeypatch):
    """If the deploy helper cannot launch, nothing is disconnected and no
    shutdown is requested -- the admin is simply returned to the admin menu."""
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    shutdowns = []
    host.request_shutdown = lambda: shutdowns.append("shutdown")
    shown = []
    monkeypatch.setattr(
        host,
        "_show_admin_menu",
        types.MethodType(lambda self, user: shown.append(user.username), host),
    )

    # Patch create_subprocess_exec so that proc.wait() returns a non-zero exit
    class FailRun:
        def __init__(self, argv):
            self.argv = argv

        async def wait(self):
            return 3  # non-zero exit code

    async def fake_exec(*args, **kwargs):
        return FailRun(args)

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(
        "server.core.administration.asyncio.sleep", AsyncNoop()
    )

    await host._reboot_server(admin_user)

    assert admin_user.spoken[-1][0] == "server-reboot-failed"
    assert shown == ["admin"]
    assert shutdowns == []


class AsyncNoop:
    async def __call__(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_reboot_spawn_success_disconnects_and_shuts_down(monkeypatch):
    """On successful request_shutdown, all approved players receive an
    auto-reconnect disconnect packet and the server shuts down gracefully."""
    host = AdminHost()
    shutdowns = []
    host.request_shutdown = lambda: shutdowns.append("shutdown")

    class Conn:
        def __init__(self):
            self.sent = []

        async def send(self, payload):
            self.sent.append(payload)

    class Player:
        def __init__(self, username, approved, trust=TrustLevel.ADMIN):
            self.username = username
            self.approved = approved
            self.trust_level = trust
            self.locale = "en"
            self.connection = Conn()

        def speak_l(self, *a, **k):
            pass

        def play_sound(self, *a):
            pass

        def get_queued_messages(self):
            return []

    alice = Player("alice", approved=True)
    bob = Player("bob", approved=False, trust=TrustLevel.USER)
    host._users = {"alice": alice, "bob": bob}

    class OkRun:
        async def wait(self):
            return 0

    async def fake_exec(*args, **kwargs):
        return OkRun()

    monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(
        "server.core.administration.asyncio.sleep", AsyncNoop()
    )

    await host._reboot_server(alice)

    # Only the approved player was sent the reconnect disconnect packet.
    assert len(alice.connection.sent) == 1
    disconnect = alice.connection.sent[0]
    assert disconnect["type"] == "disconnect"
    assert disconnect["reconnect"] is True
    assert disconnect["retry_after"] >= 1
    assert bob.connection.sent == []
    assert shutdowns == ["shutdown"]


def test_show_admin_menu_developer_sees_admin_management_but_not_owner_actions():
    """Developers get promote/demote-admin and virtual bots, but never the
    ownership-change or developer-management actions."""
    host = AdminHost()
    dev_user = DummyUser("dev", TrustLevel.DEVELOPER)

    host._show_admin_menu(dev_user)
    dev_ids = _get_menu_ids(dev_user)
    assert dev_ids == [
        "account_approval",
        "reset_user_password",
        "ban_user",
        "unban_user",
        "server_status",
        "kick_user",
        "reboot_server",
        "freeze_server",
        "promote_admin",
        "demote_admin",
        "virtual_bots",
        "broadcast_announcement",
        "lookup_user",
        "admin_reload_caches",
        "back",
    ]


def test_show_promote_developer_menu_lists_admins():
    db = DummyDB()
    db.admin_users = ["alice", "bob"]
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_promote_developer_menu(owner)
    assert owner.menus[-1]["menu_id"] == "promote_developer_menu"
    assert _get_menu_ids(owner) == ["promote_dev_alice", "promote_dev_bob", "back"]
    assert host._user_states["owner"]["menu"] == "promote_developer_menu"


def test_show_promote_developer_menu_empty_falls_back():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_promote_developer_menu(owner)
    assert owner.spoken[0][0] == "no-admins-to-promote-developer"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


def test_show_demote_developer_menu_lists_developers():
    db = DummyDB()
    db.developers = ["carol"]
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_demote_developer_menu(owner)
    assert owner.menus[-1]["menu_id"] == "demote_developer_menu"
    assert _get_menu_ids(owner) == ["demote_dev_carol", "back"]


def test_show_demote_developer_menu_empty_falls_back():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_demote_developer_menu(owner)
    assert owner.spoken[0][0] == "no-developers-to-demote"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_handle_promote_developer_selection_routes():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_promote_developer_selection(owner, "promote_dev_alice")
    assert owner.menus[-1]["menu_id"] == "promote_developer_confirm_menu"
    assert host._user_states["owner"]["target_username"] == "alice"

    await host._handle_promote_developer_selection(owner, "back")
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_handle_demote_developer_selection_routes():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_demote_developer_selection(owner, "demote_dev_carol")
    assert owner.menus[-1]["menu_id"] == "demote_developer_confirm_menu"
    assert host._user_states["owner"]["target_username"] == "carol"

    await host._handle_demote_developer_selection(owner, "back")
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_promote_to_developer_sets_level_and_notifies(monkeypatch):
    db = DummyDB()
    db.admin_users = ["alice"]
    db.developers = []
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    updated = []
    monkeypatch.setattr(db, "update_user_trust_level", lambda u, t: updated.append((u, t)))

    await host._promote_to_developer(owner, "alice", "nobody")

    assert updated == [("alice", TrustLevel.DEVELOPER)]
    assert owner.spoken[-1][0] == "promote-developer-announcement"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_promote_to_developer_rejects_non_admin(monkeypatch):
    db = DummyDB()
    db.non_admin_users = ["bob"]
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    updated = []
    monkeypatch.setattr(db, "update_user_trust_level", lambda u, t: updated.append((u, t)))

    await host._promote_to_developer(owner, "bob", "all")

    assert updated == []
    assert owner.spoken[-1][0] == "promote-developer-unavailable"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_demote_from_developer_sets_admin_and_notifies(monkeypatch):
    db = DummyDB()
    db.developers = ["carol"]
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    updated = []
    monkeypatch.setattr(db, "update_user_trust_level", lambda u, t: updated.append((u, t)))

    await host._demote_from_developer(owner, "carol", "nobody")

    assert updated == [("carol", TrustLevel.ADMIN)]
    assert owner.spoken[-1][0] == "demote-developer-announcement"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_demote_from_developer_rejects_non_developer(monkeypatch):
    db = DummyDB()
    db.admin_users = ["alice"]
    host = AdminHost(db=db)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    updated = []
    monkeypatch.setattr(db, "update_user_trust_level", lambda u, t: updated.append((u, t)))

    await host._demote_from_developer(owner, "alice", "all")

    assert updated == []
    assert owner.spoken[-1][0] == "demote-developer-unavailable"
    assert owner.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_developer_cannot_transfer_ownership(monkeypatch):
    """The one action a developer cannot do: change the server owner."""
    host = AdminHost()
    dev_user = DummyUser("dev", TrustLevel.DEVELOPER)
    db = host._db
    monkeypatch.setattr(db, "update_user_trust_level", lambda *a, **k: None)

    await host._transfer_ownership(dev_user, "alice", "all")

    # require_server_owner blocks developers; they land back on the main menu.
    assert host.main_menu_calls == ["dev"]
    assert dev_user.spoken[0][0] == "not-server-owner"


# ==================== Virtual Bot Add/Edit/Delete Flows ====================


class BotManagerStub:
    """Stub manager for the virtual-bot management menu flows."""

    def __init__(self, roster=None, profiles=None):
        self.roster = roster or []
        self.profiles = profiles or ["default", "host"]
        self.added = []
        self.renamed = []
        self.profile_changes = []
        self.removed = []
        self.brought_online = []
        self.taken_offline = []
        self.saved = 0
        self._presence_enabled = False
        self._kill_switch = False
        self._profile_presence = {}

    def get_roster(self):
        return list(self.roster)

    def get_profiles(self):
        return list(self.profiles)

    def is_roster_name(self, name):
        return any(r["name"].lower() == name.lower() for r in self.roster)

    def add_bot(self, name):
        self.added.append(name)
        return True

    def rename_bot(self, old_name, new_name):
        self.renamed.append((old_name, new_name))
        return True

    def set_bot_profile(self, name, profile):
        self.profile_changes.append((name, profile))
        return True

    def remove_bot(self, name):
        self.removed.append(name)
        return True, 0

    def bring_bot_online(self, name):
        self.brought_online.append(name)
        return True

    def take_bot_offline(self, name):
        self.taken_offline.append(name)
        return True

    def save_state(self):
        self.saved += 1

    def get_status(self):
        return {"total": len(self.roster), "online": 0, "offline": 0, "in_game": 0}

    def disconnect_all_bots(self):
        self.disconnected_all = True
        self.saved += 1
        return len(self.roster)

    # --- Presence stub surface ---
    def presence_status(self):
        return {
            "enabled": True,
            "kill_switch": self._kill_switch,
            "in_quiet_hours": False,
            "chats_sent": 3,
            "chats_blocked": 1,
        }

    def set_presence_enabled(self, value):
        self._presence_enabled = value
        self.saved += 1

    def set_profile_presence(self, profile, value):
        self._profile_presence[profile] = value
        self.saved += 1

    def profile_presence_enabled(self, profile):
        return self._profile_presence.get(profile, False)

    def set_presence_kill_switch(self, value):
        self._kill_switch = value
        self.saved += 1


def _roster_entry(name, source="config", profile="default", online=False):
    return {
        "name": name,
        "profile": profile,
        "state": "online_idle" if online else "offline",
        "online": online,
        "source": source,
    }


def test_virtual_bots_menu_includes_management_items():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])

    host._show_virtual_bots_menu(owner)
    ids = _get_menu_ids(owner)
    assert ids == [
        "fill",
        "clear",
        "online",
        "offline",
        "status",
        "guided",
        "groups",
        "profiles",
        "presence",
        "add",
        "edit",
        "delete",
        "back",
    ]


@pytest.mark.asyncio
async def test_add_bot_flow_shows_editbox_and_adds():
    host = AdminHost()
    host._username_min_length = 3
    host._username_max_length = 32
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_selection(owner, "add")
    assert host._user_states["owner"]["menu"] == "bot_name_editbox"

    await host._handle_bot_name_editbox(owner, "NewBot", host._user_states["owner"])
    assert host._virtual_bots.added == ["NewBot"]
    assert owner.spoken[-1][0] == "virtual-bots-added"
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


@pytest.mark.asyncio
async def test_add_bot_name_taken_and_invalid():
    host = AdminHost()
    host._username_min_length = 3
    host._username_max_length = 32
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Taken")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_bot_name_editbox(owner, "taken", {"menu": "bot_name_editbox"})
    assert host._virtual_bots.added == []
    assert owner.spoken[0][0] == "virtual-bots-name-taken"
    assert host._user_states["owner"]["menu"] == "bot_name_editbox"

    owner.spoken.clear()
    await host._handle_bot_name_editbox(owner, "x", {"menu": "bot_name_editbox"})
    assert host._virtual_bots.added == []
    assert owner.spoken[0][0] == "virtual-bots-name-invalid"


@pytest.mark.asyncio
async def test_edit_bot_rename_and_profile_flows():
    host = AdminHost()
    host._username_min_length = 3
    host._username_max_length = 32
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_selection(owner, "edit")
    assert _get_menu_ids(owner) == ["edit_Alpha", "back"]

    await host._handle_edit_bot_selection(owner, "edit_Alpha")
    assert _get_menu_ids(owner) == ["rename", "profile", "back"]

    await host._handle_edit_bot_actions_selection(owner, "rename", {"bot_name": "Alpha"})
    assert host._user_states["owner"]["menu"] == "rename_bot_editbox"
    await host._handle_rename_bot_editbox(owner, "Beta", host._user_states["owner"])
    assert host._virtual_bots.renamed == [("Alpha", "Beta")]
    assert owner.spoken[-1][0] == "virtual-bots-renamed"
    assert host._user_states["owner"]["menu"] == "edit_bot_menu"

    await host._handle_edit_bot_selection(owner, "edit_Alpha")
    await host._handle_edit_bot_actions_selection(owner, "profile", {"bot_name": "Alpha"})
    assert _get_menu_ids(owner) == ["default", "host", "back"]
    await host._handle_bot_profile_selection(owner, "host", {"bot_name": "Alpha"})
    assert host._virtual_bots.profile_changes == [("Alpha", "host")]
    assert owner.spoken[-1][0] == "virtual-bots-profile-changed"


@pytest.mark.asyncio
async def test_rename_bot_same_name_is_noop():
    host = AdminHost()
    host._username_min_length = 3
    host._username_max_length = 32
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_rename_bot_editbox(
        owner, "alpha", {"menu": "rename_bot_editbox", "bot_name": "Alpha"}
    )
    assert host._virtual_bots.renamed == []
    assert host._user_states["owner"]["menu"] == "edit_bot_actions_menu"


@pytest.mark.asyncio
async def test_delete_bot_flow():
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_selection(owner, "delete")
    assert _get_menu_ids(owner) == ["del_Alpha", "back"]

    await host._handle_delete_bot_selection(owner, "del_Alpha")
    assert host._user_states["owner"]["menu"] == "delete_bot_confirm_menu"

    await host._handle_delete_bot_confirm_selection(owner, "yes", host._user_states["owner"])
    assert host._virtual_bots.removed == ["Alpha"]
    assert owner.spoken[-1][0] == "virtual-bots-deleted"
    assert host._user_states["owner"]["menu"] == "delete_bot_menu"


@pytest.mark.asyncio
async def test_edit_and_delete_empty_roster_fall_back():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_selection(owner, "edit")
    assert owner.spoken[-1][0] == "virtual-bots-no-bots"
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"

    owner.spoken.clear()
    await host._handle_virtual_bots_selection(owner, "delete")
    assert owner.spoken[-1][0] == "virtual-bots-no-bots"
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


@pytest.mark.asyncio
async def test_add_virtual_bot_requires_developer():
    host = AdminHost()
    host._username_min_length = 3
    host._username_max_length = 32
    host._virtual_bots = BotManagerStub()
    admin = DummyUser("admin", TrustLevel.ADMIN)

    await host._add_virtual_bot(admin, "HackerBot")
    assert host._virtual_bots.added == []
    assert admin.spoken[0][0] == "not-server-owner"
    assert host.main_menu_calls == ["admin"]

    dev = DummyUser("dev", TrustLevel.DEVELOPER)
    await host._add_virtual_bot(dev, "DevBot")
    assert host._virtual_bots.added == ["DevBot"]


@pytest.mark.asyncio
async def test_fill_virtual_bots_blocked_during_warmup(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: True)

    await host._fill_virtual_bots(owner)

    assert owner.spoken[-1][0] == "virtual-bots-fill-localization-in-progress"
    assert host._virtual_bots.saved == 0
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


@pytest.mark.asyncio
async def test_bring_bot_online_flow_lists_only_offline(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub(
        roster=[_roster_entry("Alpha"), _roster_entry("Beta", online=True)]
    )
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: False)

    # Only offline bots appear in the bring-online list.
    await host._handle_virtual_bots_selection(owner, "online")
    assert _get_menu_ids(owner) == ["online_Alpha", "back"]

    # Selecting an offline bot brings it online.
    await host._handle_bring_bot_online_selection(owner, "online_Alpha")
    assert host._virtual_bots.brought_online == ["Alpha"]
    assert owner.spoken[-1][0] == "virtual-bots-brought-online"
    assert host._user_states["owner"]["menu"] == "bring_online_bot_menu"


@pytest.mark.asyncio
async def test_bring_bot_online_blocked_during_warmup(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: True)

    await host._handle_bring_bot_online_selection(owner, "online_Alpha")

    assert host._virtual_bots.brought_online == []
    assert owner.spoken[-1][0] == "virtual-bots-fill-localization-in-progress"
    assert host._user_states["owner"]["menu"] == "bring_online_bot_menu"


@pytest.mark.asyncio
async def test_take_bot_offline_flow_lists_only_online(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub(
        roster=[_roster_entry("Alpha", online=True), _roster_entry("Beta")]
    )
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: False)

    # Only online bots appear in the take-offline list.
    await host._handle_virtual_bots_selection(owner, "offline")
    assert _get_menu_ids(owner) == ["offline_Alpha", "back"]

    # Selecting an online bot takes it offline.
    await host._handle_take_bot_offline_selection(owner, "offline_Alpha")
    assert host._virtual_bots.taken_offline == ["Alpha"]
    assert owner.spoken[-1][0] == "virtual-bots-taken-offline"
    assert host._user_states["owner"]["menu"] == "take_offline_bot_menu"


@pytest.mark.asyncio
async def test_take_bot_offline_no_online_bots(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: False)

    await host._handle_virtual_bots_selection(owner, "offline")

    assert owner.spoken[-1][0] == "virtual-bots-all-offline"
    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


@pytest.mark.asyncio
async def test_take_bot_offline_blocked_during_warmup(monkeypatch):
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha", online=True)])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    monkeypatch.setattr(administration.Localization, "is_warmup_active", lambda: True)

    await host._handle_take_bot_offline_selection(owner, "offline_Alpha")

    assert host._virtual_bots.taken_offline == []
    assert owner.spoken[-1][0] == "virtual-bots-fill-localization-in-progress"
    assert host._user_states["owner"]["menu"] == "take_offline_bot_menu"


@pytest.mark.asyncio
async def test_take_bot_offline_back_returns_to_virtual_bots_menu():
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha", online=True)])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_take_bot_offline_selection(owner, "back")

    assert host._user_states["owner"]["menu"] == "virtual_bots_menu"


# ==================== Presence menu flows ====================


async def _open_presence_menu(host, owner):
    await host._show_virtual_bots_presence_menu(owner)
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_menu"
    return _get_menu_ids(owner)


@pytest.mark.asyncio
async def test_presence_menu_opens():
    host = AdminHost()
    host._virtual_bots = BotManagerStub(roster=[_roster_entry("Alpha")])
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await _open_presence_menu(host, owner)
    ids = _get_menu_ids(owner)
    assert ids == ["status", "enable", "disable", "kill_switch", "profiles", "back"]


@pytest.mark.asyncio
async def test_presence_menu_enable_flips_flag_and_returns():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_presence_selection(owner, "enable")

    assert host._virtual_bots._presence_enabled is True
    assert "virtual-bots-presence-enabled" in [m[0] for m in owner.spoken]
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_menu"


@pytest.mark.asyncio
async def test_presence_menu_disable_flips_flag_and_returns():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_presence_selection(owner, "disable")

    assert host._virtual_bots._presence_enabled is False
    assert "virtual-bots-presence-disabled" in [m[0] for m in owner.spoken]
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_menu"


@pytest.mark.asyncio
async def test_presence_menu_kill_switch_toggles():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    # Stub starts kill_switch False -> toggle to True (pause)
    await host._handle_virtual_bots_presence_selection(owner, "kill_switch")
    assert host._virtual_bots._kill_switch is True
    assert "virtual-bots-presence-paused" in [m[0] for m in owner.spoken]

    await host._handle_virtual_bots_presence_selection(owner, "kill_switch")
    assert host._virtual_bots._kill_switch is False
    assert "virtual-bots-presence-resumed" in [m[0] for m in owner.spoken]


@pytest.mark.asyncio
async def test_presence_profiles_menu_and_toggle():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._show_virtual_bots_presence_profiles_menu(owner)
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_profiles_menu"
    assert _get_menu_ids(owner) == ["profile_default", "profile_host", "back"]

    # Toggle the "host" profile on
    await host._handle_virtual_bots_presence_profile_selection(owner, "profile_host")
    assert host._virtual_bots._profile_presence.get("host") is True
    assert owner.spoken[-1][0] == "virtual-bots-presence-profile-enabled"
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_profiles_menu"


@pytest.mark.asyncio
async def test_presence_profiles_back_returns_to_presence_menu():
    host = AdminHost()
    host._virtual_bots = BotManagerStub()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_virtual_bots_presence_profile_selection(owner, "back")
    assert host._user_states["owner"]["menu"] == "virtual_bots_presence_menu"


# ==================== Tiered admin actions: status / kick / broadcast / lookup ====================

def test_server_status_menu_shows_readout():
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    host._users = {"admin": admin}
    host._db.non_admin_users = ["alice", "bob"]

    host._show_server_status_menu(admin)
    mu = admin.menus[-1]
    assert mu["menu_id"] == "server_status_menu"
    assert host._user_states["admin"]["menu"] == "server_status_menu"
    assert _get_menu_ids(admin)[-1] == "back"


def test_kick_user_menu_lists_lower_rank_and_excludes_self():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    admin2 = DummyUser("admin2", TrustLevel.ADMIN)
    bob = DummyUser("bob", TrustLevel.USER)
    host._users = {"owner": owner, "admin2": admin2, "bob": bob}

    # Owner can kick users strictly below their rank (users + admins), not self.
    host._show_kick_user_menu(owner)
    assert _get_menu_ids(owner) == ["kick_admin2", "kick_bob", "back"]
    assert host._user_states["owner"]["menu"] == "kick_user_menu"

    # An admin cannot kick other admins/owner, only users below.
    bob_only = DummyUser("admin3", TrustLevel.ADMIN)
    host._users = {"admin3": bob_only, "bob": bob}
    host._show_kick_user_menu(bob_only)
    assert _get_menu_ids(bob_only) == ["kick_bob", "back"]


def test_kick_user_menu_empty_goes_back_to_admin():
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    host._users = {"admin": admin}
    host._show_kick_user_menu(admin)
    assert admin.spoken[-1][0] == "no-users-to-kick"
    assert admin.menus[-1]["menu_id"] == "admin_menu"


@pytest.mark.asyncio
async def test_kick_confirm_disconnects_user():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    bob = DummyUser("bob", TrustLevel.USER)

    class FakeConn:
        def __init__(self):
            self.sent = []
            self.closed = []

        async def send(self, packet):
            self.sent.append(packet)

        async def close(self):
            self.closed.append(True)

    bob.connection = FakeConn()
    host._users = {"owner": owner, "bob": bob}

    await host._handle_kick_confirm_selection(owner, "yes", {"target_username": "bob"})
    assert bob.connection.sent == [{"type": "disconnect", "reconnect": True}]
    assert bob.connection.closed == [True]
    assert owner.spoken[-1][0] == "user-kicked"
    assert host._user_states["owner"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_kick_confirm_no_cancels():
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    await host._handle_kick_confirm_selection(admin, "no", {"target_username": "bob"})
    assert host._user_states["admin"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_broadcast_announcement_sends_to_approved_users_only():
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.DEVELOPER)
    alice = DummyUser("alice", TrustLevel.USER)
    alice.approved = True
    bob = DummyUser("bob", TrustLevel.USER)
    bob.approved = False
    host._users = {"admin": admin, "alice": alice, "bob": bob}

    await host._handle_broadcast_announcement_editbox(admin, "Restart soon", {})

    assert alice.spoken[0][0] == "__raw__"
    assert alice.spoken[0][1]["text"] == "Restart soon"
    assert alice.sounds == ["accountactionnotify.ogg"]
    assert bob.spoken == []
    assert admin.spoken[-1][0] == "broadcast-sent"


@pytest.mark.asyncio
async def test_broadcast_empty_message_rejected():
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.DEVELOPER)
    await host._handle_broadcast_announcement_editbox(admin, "   ", {})
    assert admin.spoken[-1][0] == "broadcast-empty-message"
    assert host._user_states["admin"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_lookup_user_shows_record_and_missing_user():
    db = DummyDB()
    host = AdminHost(db=db)
    admin = DummyUser("admin", TrustLevel.DEVELOPER)
    db.non_admin_users = ["alice"]

    await host._handle_lookup_user_editbox(admin, "alice", {})
    mu = admin.menus[-1]
    assert mu["menu_id"] == "lookup_user_result_menu"
    assert host._user_states["admin"]["menu"] == "lookup_user_result_menu"
    assert _get_menu_ids(admin)[-1] == "back"

    admin.spoken.clear()
    await host._handle_lookup_user_editbox(admin, "nobody", {})
    assert admin.spoken[-1][0] == "user-not-found"
    assert host._user_states["admin"]["menu"] == "admin_menu"


# ==================== Reboot flow with virtual bots ====================

class _BotsWithOnline:
    def __init__(self, online=0, in_game=0):
        self.online = online
        self.in_game = in_game
        self.disconnect_calls = 0

    def get_status(self):
        return {
            "total": self.online + self.in_game,
            "online": self.online,
            "in_game": self.in_game,
            "offline": 0,
        }

    def disconnect_all_bots(self):
        self.disconnect_calls += 1
        return self.online + self.in_game


@pytest.mark.asyncio
async def test_reboot_with_connected_bots_shows_second_confirm(monkeypatch):
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    reboots = []

    async def fake_reboot(_user):
        reboots.append(True)

    monkeypatch.setattr(host, "_reboot_server", fake_reboot)
    host._virtual_bots = _BotsWithOnline(online=2, in_game=1)

    await host._handle_reboot_server_confirm_selection(admin, "yes")
    assert admin.menus[-1]["menu_id"] == "reboot_server_bots_confirm_menu"
    assert reboots == []
    assert host._user_states["admin"]["menu"] == "reboot_server_bots_confirm_menu"


@pytest.mark.asyncio
async def test_reboot_bots_confirm_yes_disconnects_then_reboots(monkeypatch):
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    reboots = []

    async def fake_reboot(_user):
        reboots.append(True)

    monkeypatch.setattr(host, "_reboot_server", fake_reboot)
    host._virtual_bots = _BotsWithOnline(online=2)

    await host._handle_reboot_server_bots_confirm_selection(admin, "yes")
    assert host._virtual_bots.disconnect_calls == 1
    assert reboots == [True]


@pytest.mark.asyncio
async def test_reboot_bots_confirm_no_cancels(monkeypatch):
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    reboots = []

    async def fake_reboot(_user):
        reboots.append(True)

    monkeypatch.setattr(host, "_reboot_server", fake_reboot)
    host._virtual_bots = _BotsWithOnline(online=2)

    await host._handle_reboot_server_bots_confirm_selection(admin, "no")
    assert host._virtual_bots.disconnect_calls == 0
    assert reboots == []
    assert host._user_states["admin"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_reboot_without_bots_skips_warning(monkeypatch):
    host = AdminHost()
    admin = DummyUser("admin", TrustLevel.ADMIN)
    reboots = []

    async def fake_reboot(_user):
        reboots.append(True)

    monkeypatch.setattr(host, "_reboot_server", fake_reboot)
    host._virtual_bots = _BotsWithOnline(online=0, in_game=0)

    await host._handle_reboot_server_confirm_selection(admin, "yes")
    assert reboots == [True]
    assert all(
        m["menu_id"] != "reboot_server_bots_confirm_menu" for m in admin.menus
    )


# ==================== Reload Caches ====================


@pytest.mark.asyncio
async def test_reload_caches_confirm_yes_reloads(monkeypatch):
    host = AdminHost()
    dev = DummyUser("dev", TrustLevel.DEVELOPER)
    reloaded = []

    def fake_reload(force=False):
        reloaded.append(force)
        return 30

    from server.messages import localization as loc_module

    monkeypatch.setattr(loc_module.Localization, "reload", staticmethod(fake_reload))
    loads = []
    monkeypatch.setattr(host._documents, "load", lambda: loads.append(1) or 7)

    await host._handle_reload_caches_confirm_selection(dev, "yes")
    assert reloaded == [True]
    assert loads == [1]
    assert host.warmups == 1
    assert host._user_states["dev"]["menu"] == "admin_menu"


@pytest.mark.asyncio
async def test_reload_caches_confirm_no_cancels(monkeypatch):
    host = AdminHost()
    dev = DummyUser("dev", TrustLevel.DEVELOPER)
    reloaded = []

    def fake_reload(force=False):
        reloaded.append(force)
        return 30

    from server.messages import localization as loc_module

    monkeypatch.setattr(loc_module.Localization, "reload", staticmethod(fake_reload))

    await host._handle_reload_caches_confirm_selection(dev, "no")
    assert reloaded == []
    assert host.warmups == 0


def test_admin_menu_shows_reload_caches_for_developer_only():
    host = AdminHost()
    admin_user = DummyUser("admin", TrustLevel.ADMIN)
    dev_user = DummyUser("dev", TrustLevel.DEVELOPER)

    host._show_admin_menu(admin_user)
    assert "admin_reload_caches" not in _get_menu_ids(admin_user)

    host._show_admin_menu(dev_user)
    assert "admin_reload_caches" in _get_menu_ids(dev_user)


# ==================== Scheduled Actions ====================


def _make_action(action_id=1, action_type="broadcast", repeating=False, enabled=True):
    from datetime import datetime, timedelta, timezone

    from server.core.scheduler import ScheduledAction

    return ScheduledAction(
        id=action_id,
        action_type=action_type,
        payload={"message": "hi"} if action_type == "broadcast" else {},
        run_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        repeat_interval_seconds=600 if repeating else 0,
        enabled=enabled,
        created_by="owner",
    )


def test_scheduled_actions_menu_lists_and_adds():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_scheduled_actions_menu(owner)
    ids = _get_menu_ids(owner)
    assert ids[0] == "_none"
    assert "sa_add" in ids
    assert host._user_states["owner"]["menu"] == "scheduled_actions_menu"

    host._scheduler.actions = [_make_action(1), _make_action(2, "reboot", repeating=True)]
    owner.menus.clear()
    host._show_scheduled_actions_menu(owner)
    ids = _get_menu_ids(owner)
    assert ids == ["sa_1", "sa_2", "sa_add", "back"]


def test_admin_menu_shows_scheduled_actions_for_owner_only():
    host = AdminHost()
    dev = DummyUser("dev", TrustLevel.DEVELOPER)
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    host._show_admin_menu(dev)
    assert "scheduled_actions" not in _get_menu_ids(dev)

    host._show_admin_menu(owner)
    assert "scheduled_actions" in _get_menu_ids(owner)


@pytest.mark.asyncio
async def test_schedule_type_broadcast_flow():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    state = host._user_states.setdefault("owner", {})

    await host._handle_schedule_type_selection(owner, "type_broadcast")
    assert state["schedule_type"] == "broadcast"

    await host._handle_schedule_message_editbox(owner, "Hello all", state)
    assert state["schedule_message"] == "Hello all"

    await host._handle_schedule_when_editbox(owner, "30", state)
    assert state["schedule_minutes"] == 30

    await host._handle_schedule_repeat_editbox(owner, "60", state)
    assert state["schedule_repeat_minutes"] == 60
    assert owner.menus[-1]["menu_id"] == "schedule_confirm_menu"

    await host._handle_schedule_confirm_selection(owner, "yes", state)
    assert len(host._scheduler.created) == 1
    created = host._scheduler.created[0]
    assert created["action_type"] == "broadcast"
    assert created["repeat_interval_seconds"] == 3600
    assert created["payload"]["message"] == "Hello all"
    assert created["created_by"] == "owner"


@pytest.mark.asyncio
async def test_schedule_type_reboot_flow():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    state = host._user_states.setdefault("owner", {})

    await host._handle_schedule_type_selection(owner, "type_reboot")
    assert state["schedule_type"] == "reboot"

    await host._handle_schedule_when_editbox(owner, "10", state)
    await host._handle_schedule_repeat_editbox(owner, "0", state)

    await host._handle_schedule_confirm_selection(owner, "yes", state)
    created = host._scheduler.created[0]
    assert created["action_type"] == "reboot"
    assert created["repeat_interval_seconds"] == 0


@pytest.mark.asyncio
async def test_schedule_invalid_numbers_rejected():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    state = host._user_states.setdefault("owner", {})
    state["schedule_type"] = "broadcast"
    state["schedule_message"] = "hi"

    await host._handle_schedule_when_editbox(owner, "abc", state)
    assert "schedule_minutes" not in state

    await host._handle_schedule_when_editbox(owner, "-5", state)
    assert "schedule_minutes" not in state


@pytest.mark.asyncio
async def test_schedule_empty_message_rejected():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    state = host._user_states.setdefault("owner", {})
    state["schedule_type"] = "broadcast"

    await host._handle_schedule_message_editbox(owner, "   ", state)
    assert "schedule_message" not in state


@pytest.mark.asyncio
async def test_schedule_confirm_no_does_not_create():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    state = host._user_states.setdefault("owner", {})
    state["schedule_type"] = "reboot"
    state["schedule_minutes"] = 5
    state["schedule_repeat_minutes"] = 0

    await host._handle_schedule_confirm_selection(owner, "no", state)
    assert host._scheduler.created == []


@pytest.mark.asyncio
async def test_scheduled_action_toggle_and_delete():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)
    host._scheduler.actions = [_make_action(3, enabled=True)]
    state = host._user_states.setdefault("owner", {"scheduled_action_id": 3})

    await host._handle_scheduled_action_actions_selection(owner, "sa_toggle_3", state)
    assert host._scheduler.toggled == [(3, False)]

    await host._handle_scheduled_action_actions_selection(owner, "sa_delete_3", state)
    assert owner.menus[-1]["menu_id"] == "schedule_delete_confirm_menu"

    await host._handle_schedule_delete_confirm_selection(owner, "yes", state)
    assert host._scheduler.deleted == [3]


@pytest.mark.asyncio
async def test_scheduled_actions_menu_selection_routing():
    host = AdminHost()
    owner = DummyUser("owner", TrustLevel.SERVER_OWNER)

    await host._handle_scheduled_actions_selection(owner, "sa_add")
    assert owner.menus[-1]["menu_id"] == "schedule_type_menu"

    await host._handle_scheduled_actions_selection(owner, "sa_7")
    assert host._user_states["owner"]["scheduled_action_id"] == 7
    assert owner.menus[-1]["menu_id"] == "scheduled_action_actions_menu"

    await host._handle_scheduled_actions_selection(owner, "back")
    assert host._user_states["owner"]["menu"] == "admin_menu"
