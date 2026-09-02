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


class PoolAwareManager(StubManager):
    """StubManager that also exposes per-profile chat pool overrides."""

    def __init__(self, pools=None, game_pools=None, **kwargs):
        super().__init__(**kwargs)
        self.pools = pools or {}
        self.game_pools = game_pools or {}

    def profile_chat_lines(self, profile, category):
        return self.pools.get(category)

    def profile_game_chat_lines(self, profile, game_type, category):
        return self.game_pools.get(game_type, {}).get(category)


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


# ---------------------------------------------------------------------------
# Player-aware event chatter (reactions to humans at tables)
# ---------------------------------------------------------------------------


def test_render_line_substitutes_player_placeholder():
    engine = _make_engine()
    assert engine._render_line("hey {player}, welcome", player="Bob") == "hey Bob, welcome"
    # Unknown placeholders are left intact
    assert engine._render_line("untouched {missing}", player="Bob") == "untouched {missing}"


def test_emit_chat_renders_player_placeholder():
    mgr = StubManager()
    engine = _make_engine(manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False
    assert engine.emit_chat("BotA", "join", 1000, player="Bob")
    assert mgr.packets
    assert "{player}" not in mgr.packets[0]["message"]
    assert "Bob" in mgr.packets[0]["message"]


def test_human_joined_table_emits_single_reaction():
    cfg = PresenceConfig(table_event_cooldown_ticks=0)
    mgr = StubManager(online=("BotA", "BotB"))
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    ok = engine.on_human_joined_table("tbl1", "Bob", ["BotA", "BotB"], 1000)
    assert ok is True
    assert len(mgr.chats) == 1  # exactly one bot reacts per event
    assert mgr.chats[0] in ("BotA", "BotB")
    assert "Bob" in mgr.packets[0]["message"]
    assert mgr.packets[0]["sender"] == mgr.chats[0]


def test_event_without_candidates_is_noop():
    cfg = PresenceConfig(table_event_cooldown_ticks=0)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_human_joined_table("tbl1", "Bob", [], 1000) is False
    assert mgr.chats == []


def test_event_hooks_require_humans_for_start_and_end():
    cfg = PresenceConfig(table_event_cooldown_ticks=0)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_game_started("tbl1", [], ["BotA"], 1000) is False
    assert engine.on_game_ended("tbl1", [], ["BotA"], 1010) is False
    assert mgr.chats == []


def test_table_reaction_cooldown():
    cfg = PresenceConfig(
        table_event_cooldown_ticks=100, chat_min_ticks=0
    )
    mgr = StubManager(online=("BotA", "BotB"))
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000) is True
    # Inside the cooldown window: suppressed, no chatter
    assert engine.on_human_joined_table("tbl1", "Carol", ["BotA"], 1099) is False
    assert len(mgr.chats) == 1
    # After the window elapses: allowed again
    assert engine.on_human_joined_table("tbl1", "Carol", ["BotA"], 1100) is True
    assert len(mgr.chats) == 2


def test_event_hooks_respect_master_switch():
    mgr = StubManager()
    engine = _make_engine(manager=mgr, enabled=False)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000) is False
    assert engine.on_game_started("tbl1", ["Bob"], ["BotA"], 1010) is False
    assert mgr.chats == []


def test_game_start_and_end_name_a_human():
    cfg = PresenceConfig(table_event_cooldown_ticks=0, chat_min_ticks=0)
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_game_started("tbl1", ["Alice", "Bob"], ["BotA"], 1000) is True
    assert engine.on_game_ended("tbl1", ["Alice", "Bob"], ["BotA"], 1100) is True
    assert len(mgr.chats) == 2
    assert "Alice" in mgr.packets[0]["message"] or "Bob" in mgr.packets[0]["message"]
    assert "Alice" in mgr.packets[1]["message"] or "Bob" in mgr.packets[1]["message"]


