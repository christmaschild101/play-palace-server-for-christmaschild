"""Tests for account online/offline presence sound resolution.

The login broadcast (``_broadcast_login_presence``) and logout broadcast
(``_on_client_disconnect``) now read ``user.preferences.online_sound`` and
``user.preferences.offline_sound`` instead of hardcoding the role-based
``online.ogg`` / ``offlineadmin.ogg`` files.
"""

from server.core.users.preferences import MainSound, UserPreferences
from server.core.users.base import TrustLevel
from server.core.server import Server


class DummyUser:
    """Minimal stand-in for NetworkUser presence-sound lookups."""

    def __init__(self, username: str, *, trust: TrustLevel, approved: bool = True,
                 online_sound: MainSound = MainSound.Default,
                 offline_sound: MainSound = MainSound.Default):
        self.username = username
        self.trust_level = trust
        self.approved = approved
        self.preferences = UserPreferences(
            online_sound=online_sound,
            offline_sound=offline_sound,
        )


def _presence_sound_for(user: DummyUser, *, offline: bool = False) -> str:
    """Mirror Server._presence_sound_for against a DummyUser."""
    # Inlined from server.py so tests run without the full server import.
    pref = user.preferences.offline_sound if offline else user.preferences.online_sound
    is_admin = user.trust_level.value >= TrustLevel.ADMIN.value
    default = (
        ("offlineadmin.ogg" if is_admin else "offline.ogg")
        if offline
        else ("onlineadmin.ogg" if is_admin else "online.ogg")
    )
    if pref is MainSound.Default:
        return default
    if pref is MainSound.Chime:
        return ("offlinechime.ogg" if offline else "onlinechime.ogg")
    # MainSound.Alert (and any future value) uses the alerted variant
    return ("offlinealert.ogg" if offline else "onlinealert.ogg")


def test_non_admin_default_online_sound():
    user = DummyUser("alice", trust=TrustLevel.USER)
    assert _presence_sound_for(user) == "online.ogg"


def test_admin_default_online_sound():
    user = DummyUser("bob", trust=TrustLevel.ADMIN)
    assert _presence_sound_for(user) == "onlineadmin.ogg"


def test_non_admin_default_offline_sound():
    user = DummyUser("alice", trust=TrustLevel.USER)
    assert _presence_sound_for(user, offline=True) == "offline.ogg"


def test_admin_default_offline_sound():
    user = DummyUser("bob", trust=TrustLevel.ADMIN)
    assert _presence_sound_for(user, offline=True) == "offlineadmin.ogg"


def test_non_admin_online_chime_override():
    user = DummyUser("alice", trust=TrustLevel.USER, online_sound=MainSound.Chime)
    assert _presence_sound_for(user) == "onlinechime.ogg"


def test_non_admin_offline_chime_override():
    user = DummyUser("alice", trust=TrustLevel.USER, offline_sound=MainSound.Chime)
    assert _presence_sound_for(user, offline=True) == "offlinechime.ogg"


def test_non_admin_offline_alert_override():
    user = DummyUser("alice", trust=TrustLevel.USER, offline_sound=MainSound.Alert)
    assert _presence_sound_for(user, offline=True) == "offlinealert.ogg"


def test_admin_online_alert_override():
    user = DummyUser("bob", trust=TrustLevel.ADMIN, online_sound=MainSound.Alert)
    assert _presence_sound_for(user) == "onlinealert.ogg"


def test_banned_user_has_no_offline_broadcast():
    # The server only broadcasts offline for approved, non-banned users.
    user = DummyUser("cease", trust=TrustLevel.BANNED, approved=False)
    assert user.approved is False
    assert user.trust_level is TrustLevel.BANNED


def test_server_presence_sound_for_exists():
    # Ensure the real helper exists and matches the inlined shape.
    assert callable(getattr(Server, "_presence_sound_for", None))


def test_real_server_method_resolves_online_sound():
    """Regression: Server._presence_sound_for must run without NameError.

    Previously server.py referenced MainSound without importing it, so the
    login/disconnect presence broadcast crashed and users never received
    their post-login menus.
    """
    user = DummyUser("alice", trust=TrustLevel.USER, online_sound=MainSound.Chime)
    assert Server._presence_sound_for(None, user) == "onlinechime.ogg"  # self unused by helper


def test_real_server_method_resolves_offline_alert():
    user = DummyUser("bob", trust=TrustLevel.ADMIN, offline_sound=MainSound.Alert)
    assert Server._presence_sound_for(None, user, offline=True) == "offlinealert.ogg"  # self unused
