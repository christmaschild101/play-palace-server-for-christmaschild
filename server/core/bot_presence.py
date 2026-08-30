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

    # Session cadence shaping
    session_shape_enabled: bool = True
    burst_login_chance: float = 0.15  # chance a bot comes online in a burst window
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

    def emit_chat(self, bot_name: str, category: str, tick: int) -> bool:
        """Attempt to emit one chat line for ``bot_name``.

        Returns True if emitted. The packet is delivered through the
        manager's broadcast callback (server-side only).
        """
        allowed, reason = self._can_emit(bot_name, tick)
        if not allowed:
            self._rate.chats_blocked_total += 1
            return False

        cfg = self._config
        pools = {
            "greeting": cfg.chat_lines_greeting,
            "ingame": cfg.chat_lines_ingame,
            "postgame": cfg.chat_lines_postgame,
            "idle": cfg.chat_lines_idle,
        }
        pool = pools.get(category) or cfg.chat_lines_idle
        if not pool:
            return False
        message = random.choice(pool)  # nosec B311
        packet = self._chat_packet(bot_name, message)
        delivered = self._manager.broadcast_chat_packet(bot_name, packet)
        if delivered:
            self._record_emit(bot_name, tick)
        return delivered

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

    def on_game_start(self, bot_name: str, tick: int) -> None:
        self.emit_chat(bot_name, "ingame", tick)

    def on_game_end(self, bot_name: str, tick: int) -> None:
        self.emit_chat(bot_name, "postgame", tick)

    def on_bot_offline(self, bot_name: str) -> None:
        self._chat_timers.pop(bot_name, None)
        self._afk_until.pop(bot_name, None)

    # -- admin snapshot ---------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        cfg = self._config
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
        }
