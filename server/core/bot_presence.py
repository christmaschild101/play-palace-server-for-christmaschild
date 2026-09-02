"""Virtual bot presence: chat lines, session cadence, and rate limiting.

All behavior is server-side. Bots emit the existing ``chat`` packet shape
(same JSON as ``Server._handle_chat`` broadcasts); no new packet types are
introduced and the desktop client needs no changes. Bots never *receive*
chat — ``VirtualUser.speak`` is a no-op — so echo loops are impossible by
construction.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .virtual_bots import VirtualBotManager

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class PresenceConfig:
    """Presence tuning knobs, loaded from ``[virtual_bots.presence]``."""

    # Master switches (guardrails)
    enabled: bool = False  # global opt-in; per-profile flags refine this
    kill_switch: bool = False  # instant pause of ALL bot chatter, DB-persisted

    # Chat cadence (ticks; server tick is 50ms)
    chat_min_ticks: int = 400  # 20s minimum between any two bot chats (global gap)
    chat_max_ticks: int = 4800  # 4m maximum idle-chatter interval per bot
    idle_chat_chance: float = 0.3  # chance an eligible idle bot chats this window

    # Rate caps (guardrails)
    max_chats_per_bot_per_hour: int = 20
    max_chats_per_minute_global: int = 12
    quiet_hours_start: int = 23  # hour of day (0-23), inclusive
    quiet_hours_end: int = 7  # hour of day (0-23), exclusive
    quiet_multiplier: float = 0.2  # activity multiplier during quiet hours

    # Session cadence shaping: offline bots cluster their logins into short
    # "burst" windows instead of trickling in one at a time. Gated on the
    # global ``enabled`` switch, so nothing changes until presence is opted in.
    # See BotPresenceEngine.should_bot_log_in for the exact mechanics.
    session_shape_enabled: bool = True
    burst_login_chance: float = 0.15  # chance a cycle boundary opens a burst window
    burst_window_ticks: int = 1200  # how long a burst stays open (1 min at 50ms)
    burst_quiet_ticks: int = 12000  # enforced pause between burst windows (10 min)
    hesitation_factor: float = 1.5  # multiplier applied to think-tick jitter
    afk_chance: float = 0.05  # chance an idle bot enters an AFK stretch
    afk_min_ticks: int = 1200  # 1 min minimum AFK
    afk_max_ticks: int = 6000  # 5 min maximum AFK

    # Chat line pools (English defaults; per-profile pools can override)
    chat_lines_greeting: list[str] = field(default_factory=lambda: [
        "morning all",
        "hey everyone",
        "back again",
        "hello o/",
    ])
    chat_lines_ingame: list[str] = field(default_factory=lambda: [
        "nice move",
        "close one",
        "good luck all",
        "this is tense",
    ])
    chat_lines_postgame: list[str] = field(default_factory=lambda: [
        "gg",
        "good game",
        "well played",
        "rematch sometime?",
    ])
    chat_lines_idle: list[str] = field(default_factory=lambda: [
        "anyone up for a game?",
        "quiet in here",
        "brb coffee",
        "table open?",
    ])

    # Player-aware reaction chatter: bots react to humans at their tables.
    # Lines may use the {player} placeholder, substituted before broadcast.
    # Per-profile pool overrides are layered on top of these defaults.
    chat_lines_join: list[str] = field(default_factory=lambda: [
        "hey {player}, welcome to the table",
        "oh nice, {player} joined us",
        "sit down {player}, we were just about to start",
        "welcome {player}",
    ])
    chat_lines_takeover: list[str] = field(default_factory=lambda: [
        "welcome back {player}",
        "ah, {player} returned",
        "good to have you back {player}",
        "{player} rejoined us!",
    ])
    chat_lines_gamestart: list[str] = field(default_factory=lambda: [
        "good luck {player}",
        "let's see what {player}'s got",
        "glhf {player}",
        "play nice {player} :)",
    ])
    chat_lines_gameend: list[str] = field(default_factory=lambda: [
        "gg {player}",
        "nice win {player}",
        "rematch sometime, {player}?",
        "well played {player}",
    ])

    # Minimum gap (ticks) between event-driven reactions at the same table.
    # Guards against chatter storms when tables churn (joins, starts, ends).
    table_event_cooldown_ticks: int = 3000  # 2.5 min at 50ms ticks

    # Per-game line pools: game type -> category -> lines. When a bot chats
    # at a table whose game has a pool here, those lines win over the generic
    # pools above. Categories may use the {player} placeholder like the rest.
    # Per-profile game pool overrides layer on top of these.
    game_pools: dict[str, dict[str, list[str]]] = field(default_factory=dict)


# Category -> PresenceConfig field holding that category's line pool.
# Used to resolve per-profile pool overrides and config defaults alike.
POOL_FIELD_BY_CATEGORY = {
    "greeting": "chat_lines_greeting",
    "ingame": "chat_lines_ingame",
    "postgame": "chat_lines_postgame",
    "idle": "chat_lines_idle",
    "join": "chat_lines_join",
    "takeover": "chat_lines_takeover",
    "gamestart": "chat_lines_gamestart",
    "gameend": "chat_lines_gameend",
}


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


@dataclass
class RateState:
    """Rolling counters enforcing the presence guardrails."""

    # bot name -> list of epoch-hour buckets with counts
    per_bot_hour: dict[str, dict[int, int]] = field(default_factory=dict)
    # epoch-minute -> global count
    global_minute: dict[int, int] = field(default_factory=dict)
    # tick of the last emitted chat (any bot)
    last_chat_tick: int = -10**9
    # bot name -> tick of that bot's last chat
    per_bot_last_tick: dict[str, int] = field(default_factory=dict)
    chats_sent_total: int = 0
    chats_blocked_total: int = 0


class BotPresenceEngine:
    """Decides when virtual bots emit chat, enforcing all guardrails.

    Driven from ``VirtualBotManager.on_tick``. Emission writes the exact
    ``chat`` broadcast packet shape used by ``Server._handle_chat``.
    """

    def __init__(self, manager: "VirtualBotManager", config: PresenceConfig | None = None):
        self._manager = manager
        self._config = config or PresenceConfig()
        self._rate = RateState()
        # bot name -> ticks until its next chatter opportunity
        self._chat_timers: dict[str, int] = {}
        # bot name -> AFK ticks remaining
        self._afk_until: dict[str, int] = {}
        # Session cadence state (burst logins): end tick of the open burst
        # window and the earliest tick a new burst attempt may be made.
        # -1 = no window open / no quiet period in effect.
        self._burst_until_tick: int = -1
        self._burst_quiet_until: int = -1
        self._bursts_opened: int = 0
        # table id -> tick of the last event-driven reaction at that table
        self._table_last_event_tick: dict[str, int] = {}

    # -- config access ------------------------------------------------------

    @property
    def config(self) -> PresenceConfig:
        return self._config

    def set_config(self, config: PresenceConfig) -> None:
        self._config = config

    @property
    def rate_state(self) -> RateState:
        return self._rate

    # -- guardrail checks ----------------------------------------------------

    def _hour_bucket(self, tick: int, ticks_per_hour: int = 72000) -> int:
        """Epoch-ish hour bucket from the server tick counter (50ms ticks)."""
        return tick // max(1, ticks_per_hour)

    def _minute_bucket(self, tick: int, ticks_per_minute: int = 1200) -> int:
        return tick // max(1, ticks_per_minute)

    def _in_quiet_hours(self, hour_of_day: int | None = None) -> bool:
        cfg = self._config
        if hour_of_day is None:
            import datetime

            hour_of_day = datetime.datetime.now().hour
        start, end = cfg.quiet_hours_start, cfg.quiet_hours_end
        if start == end:
            return False
        if start < end:
            return start <= hour_of_day < end
        # wraps midnight (e.g. 23 -> 7)
        return hour_of_day >= start or hour_of_day < end

    def _can_emit(self, bot_name: str, tick: int) -> tuple[bool, str]:
        """All guardrails. Returns (allowed, reason)."""
        cfg = self._config
        rate = self._rate

        if cfg.kill_switch:
            return False, "kill_switch"
        if not cfg.enabled:
            return False, "disabled"

        # Per-profile opt-in
        profile = self._manager.bot_profile(bot_name)
        if not self._manager.profile_presence_enabled(profile):
            return False, "profile_opt_out"

        # Quiet hours suppress chatter entirely
        if self._in_quiet_hours():
            return False, "quiet_hours"

        # Global minimum gap between any two bot chats
        if tick - rate.last_chat_tick < cfg.chat_min_ticks:
            return False, "global_gap"

        # Per-bot gap
        bot_last = rate.per_bot_last_tick.get(bot_name, -10**9)
        if tick - bot_last < cfg.chat_min_ticks:
            return False, "bot_gap"

        # Global per-minute cap
        minute = self._minute_bucket(tick)
        if rate.global_minute.get(minute, 0) >= cfg.max_chats_per_minute_global:
            return False, "global_minute_cap"

        # Per-bot hourly cap
        hour = self._hour_bucket(tick)
        if rate.per_bot_hour.setdefault(bot_name, {}).get(hour, 0) >= cfg.max_chats_per_bot_per_hour:
            return False, "bot_hour_cap"

        return True, "ok"

    def _record_emit(self, bot_name: str, tick: int) -> None:
        cfg = self._config
        rate = self._rate
        hour = self._hour_bucket(tick)
        minute = self._minute_bucket(tick)
        rate.per_bot_hour.setdefault(bot_name, {})[hour] = (
            rate.per_bot_hour.get(bot_name, {}).get(hour, 0) + 1
        )
        rate.global_minute[minute] = rate.global_minute.get(minute, 0) + 1
        rate.last_chat_tick = tick
        rate.per_bot_last_tick[bot_name] = tick
        rate.chats_sent_total += 1
        # Prune old buckets to keep memory bounded
        if len(rate.global_minute) > 120:
            cutoff = minute - 60
            rate.global_minute = {m: c for m, c in rate.global_minute.items() if m >= cutoff}
        if len(rate.per_bot_hour) > 500:
            for name in list(rate.per_bot_hour):
                buckets = rate.per_bot_hour[name]
                if len(buckets) > 48:
                    hcutoff = hour - 48
                    rate.per_bot_hour[name] = {h: c for h, c in buckets.items() if h >= hcutoff}

    # -- chat emission -------------------------------------------------------

    def _chat_packet(self, sender: str, message: str, convo: str = "global") -> dict[str, str]:
        """The exact chat packet shape broadcast by ``Server._handle_chat``."""
        return {
            "type": "chat",
            "convo": convo,
            "sender": sender,
            "message": message,
            "language": "Other",
        }

    def emit_chat(
        self, bot_name: str, category: str, tick: int, game_type: str = "", **vars: str
    ) -> bool:
        """Attempt to emit one chat line for ``bot_name``.

        ``game_type`` selects game-specific lines when configured; ``vars``
        are placeholder substitutions (e.g. ``player=...``) applied to the
        selected line before broadcast. Returns True if emitted. The packet
        is delivered through the manager's broadcast callback (server-side
        only).
        """
        allowed, reason = self._can_emit(bot_name, tick)
        if not allowed:
            self._rate.chats_blocked_total += 1
            return False

        pool = self._pool_for(bot_name, category, game_type)
        if not pool:
            return False
        message = random.choice(pool)  # nosec B311
        if vars:
            message = self._render_line(message, **vars)
        packet = self._chat_packet(bot_name, message)
        delivered = self._manager.broadcast_chat_packet(bot_name, packet)
        if delivered:
            self._record_emit(bot_name, tick)
        return delivered

    @staticmethod
    def _render_line(line: str, **vars: str) -> str:
        """Substitute ``{key}`` placeholders; unknown tokens are left intact."""
        for key, value in vars.items():
            line = line.replace("{" + key + "}", value)
        return line

    def _pool_for(self, bot_name: str, category: str, game_type: str = "") -> list[str]:
        """Resolve the line pool for a category, honoring game and profile overrides.

        Priority: per-profile game pool, config game pool, per-profile generic
        pool, config generic pool. When no ``game_type`` is given, the bot's
        current table (if any) supplies one, so idle chatter is also aware of
        the game being played.
        """
        if not game_type:
            game_type = self._bot_game_type(bot_name)
        if game_type:
            game_pool = self._game_pool_for(bot_name, game_type, category)
            if game_pool:
                return game_pool

        field = POOL_FIELD_BY_CATEGORY.get(category)
        manager = getattr(self, "_manager", None)
        resolver = getattr(manager, "profile_chat_lines", None)
        if resolver is not None:
            try:
                profile_lines = resolver(self._manager.bot_profile(bot_name), category)
            except Exception:  # noqa: BLE001 - a bad pool must never break chatter
                profile_lines = None
            if profile_lines:
                return profile_lines
        if field:
            return getattr(self._config, field, None) or []
        return []

    def _game_pool_for(self, bot_name: str, game_type: str, category: str) -> list[str] | None:
        """Game-specific pool for a category, honoring per-profile overrides."""
        manager = getattr(self, "_manager", None)
        resolver = getattr(manager, "profile_game_chat_lines", None)
        if resolver is not None:
            try:
                profile_lines = resolver(
                    self._manager.bot_profile(bot_name), game_type, category
                )
            except Exception:  # noqa: BLE001 - a bad pool must never break chatter
                profile_lines = None
            if profile_lines:
                return profile_lines
        pools = getattr(self._config, "game_pools", None) or {}
        category_pool = pools.get(game_type)
        if isinstance(category_pool, dict):
            value = category_pool.get(category)
            if isinstance(value, str):
                return [value]
            if isinstance(value, list) and value:
                return [str(line) for line in value]
        return None

    def _bot_game_type(self, bot_name: str) -> str:
        """Game type of the table a bot is currently at, if resolvable."""
        resolver = getattr(self._manager, "bot_game_type", None)
        if resolver is None:
            return ""
        try:
            return resolver(bot_name) or ""
        except Exception:  # noqa: BLE001 - never break chatter on lookup failure
            return ""

    # -- session cadence (burst logins) -------------------------------------

    def should_bot_log_in(self, bot_name: str, tick: int) -> bool:
        """Whether it is a good moment for an offline bot to come online.

        With session shaping on, logins cluster naturally: a burst window
        opens with ``burst_login_chance`` when no window is active (and the
        quiet stretch between attempts has elapsed), every offline bot polled
        while it is open comes online, then a quiet stretch is enforced so a
        single eager bot cannot re-trigger the next burst immediately.

        Returns True when shaping is off, presence is disabled, or the kill
        switch is on, so the manager's login behavior is unchanged in every
        configuration that predates session shaping.
        """
        cfg = self._config
        if not cfg.session_shape_enabled or not cfg.enabled or cfg.kill_switch:
            return True

        if tick <= self._burst_until_tick:
            # Inside an open burst window: come online now.
            return True
        if tick <= self._burst_quiet_until:
            # Quiet stretch between bursts: defer the login.
            return False

        # Cycle boundary: roll for a new burst window.
        if random.random() < cfg.burst_login_chance:  # nosec B311
            self._burst_until_tick = tick + cfg.burst_window_ticks
            self._burst_quiet_until = self._burst_until_tick + cfg.burst_quiet_ticks
            self._bursts_opened += 1
            return True
        self._burst_quiet_until = tick + cfg.burst_quiet_ticks
        return False

    # -- player-aware event reactions --------------------------------------

    def _table_cooldown_ok(self, table_id: str, tick: int) -> bool:
        """True if enough ticks have passed since the last reaction at a table."""
        cooldown = self._config.table_event_cooldown_ticks
        if cooldown <= 0:
            return True
        last = self._table_last_event_tick.get(table_id, -10**9)
        return tick - last >= cooldown

    def _record_table_event(self, table_id: str, tick: int) -> None:
        """Remember that a reaction happened at ``table_id`` on ``tick``."""
        self._table_last_event_tick[table_id] = tick

    def _emit_event(
        self,
        category: str,
        candidates: list[str],
        tick: int,
        game_type: str = "",
        **vars: str,
    ) -> bool:
        """Emit exactly one reaction from a random eligible candidate.

        Candidates are tried in random order until one passes the guardrails;
        if every candidate is blocked the event stays silent. Returns True if
        a reaction was delivered.
        """
        if not candidates:
            return False
        shuffled = list(candidates)
        random.shuffle(shuffled)  # nosec B311
        for bot_name in shuffled:
            if self.emit_chat(bot_name, category, tick, game_type=game_type, **vars):
                return True
        return False

    def _react_to_event(
        self,
        table_id: str,
        category: str,
        candidates: list[str],
        tick: int,
        game_type: str = "",
        **vars: str,
    ) -> bool:
        """Shared guardrail + cooldown wrapper for event-driven reactions."""
        if self._config.kill_switch or not self._config.enabled:
            return False
        if not candidates:
            return False
        if not self._table_cooldown_ok(table_id, tick):
            return False
        if self._emit_event(category, candidates, tick, game_type=game_type, **vars):
            self._record_table_event(table_id, tick)
            return True
        return False

    def on_human_joined_table(
        self,
        table_id: str,
        human_name: str,
        candidates: list[str],
        tick: int,
        game_type: str = "",
    ) -> bool:
        """One bot at the table greets a human who just joined."""
        return self._react_to_event(
            table_id, "join", candidates, tick, game_type=game_type, player=human_name
        )

    def on_human_took_over(
        self,
        table_id: str,
        human_name: str,
        candidates: list[str],
        tick: int,
        game_type: str = "",
    ) -> bool:
        """One bot at the table acknowledges a human taking over a bot seat."""
        return self._react_to_event(
            table_id, "takeover", candidates, tick, game_type=game_type, player=human_name
        )

    def on_game_started(
        self,
        table_id: str,
        human_names: list[str],
        candidates: list[str],
        tick: int,
        game_type: str = "",
    ) -> bool:
        """One bot wishes a human player luck as the game begins."""
        if not human_names:
            return False
        player = random.choice(sorted(human_names))  # nosec B311
        return self._react_to_event(
            table_id, "gamestart", candidates, tick, game_type=game_type, player=player
        )

    def on_game_ended(
        self,
        table_id: str,
        human_names: list[str],
        candidates: list[str],
        tick: int,
        game_type: str = "",
        winner_name: str = "",
    ) -> bool:
        """One bot offers post-game banter naming the real winner.

        ``winner_name`` is the recorded winner from the game result (player or
        team name). When absent (draws, games that don't track one), a random
        human participant is named instead.
        """
        if not human_names:
            return False
        player = winner_name or random.choice(sorted(human_names))  # nosec B311
        return self._react_to_event(
            table_id, "gameend", candidates, tick, game_type=game_type, player=player
        )

    # -- tick integration -----------------------------------------------------

    def on_tick(self, tick: int) -> None:
        """Called once per server tick from the virtual bot manager."""
        if self._config.kill_switch or not self._config.enabled:
            return

        multiplier = self._config.quiet_multiplier if self._in_quiet_hours() else 1.0
        if multiplier < 1.0 and random.random() > multiplier:  # nosec B311
            # Quiet hours: only ~20% of ticks even consider chatter
            return

        for bot_name in self._manager.online_bot_names():
            if bot_name in self._afk_until and self._afk_until[bot_name] > tick:
                continue

            timer = self._chat_timers.get(bot_name)
            if timer is None:
                # Initialize with a randomized window
                self._reset_timer(bot_name, tick)
                continue
            if timer > 0:
                self._chat_timers[bot_name] = timer - 1
                continue

            # Timer expired: maybe chat, maybe AFK, then re-arm
            if random.random() < self._config.afk_chance:  # nosec B311
                self._afk_until[bot_name] = tick + random.randint(  # nosec B311
                    self._config.afk_min_ticks, self._config.afk_max_ticks
                )
            elif random.random() < self._config.idle_chat_chance:  # nosec B311
                category = self._manager.bot_chat_category(bot_name)
                self.emit_chat(bot_name, category, tick)
            self._reset_timer(bot_name, tick)

    def _reset_timer(self, bot_name: str, tick: int) -> None:
        base = random.randint(  # nosec B311
            self._config.chat_min_ticks, self._config.chat_max_ticks
        )
        self._chat_timers[bot_name] = int(base * max(0.1, self._config.hesitation_factor / 1.5))

    # -- event hooks (called from VirtualBotManager lifecycle) -----------------

    def on_bot_online(self, bot_name: str, tick: int) -> None:
        self._reset_timer(bot_name, tick)
        self.emit_chat(bot_name, "greeting", tick)

    def on_bot_offline(self, bot_name: str) -> None:
        self._chat_timers.pop(bot_name, None)
        self._afk_until.pop(bot_name, None)

    # -- admin snapshot ---------------------------------------------------------

    def get_status(self, tick: int | None = None) -> dict[str, Any]:
        cfg = self._config
        shaping: dict[str, Any] = {
            "enabled": cfg.session_shape_enabled,
            "burst_login_chance": cfg.burst_login_chance,
            "burst_window_ticks": cfg.burst_window_ticks,
            "burst_quiet_ticks": cfg.burst_quiet_ticks,
            "bursts_opened": self._bursts_opened,
        }
        if tick is not None:
            shaping["burst_active"] = tick <= self._burst_until_tick
            shaping["quiet_until_tick"] = self._burst_quiet_until
            shaping["burst_until_tick"] = self._burst_until_tick
        return {
            "enabled": cfg.enabled,
            "kill_switch": cfg.kill_switch,
            "quiet_hours": f"{cfg.quiet_hours_start:02d}-{cfg.quiet_hours_end:02d}",
            "in_quiet_hours": self._in_quiet_hours(),
            "max_per_bot_hour": cfg.max_chats_per_bot_per_hour,
            "max_global_minute": cfg.max_chats_per_minute_global,
            "chats_sent": self._rate.chats_sent_total,
            "chats_blocked": self._rate.chats_blocked_total,
            "afk_bots": len(self._afk_until),
            "session_shaping": shaping,
        }