def test_game_end_names_real_winner():
    cfg = PresenceConfig(
        table_event_cooldown_ticks=0,
        chat_min_ticks=0,
        game_pools={"chess": {"gameend": ["gg {player}"]}},
    )
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    ok = engine.on_game_ended(
        "tbl1", ["Alice", "Bob"], ["BotA"], 1000, game_type="chess", winner_name="Bob"
    )
    assert ok is True
    # The recorded winner is named, not a random human participant
    assert mgr.packets[0]["message"] == "gg Bob"


def test_game_end_falls_back_to_human_without_winner():
    cfg = PresenceConfig(
        table_event_cooldown_ticks=0,
        chat_min_ticks=0,
        game_pools={"chess": {"gameend": ["gg {player}"]}},
    )
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    # No winner recorded (draw): a human participant is named
    ok = engine.on_game_ended(
        "tbl1", ["Alice", "Bob"], ["BotA"], 1000, game_type="chess", winner_name=""
    )
    assert ok is True
    assert mgr.packets[0]["message"] in ("gg Alice", "gg Bob")


def test_engine_uses_profile_chat_pool_override():
    cfg = PresenceConfig(table_event_cooldown_ticks=0, chat_min_ticks=0)
    mgr = PoolAwareManager(pools={"join": ["custom {player} line"]})
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    assert engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000) is True
    assert mgr.packets[0]["message"] == "custom Bob line"


# ---------------------------------------------------------------------------
# VirtualBotManager notify wrappers (candidate resolution + delegation)
# ---------------------------------------------------------------------------


class PresenceSpy:
    """Records calls made to the presence engine by the manager wrappers."""

    def __init__(self):
        self.calls = []

    def on_human_joined_table(
        self, table_id, human_name, candidates, tick, game_type="", winner_name=""
    ):
        self.calls.append(("join", table_id, human_name, sorted(candidates), tick, game_type, winner_name))

    def on_human_took_over(
        self, table_id, human_name, candidates, tick, game_type="", winner_name=""
    ):
        self.calls.append(("takeover", table_id, human_name, sorted(candidates), tick, game_type, winner_name))

    def on_game_started(
        self, table_id, human_names, candidates, tick, game_type="", winner_name=""
    ):
        self.calls.append(("started", table_id, sorted(human_names), sorted(candidates), tick, game_type, winner_name))

    def on_game_ended(
        self, table_id, human_names, candidates, tick, game_type="", winner_name=""
    ):
        self.calls.append(
            ("ended", table_id, sorted(human_names), sorted(candidates), tick, game_type, winner_name)
        )


def test_manager_notify_resolves_table_candidates():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._presence = PresenceSpy()
    manager._tick_counter = 7
    manager._bots["BotA"] = VirtualBot(
        "BotA", state=VirtualBotState.IN_GAME, table_id="tbl1"
    )
    # BotB is online but not at the table -> must not be a candidate
    manager._bots["BotB"] = VirtualBot(
        "BotB", state=VirtualBotState.ONLINE_IDLE, table_id=None
    )
    table = SimpleNamespace(table_id="tbl1", game_type="scopa")

    manager.notify_human_joined_table(table, "Bob")
    manager.notify_human_took_over(table, "Carol")
    manager.notify_game_started(table, ["Bob", "Carol"])
    manager.notify_game_ended(table, ["Bob"])

    assert manager._presence.calls == [
        ("join", "tbl1", "Bob", ["BotA"], 7, "scopa", ""),
        ("takeover", "tbl1", "Carol", ["BotA"], 7, "scopa", ""),
        ("started", "tbl1", ["Bob", "Carol"], ["BotA"], 7, "scopa", ""),
        ("ended", "tbl1", ["Bob"], ["BotA"], 7, "scopa", ""),
    ]
    # winner_name is threaded through from the game result
    manager.notify_game_ended(table, ["Bob", "Carol"], winner_name="Carol")
    assert manager._presence.calls[-1] == (
        "ended", "tbl1", ["Bob", "Carol"], ["BotA"], 7, "scopa", "Carol"
    )


