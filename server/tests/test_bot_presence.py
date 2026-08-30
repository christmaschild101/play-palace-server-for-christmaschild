"""Tests for the BotPresenceEngine: rate limits, opt-in, and chat emission."""

from types import SimpleNamespace

import pytest

from server.core.bot_presence import BotPresenceEngine, PresenceConfig
from server.core.virtual_bots import (
    VirtualBot,
    VirtualBotManager,
    VirtualBotProfileOverride,
    VirtualBotState,
)


class FakeServer:
    def __init__(self, db=None):
        self._db = db
        self._users = {}
        self.delivered = {}

    def _iter_approved_users(self):
        for name, user in self._users.items():
            if getattr(user, "approved", True):
                yield name, user


class FakeConn:
    def __init__(self, store, owner):
        self.store = store
        self.owner = owner

    def send(self, packet):
        self.store[self.owner] = packet


class StubManager:
    """Tiny stand-in for the slots the engine needs from VirtualBotManager."""

    def __init__(self, enabled_profiles=("default",), online=("BotA",)):
        self._enabled = enabled_profiles
        self._online = online
        self.packets = []
        self.chats = []

    def bot_profile(self, bot_name):
        return "default"

    def profile_presence_enabled(self, profile):
        return profile in self._enabled

    def online_bot_names(self):
        return list(self._online)

    def bot_chat_category(self, bot_name):
        return "idle"

    def broadcast_chat_packet(self, bot_name, packet):
        self.packets.append(packet)
        self.chats.append(bot_name)
        return True


def _make_engine(
    *, config=None, manager=None, kill_switch=False, enabled=True
) -> BotPresenceEngine:
    cfg = config or PresenceConfig()
    cfg.enabled = enabled
    cfg.kill_switch = kill_switch
    if manager is None:
        manager = StubManager()
    return BotPresenceEngine(manager, cfg)


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def test_disabled_global_blocks_emission():
    mgr = StubManager()
    engine = _make_engine(manager=mgr, enabled=False)
    assert not engine.emit_chat("BotA", "idle", 1000)
    assert mgr.chats == []


def test_kill_switch_blocks_emission():
    mgr = StubManager()
    engine = _make_engine(manager=mgr, enabled=True, kill_switch=True)
    assert not engine.emit_chat("BotA", "idle", 1000)
    assert mgr.chats == []


def test_profile_opt_out_blocks_emission():
    mgr = StubManager(enabled_profiles=("other",))
    engine = _make_engine(manager=mgr, enabled=True)
    assert not engine.emit_chat("BotA", "idle", 1000)
    assert mgr.chats == []


def test_profile_opt_in_allows_emission():
    mgr = StubManager(enabled_profiles=("default",))
    engine = _make_engine(manager=mgr, enabled=True)
    assert engine.emit_chat("BotA", "idle", 1000)
    assert mgr.chats == ["BotA"]


def test_global_gap_between_any_two_bot_chats():
    cfg = PresenceConfig(chat_min_ticks=100)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    assert engine.emit_chat("BotA", "idle", 1000)
    # Same tick / too soon -> blocked by global gap
    assert not engine.emit_chat("BotB", "idle", 1090)
    assert len(mgr.chats) == 1
    # After enough ticks, allowed again
    assert engine.emit_chat("BotB", "idle", 1200)
    assert len(mgr.chats) == 2


def test_per_bot_hourly_cap():
    cfg = PresenceConfig(max_chats_per_bot_per_hour=2)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)

    # Same hour bucket, spaced enough to pass the global gap.
    gap = max(1, cfg.chat_min_ticks + 1)
    assert engine.emit_chat("BotA", "idle", 1000)
    assert engine.emit_chat("BotA", "idle", 1000 + gap)
    # Third one hits the per-bot hourly cap.
    assert not engine.emit_chat("BotA", "idle", 1000 + gap * 2)
    assert len(mgr.chats) == 2


def test_global_per_minute_cap():
    cfg = PresenceConfig(max_chats_per_minute_global=1)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    # Two different bots, within the SAME minute bucket (tick//1200) but
    # spaced beyond the gap -> the global per-minute cap limits them.
    assert engine.emit_chat("BotA", "idle", 400)
    assert not engine.emit_chat("BotB", "idle", 900)
    assert len(mgr.chats) == 1


def test_quiet_hours_block_emission():
    cfg = PresenceConfig(chat_min_ticks=0)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    # monkeypatch the hour so we're inside the 23-7 quiet window
    engine._in_quiet_hours = lambda *a, **k: True
    assert not engine.emit_chat("BotA", "idle", 1000)
    assert mgr.chats == []


def test_emitted_packet_shape_matches_server_chat_broadcast():
    mgr = StubManager()
    engine = _make_engine(manager=mgr)
    engine.emit_chat("BotA", "greeting", 5000)
    assert mgr.packets == [
        {
            "type": "chat",
            "convo": "global",
            "sender": "BotA",
            "message": mgr.packets[0]["message"],
            "language": "Other",
        }
    ]


# ---------------------------------------------------------------------------
# Tick loop
# ---------------------------------------------------------------------------


def test_on_tick_emits_when_timer_fires(monkeypatch):
    cfg = PresenceConfig(chat_min_ticks=10, chat_max_ticks=10, afk_chance=0.0)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)

    # Force quiet hours off and make random draw a low value so the idle
    # chat chance branch fires (0.0 < 0.3) rather than the AFK branch.
    engine._in_quiet_hours = lambda *a, **k: False
    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.0)

    # First tick arms the timer, subsequent ticks count down until 0.
    for t in range(1, 60):
        engine.on_tick(t)
    assert mgr.chats  # at least one chat should have fired


# ---------------------------------------------------------------------------
# Admin-facing manager methods (opt-in isolation)
# ---------------------------------------------------------------------------


def test_manager_profile_opt_in_defaults_off(tmp_path, monkeypatch):
    """A profile with presence_enabled unset keeps the global default (off)."""
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._profiles = {"default": VirtualBotProfileOverride(name="default")}
    manager._config.default_profile = "default"

    # Without any explicit presence config, presence must be off.
    assert not manager._config.presence_enabled
    assert not manager.profile_presence_enabled("default")


def test_manager_set_profile_presence_toggles():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._profiles = {"default": VirtualBotProfileOverride(name="default")}
    manager._config.default_profile = "default"

    assert not manager.profile_presence_enabled("default")
    manager.set_profile_presence("default", True)
    assert manager.profile_presence_enabled("default")
    manager.set_profile_presence("default", False)
    assert not manager.profile_presence_enabled("default")


def test_manager_global_presence_flag():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._config.presence_enabled = False
    assert not manager.profile_presence_enabled("default")
    manager.set_presence_enabled(True)
    assert manager.profile_presence_enabled("default")


def test_kill_switch_persists_and_overrides_startup(tmp_path, monkeypatch):
    """The DB kill switch survives restarts and overrides config-file state."""
    from server.persistence.database import Database

    db = Database(str(tmp_path / "test.db"))
    db.connect()
    manager = VirtualBotManager(FakeServer(db=db))

    # Simulate an admin toggling the kill switch
    manager.set_presence_kill_switch(True)
    assert db.load_virtual_bot_presence_state()["kill_switch"] is True

    # A fresh manager reading the same DB should come up with chatter paused
    # even if its config file said enabled.
    manager2 = VirtualBotManager(FakeServer(db=db))
    manager2._load_presence_config({"enabled": True, "kill_switch": False})
    assert manager2._presence is not None
    assert manager2._presence.config.kill_switch is True
    assert db.load_virtual_bot_presence_state()["kill_switch"] is True
    db.close()