def test_manager_notify_noops_without_presence():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._presence = None
    manager._bots["BotA"] = VirtualBot(
        "BotA", state=VirtualBotState.IN_GAME, table_id="tbl1"
    )
    table = SimpleNamespace(table_id="tbl1")
    # Must not raise, and must not require a presence engine
    manager.notify_human_joined_table(table, "Bob")
    manager.notify_human_took_over(table, "Bob")
    manager.notify_game_started(table, ["Bob"])
    manager.notify_game_ended(table, ["Bob"])


def test_manager_notify_game_events_require_humans():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._presence = PresenceSpy()
    manager._bots["BotA"] = VirtualBot(
        "BotA", state=VirtualBotState.IN_GAME, table_id="tbl1"
    )
    table = SimpleNamespace(table_id="tbl1")

    manager.notify_game_started(table, [])
    manager.notify_game_ended(table, [])
    assert manager._presence.calls == []


def test_manager_profile_chat_lines():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._profiles = {
        "default": VirtualBotProfileOverride(name="default"),
        "chatty": VirtualBotProfileOverride(
            name="chatty",
            chat_lines_join=["sup {player}"],
            chat_lines_gamestart="gl {player}",
        ),
    }

    assert manager.profile_chat_lines("chatty", "join") == ["sup {player}"]
    # Single-string TOML values are coerced to lists
    assert manager.profile_chat_lines("chatty", "gamestart") == ["gl {player}"]
    # Unset pools and unknown profiles fall back to the config defaults
    assert manager.profile_chat_lines("chatty", "idle") is None
    assert manager.profile_chat_lines("default", "join") is None
    assert manager.profile_chat_lines("ghost", "join") is None


def test_manager_profile_game_chat_lines():
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._profiles = {
        "default": VirtualBotProfileOverride(name="default"),
        "chatty": VirtualBotProfileOverride(
            name="chatty",
            game_pools={"scopa": {"join": ["profile scopa {player}"]}},
        ),
    }

    assert manager.profile_game_chat_lines("chatty", "scopa", "join") == [
        "profile scopa {player}"
    ]
    assert manager.profile_game_chat_lines("chatty", "chess", "join") is None
    assert manager.profile_game_chat_lines("chatty", "scopa", "gameend") is None
    assert manager.profile_game_chat_lines("default", "scopa", "join") is None


def test_manager_bot_game_type_resolves():
    tables = {
        "tbl1": SimpleNamespace(game_type="scopa"),
        "tbl2": SimpleNamespace(game_type=""),
    }
    server = FakeServer()
    server._tables = SimpleNamespace(get_table=lambda table_id: tables.get(table_id))
    manager = VirtualBotManager(server)
    manager._bots["BotA"] = VirtualBot(
        "BotA", state=VirtualBotState.IN_GAME, table_id="tbl1"
    )
    manager._bots["BotB"] = VirtualBot(
        "BotB", state=VirtualBotState.IN_GAME, table_id="tbl2"
    )
    manager._bots["BotC"] = VirtualBot("BotC", state=VirtualBotState.ONLINE_IDLE)

    assert manager.bot_game_type("BotA") == "scopa"
    assert manager.bot_game_type("BotB") == ""
    assert manager.bot_game_type("BotC") == ""
    assert manager.bot_game_type("Ghost") == ""


def test_load_config_parses_presence_and_profile_game_pools(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [virtual_bots]
        names = ["BotA"]

        [virtual_bots.presence]
        enabled = true

        [virtual_bots.presence.game_pools.scopa]
        join = ["scopa join {player}"]
        gameend = "bella {player}!"

        [virtual_bots.profiles.chatty.game_pools.chess]
        join = "chess line for {player}"
        """
    )

    server = FakeServer()
    manager = VirtualBotManager(server)
    manager.load_config(config_path)

    # Presence-level game pools land on the engine config
    assert manager._presence is not None
    game_pools = manager._presence.config.game_pools
    assert game_pools["scopa"]["join"] == ["scopa join {player}"]
    # Single-string nested lines are accepted and coerced at emit time
    assert game_pools["scopa"]["gameend"] == "bella {player}!"
    # Profile-level game pools are parsed and resolvable
    assert manager.profile_game_chat_lines("chatty", "chess", "join") == [
        "chess line for {player}"
    ]
    assert manager.profile_game_chat_lines("chatty", "scopa", "join") is None


# ---------------------------------------------------------------------------
# Game-specific pools (contextual banter per game type)
# ---------------------------------------------------------------------------


class GameAwareManager(StubManager):
    """StubManager that reports the game a bot is currently playing."""

    def __init__(self, game_by_bot=None, category="idle", **kwargs):
        super().__init__(**kwargs)
        self.game_by_bot = game_by_bot or {}
        self._category = category

    def bot_game_type(self, bot_name):
        return self.game_by_bot.get(bot_name, "")

    def bot_chat_category(self, bot_name):
        return self._category


def test_event_reactions_use_game_specific_pool():
    cfg = PresenceConfig(
        table_event_cooldown_ticks=0,
        game_pools={"scopa": {"join": ["scopa join for {player}"]}},
    )
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    ok = engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000, game_type="scopa")
    assert ok is True
    assert mgr.packets[0]["message"] == "scopa join for Bob"


def test_event_reactions_fall_back_to_generic_without_game_pool():
    cfg = PresenceConfig(
        table_event_cooldown_ticks=0,
        game_pools={"scopa": {"join": ["scopa join for {player}"]}},
    )
    mgr = StubManager()
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    # No pool for chess -> generic join pool, still player-aware
    ok = engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000, game_type="chess")
    assert ok is True
    assert mgr.packets[0]["message"] != "scopa join for Bob"
    assert "Bob" in mgr.packets[0]["message"]


def test_idle_chatter_uses_game_pool_via_table(monkeypatch):
    cfg = PresenceConfig(
        chat_min_ticks=5,
        chat_max_ticks=5,
        afk_chance=0.0,
        idle_chat_chance=1.0,
        game_pools={"scopa": {"ingame": ["scopa banter here"]}},
    )
    mgr = GameAwareManager(
        game_by_bot={"BotA": "scopa"}, category="ingame", online=("BotA",)
    )
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False
    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.0)

    for t in range(1, 60):
        engine.on_tick(t)
    assert mgr.packets
    assert all(packet["message"] == "scopa banter here" for packet in mgr.packets)


def test_engine_uses_profile_game_pool_override():
    cfg = PresenceConfig(table_event_cooldown_ticks=0, chat_min_ticks=0)
    mgr = PoolAwareManager(game_pools={"scopa": {"join": ["profile scopa {player}"]}})
    engine = _make_engine(config=cfg, manager=mgr)
    engine._in_quiet_hours = lambda *a, **k: False

    ok = engine.on_human_joined_table("tbl1", "Bob", ["BotA"], 1000, game_type="scopa")
    assert ok is True
    assert mgr.packets[0]["message"] == "profile scopa Bob"


# ---------------------------------------------------------------------------
# Session cadence (burst logins)
# ---------------------------------------------------------------------------


def test_session_shaping_off_when_presence_disabled():
    engine = _make_engine(enabled=False)
    assert engine.should_bot_log_in("BotA", 1000) is True


def test_session_shaping_disabled_admits():
    cfg = PresenceConfig(session_shape_enabled=False)
    engine = _make_engine(config=cfg)
    assert engine.should_bot_log_in("BotA", 1000) is True


def test_kill_switch_does_not_shape_logins():
    engine = _make_engine(kill_switch=True)
    assert engine.should_bot_log_in("BotA", 1000) is True


def test_burst_window_opens_and_admits_cluster(monkeypatch):
    cfg = PresenceConfig(
        burst_login_chance=0.5, burst_window_ticks=100, burst_quiet_ticks=1000
    )
    engine = _make_engine(config=cfg)

    # Cycle boundary: successful roll opens a window and logs this bot in.
    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.0)
    assert engine.should_bot_log_in("BotA", 1000) is True
    assert engine._burst_until_tick == 1100
    # A second bot polled while the window is open joins the burst.
    assert engine.should_bot_log_in("BotB", 1050) is True

    # Window closed: the enforced quiet stretch defers logins.
    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.9)
    assert engine.should_bot_log_in("BotC", 1101) is False
    assert engine.should_bot_log_in("BotD", 1500) is False

    # Quiet expired: the next boundary rolls again and can open a fresh burst.
    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.0)
    assert engine.should_bot_log_in("BotE", 2101) is True
    assert engine._burst_until_tick == 2201


def test_failed_roll_enters_quiet(monkeypatch):
    cfg = PresenceConfig(
        burst_login_chance=0.5, burst_window_ticks=100, burst_quiet_ticks=1000
    )
    engine = _make_engine(config=cfg)

    monkeypatch.setattr("server.core.bot_presence.random.random", lambda: 0.9)
    assert engine.should_bot_log_in("BotA", 1000) is False
    assert engine._burst_until_tick == -1  # no window opened
    assert engine._burst_quiet_until == 2000
    # The pause applies to every other poller too.
    assert engine.should_bot_log_in("BotB", 1500) is False


def test_get_status_reports_session_shaping():
    engine = _make_engine()
    status = engine.get_status(tick=1000)
    shaping = status["session_shaping"]
    assert shaping["enabled"] is True
    assert shaping["bursts_opened"] == 0
    assert shaping["burst_active"] is False
    # Live fields are omitted when no tick is supplied.
    assert "burst_active" not in engine.get_status()["session_shaping"]


def test_process_offline_bot_defers_when_presence_blocks(monkeypatch):
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._presence = SimpleNamespace(should_bot_log_in=lambda name, tick: False)
    bot = VirtualBot("BotA", state=VirtualBotState.OFFLINE)
    manager._bots["BotA"] = bot
    monkeypatch.setattr("server.core.virtual_bots.random.randint", lambda a, b: a)

    manager._process_offline_bot(bot)

    assert bot.state == VirtualBotState.OFFLINE
    assert bot.cooldown_ticks == manager._config.min_offline_ticks


def test_process_offline_bot_brings_online_when_presence_allows(monkeypatch):
    server = FakeServer()
    manager = VirtualBotManager(server)
    manager._presence = SimpleNamespace(should_bot_log_in=lambda name, tick: True)
    bot = VirtualBot("BotA", state=VirtualBotState.OFFLINE)
    manager._bots["BotA"] = bot
    brought = {}

    def fake_bring(online_bot):
        brought["bot"] = online_bot
        online_bot.state = VirtualBotState.ONLINE_IDLE

    monkeypatch.setattr(manager, "_bring_bot_online", fake_bring)

    manager._process_offline_bot(bot)

    assert brought["bot"] is bot
    assert bot.state == VirtualBotState.ONLINE_IDLE


def test_load_config_parses_session_cadence(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
        [virtual_bots]
        names = ["BotA"]

        [virtual_bots.presence]
        enabled = true
        burst_login_chance = 0.4
        burst_window_ticks = 50
        burst_quiet_ticks = 500
        """
    )

    server = FakeServer()
    manager = VirtualBotManager(server)
    manager.load_config(config_path)

    cfg = manager._presence.config
    assert cfg.burst_login_chance == 0.4
    assert cfg.burst_window_ticks == 50
    assert cfg.burst_quiet_ticks == 500