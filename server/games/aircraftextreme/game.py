"""Aircraft Extreme Game Implementation for PlayPalace.

An original flight board game for 2-4 pilots on a 6x6 sky map.

Design (accessibility-first, per docs/design/plans/game_development_guide.md):
  - Map: 6x6 grid. Each pilot starts on their own corner runway (NW, NE, SW,
    SE in seat order). A 2x2 thunderstorm block sits in the middle
    (rows 3-4, columns 3-4) and can never be entered.
  - Goal: fly to the opposite corner to bank laps; first pilot to complete
    the target number of laps and land on their own runway wins. If only
    one plane remains flying (every other pilot out of the game), that
    pilot wins by air supremacy.
  - Turn: 2 actions per turn. Actions: Fly (4 directions, costs 1 engine
    power), Fire cannons (range 2 squares, orthogonal + diagonal),
    Barrel roll (dodge the next shot), Climb (restore engine to full),
    Dive into clouds (absorb the next hit). Landing on your runway with
    all laps complete wins immediately, so flying home is automatic.
  - Engine: each pilot has 3 power. Flying costs 1; at 0 the engine is dead
    (no flying, no firing) until the pilot plays Climb, which recharges to
    full. A missed shot costs the shooter 1 power (they have to fly back
    into position, which costs engine too).
  - Thunderstorm: whenever a plane ends a fly action adjacent to the storm
    block, the storm may strike (30% chance) for configurable damage.
  - Being shot down: the plane is destroyed; the pilot respawns on their
    runway when their next turn comes around, with a fresh plane at the
    configured respawn health. If a pilot is shot down three times, they
    are out of the game.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player
from ..registry import register_game
from ...game_utils.actions import Action, ActionSet, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.grid_mixin import GridGameMixin, GridCursor
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

from .options import AircraftExtremeOptions
from .player import AircraftExtremePlayer

# Map geometry
GRID_SIZE = 6
STORM_MIN = 2  # storm block rows/cols 2..3 (0-indexed) => rows 3-4 in speech
STORM_MAX = 3

# Engine / combat constants
MAX_POWER = 3
ACTIONS_PER_TURN = 2
FIRE_RANGE = 2
CANNON_DAMAGE = 2
STORM_CHANCE = 0.3  # nosec B311 - game randomness, not security
HIT_CHANCE = 0.6  # nosec B311
DIRECTIONS = ("north", "south", "west", "east")
DELTAS = {"north": (-1, 0), "south": (1, 0), "west": (0, -1), "east": (0, 1)}
BASES = ("nw", "ne", "sw", "se")
BASE_KEYS = {
    "nw": "aircraftextreme-base-nw",
    "ne": "aircraftextreme-base-ne",
    "sw": "aircraftextreme-base-sw",
    "se": "aircraftextreme-base-se",
}
BASE_CORNERS = {
    "nw": (0, 0),
    "ne": (0, GRID_SIZE - 1),
    "sw": (GRID_SIZE - 1, 0),
    "se": (GRID_SIZE - 1, GRID_SIZE - 1),
}
# A lap is banked by touching the corner opposite your base.
TARGET_CORNERS = {
    "nw": (GRID_SIZE - 1, GRID_SIZE - 1),
    "ne": (GRID_SIZE - 1, 0),
    "sw": (0, GRID_SIZE - 1),
    "se": (0, 0),
}
MAX_DOWNS = 3  # after this many shootdowns a pilot is out of the game
STATUS_KEYS = (
    ("downed", "aircraftextreme-status-downed"),
    ("cloud_shield", "aircraftextreme-status-clouded"),
    ("barrel_roll", "aircraftextreme-status-evasive"),
)


def in_storm(row: int, col: int) -> bool:
    """Whether the given square is inside the thunderstorm block."""
    return STORM_MIN <= row <= STORM_MAX and STORM_MIN <= col <= STORM_MAX


def adjacent_to_storm(row: int, col: int) -> bool:
    """Whether a plane on this square can be struck by the storm."""
    return (
        STORM_MIN - 1 <= row <= STORM_MAX + 1
        and STORM_MIN - 1 <= col <= STORM_MAX + 1
    )


@dataclass
@register_game
class AircraftExtremeGame(GridGameMixin, Game):
    """Aircraft Extreme - flight board game with dogfights and storms."""

    players: list[AircraftExtremePlayer] = field(default_factory=list)
    options: AircraftExtremeOptions = field(default_factory=AircraftExtremeOptions)

    # Game state
    intro_wait_ticks: int = 0
    winner_id: str | None = None
    win_reason: str | None = None
    # Grid mixin serialized state
    grid_rows: int = GRID_SIZE
    grid_cols: int = GRID_SIZE
    grid_cursors: dict[str, GridCursor] = field(default_factory=dict)
    grid_row_labels: list[str] = field(default_factory=lambda: [str(i + 1) for i in range(GRID_SIZE)])
    grid_col_labels: list[str] = field(default_factory=lambda: [chr(ord("A") + i) for i in range(GRID_SIZE)])

    # ==========================================================================
    # Metadata
    # ==========================================================================

    @classmethod
    def get_name(cls) -> str:
        return "Aircraft Extreme"

    @classmethod
    def get_type(cls) -> str:
        return "aircraftextreme"

    @classmethod
    def get_category(cls) -> str:
        return "category-board-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 4

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        return [
            {
                "id": "most_laps",
                "path": "final_laps.{player_name}",
                "aggregate": "max",
                "format": "score",
            },
            {
                "id": "avg_laps",
                "path": "final_laps.{player_name}",
                "aggregate": "avg",
                "format": "avg",
            },
        ]

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> AircraftExtremePlayer:
        """Create a new pilot."""
        return AircraftExtremePlayer(id=player_id, name=name, is_bot=is_bot)

    def prestart_validate(self) -> list[str]:
        """Validate options before the game starts."""
        errors = super().prestart_validate()
        if self.options.respawn_health > self.options.start_health:
            errors.append("aircraftextreme-error-respawn-too-high")
        return errors

    # ==========================================================================
    # Game flow
    # ==========================================================================

    def on_start(self) -> None:
        """Place the planes and start the sortie."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        self.round = 1
        self.winner_id = None
        self.win_reason = None
        self.intro_wait_ticks = 0

        self._team_manager.team_mode = "individual"
        self._team_manager.setup_teams([p.name for p in self.players if not p.is_spectator])

        active = [p for p in self.players if not p.is_spectator]
        for p, base in zip(active, BASES):
            if isinstance(p, AircraftExtremePlayer):
                row, col = BASE_CORNERS[base]
                p.reset_for_game(base, self.options.start_health, row, col)

        self.set_turn_players(active, reset_index=True)
        self._init_grid()

        self.play_music("game_aircraftextreme/mus.ogg")

        self.broadcast_l("aircraftextreme-intro", laps=self.options.laps)
        self.broadcast_l(
            "aircraftextreme-map-briefing",
            size=GRID_SIZE,
            actions=ACTIONS_PER_TURN,
        )
        for p in active:
            user = self.get_user(p)
            if user and isinstance(p, AircraftExtremePlayer):
                user.speak_l(
                    "aircraftextreme-your-base",
                    base=Localization.get(self._player_locale(p), BASE_KEYS[p.base]),
                    laps=self.options.laps,
                )
        self._sync_team_scores()
        self._prepare_turn(self.current_player)

    def on_tick(self) -> None:
        super().on_tick()
        if not self.game_active:
            return
        if self.intro_wait_ticks > 0:
            self.intro_wait_ticks -= 1
            return
        # Bot safety net: a bot out of actions must never strand the turn
        # (e.g. if an action path ever skips end-of-action processing).
        current = self.current_player
        if (
            isinstance(current, AircraftExtremePlayer)
            and current.is_bot
            and not current.downed
            and current.actions_left <= 0
        ):
            self._advance_turn()
            return
        BotHelper.on_tick(self)

    def _prepare_turn(self, player: AircraftExtremePlayer) -> None:
        """Give actions, speak the respawn message if due, announce."""
        if player.downed:
            player.downed = False
            player.row, player.col = BASE_CORNERS[player.base]
            player.health = self.options.respawn_health
            player.power = MAX_POWER
            player.barrel_roll = False
            player.cloud_shield = False
            self.play_sound("game_aircraftextreme/respawn.ogg")
            self.broadcast_l("aircraftextreme-respawn-after-down", player=player.name)
        player.actions_left = ACTIONS_PER_TURN
        if player.is_bot:
            BotHelper.jolt_bot(player, ticks=random.randint(15, 25))  # nosec B311
        self._sync_team_scores()
        self.broadcast_personal_l(
            player,
            "aircraftextreme-your-turn",
            "aircraftextreme-turn-start",
            zone=self._zone_name(player),
            position=self._position_name(player),
            power=player.power,
            health=player.health,
            left=self._actions_left_text(player),
        )
        self.rebuild_all_menus()

    def _advance_turn(self) -> None:
        """Move to the next pilot who is still in the game."""
        if not self.turn_player_ids:
            return
        for _ in range(len(self.turn_player_ids)):
            self.turn_index = (self.turn_index + 1) % len(self.turn_player_ids)
            nxt = self._player_for_turn_index()
            if nxt is not None and not self._is_out(nxt):
                self._prepare_turn(nxt)
                return
        # No active pilot left to take a turn: someone must already have won
        # by air supremacy; if not (spectator-only edge), end the game.
        alive = self._active_pilots()
        if alive:
            self._win(alive[0], "aircraftextreme-last-plane")

    def _player_for_turn_index(self) -> AircraftExtremePlayer | None:
        """Resolve the pilot at the current turn index."""
        if not self.turn_player_ids:
            return None
        pid = self.turn_player_ids[self.turn_index]
        for p in self.players:
            if p.id == pid:
                return p
        return None

    def _end_action(self, player: AircraftExtremePlayer) -> None:
        """Common end-of-action processing."""
        self._sync_team_scores()
        if player.actions_left <= 0:
            self._advance_turn()
        else:
            self.rebuild_all_menus()

    def _is_out(self, player: AircraftExtremePlayer) -> bool:
        """Whether this pilot has been eliminated from the game."""
        return player.downs >= MAX_DOWNS or player.is_spectator

    def _active_pilots(self) -> list[AircraftExtremePlayer]:
        """Pilots still in the game (not eliminated)."""
        return [
            p
            for p in self.players
            if isinstance(p, AircraftExtremePlayer) and not self._is_out(p)
        ]

    # ==========================================================================
    # Map helpers
    # ==========================================================================

    @staticmethod
    def _in_bounds(row: int, col: int) -> bool:
        return 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE

    def _plane_at(self, row: int, col: int) -> AircraftExtremePlayer | None:
        """The active, flying plane on the given square, if any."""
        for p in self._active_pilots():
            if not p.downed and p.row == row and p.col == col:
                return p
        return None

    def _zone_name(self, player: AircraftExtremePlayer) -> str:
        """Localized zone description for a pilot's position."""
        locale = self._player_locale(player)
        if in_storm(player.row, player.col):
            return Localization.get(locale, "aircraftextreme-zone-storm")
        if player.row < STORM_MIN:
            return Localization.get(locale, "aircraftextreme-zone-north")
        if player.row > STORM_MAX:
            return Localization.get(locale, "aircraftextreme-zone-south")
        if player.col < STORM_MIN:
            return Localization.get(locale, "aircraftextreme-zone-west")
        return Localization.get(locale, "aircraftextreme-zone-east")

    def _position_name(self, player: AircraftExtremePlayer) -> str:
        """Localized row/column position string."""
        locale = self._player_locale(player)
        return Localization.get(
            locale, "aircraftextreme-position", row=player.row + 1, col=player.col + 1
        )

    def _player_locale(self, player: Player) -> str:
        user = self.get_user(player)
        return user.locale if user else "en"

    def _actions_left_text(self, player: AircraftExtremePlayer) -> str:
        locale = self._player_locale(player)
        key = (
            "aircraftextreme-actions-one"
            if player.actions_left == 1
            else "aircraftextreme-actions-two"
        )
        return Localization.get(locale, key)

    def _direction_blocked_reason(
        self, player: AircraftExtremePlayer, dr: int, dc: int
    ) -> str | None:
        """Why a fly direction is blocked, or None when clear."""
        row, col = player.row + dr, player.col + dc
        if not self._in_bounds(row, col):
            return "aircraftextreme-fly-blocked-edge"
        if in_storm(row, col):
            return "aircraftextreme-fly-blocked-storm"
        if self._plane_at(row, col) is not None:
            return "aircraftextreme-fly-blocked-occupied"
        return None

    # ==========================================================================
    # Action sets / keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: AircraftExtremePlayer) -> ActionSet:
        """Create the turn action set (grid cells + flight actions)."""
        action_set = ActionSet(name="turn")
        for action in self.build_grid_actions(player):
            action_set.add(action)
        for action in self.build_grid_nav_actions():
            action_set.add(action)
        locale = self._player_locale(player)
        flight_actions = (
            ("fly_north", "aircraftextreme-action-fly-north"),
            ("fly_south", "aircraftextreme-action-fly-south"),
            ("fly_west", "aircraftextreme-action-fly-west"),
            ("fly_east", "aircraftextreme-action-fly-east"),
            ("fire", "aircraftextreme-action-fire"),
            ("barrel_roll", "aircraftextreme-action-barrel-roll"),
            ("climb", "aircraftextreme-action-climb"),
            ("cloud", "aircraftextreme-action-cloud"),
        )
        for action_id, key in flight_actions:
            action_set.add(
                Action(
                    id=action_id,
                    label=Localization.get(locale, key),
                    handler=f"_action_{action_id}",
                    is_enabled="_is_flight_action_enabled",
                    is_hidden="_is_flight_action_hidden",
                )
            )
        return action_set

    def create_standard_action_set(self, player: Player) -> ActionSet:
        """Add status readouts to the standard set."""
        action_set = super().create_standard_action_set(player)
        locale = self._player_locale(player)
        local_actions = [
            Action(
                id="pilot_status",
                label=Localization.get(locale, "aircraftextreme-action-pilot-status"),
                handler="_action_pilot_status",
                is_enabled="_is_status_enabled",
                is_hidden="_is_status_hidden",
            ),
            Action(
                id="sky_status",
                label=Localization.get(locale, "aircraftextreme-action-sky-status"),
                handler="_action_sky_status",
                is_enabled="_is_status_enabled",
                is_hidden="_is_status_hidden",
            ),
        ]
        for action in reversed(local_actions):
            action_set.add(action)
            if action.id in action_set._order:
                action_set._order.remove(action.id)
            action_set._order.insert(0, action.id)
        return action_set

    def setup_keybinds(self) -> None:
        super().setup_keybinds()
        self.define_keybind("f", "Fire cannons", ["fire"], state=KeybindState.ACTIVE)
        self.define_keybind("space", "Pilot status", ["pilot_status"], state=KeybindState.ACTIVE)
        self.define_keybind(
            "c",
            "Sky report",
            ["sky_status"],
            state=KeybindState.ACTIVE,
            include_spectators=True,
        )

    def _is_flight_action_enabled(self, player: Player) -> str | None:
        if self.status != GameStatus.PLAYING:
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if self.current_player != player:
            return "action-not-your-turn"
        if not isinstance(player, AircraftExtremePlayer):
            return "action-not-available"
        if player.downed or self._is_out(player):
            return "aircraftextreme-reason-downed"
        if player.actions_left <= 0:
            return "aircraftextreme-reason-no-actions"
        return None

    def _is_flight_action_hidden(self, player: Player) -> Visibility:
        if self.status != GameStatus.PLAYING:
            return Visibility.HIDDEN
        if player.is_spectator:
            return Visibility.HIDDEN
        if not isinstance(player, AircraftExtremePlayer):
            return Visibility.HIDDEN
        if self.current_player != player or player.downed or self._is_out(player):
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    def _is_status_enabled(self, player: Player) -> str | None:
        if self.status != GameStatus.PLAYING:
            return "action-not-playing"
        return None

    def _is_status_hidden(self, player: Player) -> Visibility:
        return Visibility.HIDDEN

    # ==========================================================================
    # Flying
    # ==========================================================================

    def _action_fly_north(self, player: Player, action_id: str) -> None:
        self._do_fly(player, "north")

    def _action_fly_south(self, player: Player, action_id: str) -> None:
        self._do_fly(player, "south")

    def _action_fly_west(self, player: Player, action_id: str) -> None:
        self._do_fly(player, "west")

    def _action_fly_east(self, player: Player, action_id: str) -> None:
        self._do_fly(player, "east")

    def _do_fly(self, player: Player, direction: str) -> None:
        """Execute a fly action in the given direction."""
        if not isinstance(player, AircraftExtremePlayer) or self.current_player != player:
            return
        if player.actions_left <= 0 or player.downed or self._is_out(player):
            return
        dr, dc = DELTAS[direction]
        blocked = self._direction_blocked_reason(player, dr, dc)
        if blocked:
            user = self.get_user(player)
            if user:
                user.speak_l(blocked)
            return
        if player.power <= 0:
            user = self.get_user(player)
            if user:
                user.speak_l("aircraftextreme-reason-no-power")
            return

        player.power -= 1
        player.row += dr
        player.col += dc
        player.actions_left -= 1
        self.play_sound(f"game_aircraftextreme/fly-{random.randint(1, 3)}.ogg")  # nosec B311
        self.broadcast_personal_l(
            player,
            "aircraftextreme-you-fly",
            "aircraftextreme-flies",
            direction=direction,
            position=self._position_name(player),
            power=player.power,
        )
        if self._check_lap(player):
            # Banked a lap at the far corner: keep playing (fly home next).
            if player.laps >= self.options.laps:
                user = self.get_user(player)
                if user:
                    user.speak_l("aircraftextreme-fly-home")
        self._check_win_by_landing(player)
        if self.winner_id:
            return
        self._storm_check(player)
        if self.winner_id:
            return
        self._end_action(player)

    def _check_lap(self, player: AircraftExtremePlayer) -> bool:
        """Bank a lap when the pilot touches their target corner."""
        target_row, target_col = TARGET_CORNERS[player.base]
        if (player.row, player.col) == (target_row, target_col):
            player.laps += 1
            self.play_sound("game_aircraftextreme/lap.ogg")
            self.broadcast_l(
                "aircraftextreme-lap-complete",
                player=player.name,
                lap=player.laps,
                total=self.options.laps,
            )
            return True
        return False

    def _storm_check(self, player: AircraftExtremePlayer) -> None:
        """Roll a storm strike when the plane ends adjacent to the storm."""
        if not adjacent_to_storm(player.row, player.col) or self.options.storm_damage <= 0:
            return
        if random.random() >= STORM_CHANCE:  # nosec B311
            self.broadcast_l("aircraftextreme-storm-miss", player=player.name)
            return
        self.play_sound("game_aircraftextreme/storm.ogg")
        self._apply_damage(player, self.options.storm_damage, "aircraftextreme-storm-hit", None)

    # ==========================================================================
    # Combat
    # ==========================================================================

    def _action_fire(self, player: Player, action_id: str) -> None:
        """Fire cannons at the nearest plane in range."""
        if not isinstance(player, AircraftExtremePlayer) or self.current_player != player:
            return
        if player.actions_left <= 0 or player.downed or self._is_out(player):
            return
        if self._at_base(player):
            user = self.get_user(player)
            if user:
                user.speak_l("aircraftextreme-fire-own-base")
            return

        target = self._nearest_target(player)
        if target is None:
            user = self.get_user(player)
            if user:
                user.speak_l("aircraftextreme-fire-no-target")
            return

        player.actions_left -= 1
        self.play_sound("game_aircraftextreme/fire.ogg")
        self.broadcast_l("aircraftextreme-fire-at", player=player.name, target=target.name)

        if target.barrel_roll:
            target.barrel_roll = False
            self.broadcast_l(
                "aircraftextreme-fire-miss",
                player=player.name,
                target=target.name,
                power=player.power,
            )
            self._end_action(player)
            return
        if random.random() >= HIT_CHANCE:  # nosec B311
            player.power = max(0, player.power - 1)
            self.broadcast_l(
                "aircraftextreme-fire-miss",
                player=player.name,
                target=target.name,
                power=player.power,
            )
            self._end_action(player)
            return
        if target.cloud_shield:
            target.cloud_shield = False
            self.broadcast_l("aircraftextreme-cloud-shield-used", player=target.name)
            self._end_action(player)
            return
        if self._at_base(target):
            self.broadcast_l("aircraftextreme-fire-target-safe", target=target.name)
            self._end_action(player)
            return

        self._apply_damage(target, CANNON_DAMAGE, "aircraftextreme-fire-hit", player)
        self._end_action(player)

    def _nearest_target(self, player: AircraftExtremePlayer) -> AircraftExtremePlayer | None:
        """Closest valid target within firing range (orthogonal + diagonal)."""
        best = None
        best_dist = FIRE_RANGE + 1
        for p in self._active_pilots():
            if p.id == player.id or p.downed:
                continue
            dist = max(abs(p.row - player.row), abs(p.col - player.col))
            if dist <= FIRE_RANGE and dist < best_dist:
                best = p
                best_dist = dist
        return best

    def _apply_damage(
        self,
        target: AircraftExtremePlayer,
        damage: int,
        hit_key: str,
        attacker: AircraftExtremePlayer | None,
    ) -> None:
        """Apply damage, handling shootdowns and elimination."""
        target.health -= damage
        if attacker is not None:
            self.broadcast_l(
                hit_key,
                player=attacker.name,
                target=target.name,
                damage=damage,
                health=target.health,
            )
        else:
            self.broadcast_l(
                hit_key,
                player=target.name,
                damage=damage,
                health=target.health,
            )
        if target.health <= 0:
            self._shoot_down(target, attacker)

    def _shoot_down(
        self, victim: AircraftExtremePlayer, killer: AircraftExtremePlayer | None
    ) -> None:
        """Destroy the victim's plane; they respawn next turn or are out."""
        victim.health = 0
        victim.downed = True
        victim.downs += 1
        victim.barrel_roll = False
        victim.cloud_shield = False
        self.play_sound("game_aircraftextreme/shotdown.ogg")
        if killer is not None:
            self.broadcast_l("aircraftextreme-shot-down", killer=killer.name, victim=victim.name)
        else:
            self.broadcast_l("aircraftextreme-storm-downed", player=victim.name)
        if self._is_out(victim):
            self.broadcast_l("aircraftextreme-pilot-out", player=victim.name)
        self.rebuild_all_menus()
        self._check_last_plane()

    def _check_last_plane(self) -> None:
        """If only one pilot remains in the game, they win by air supremacy."""
        alive = self._active_pilots()
        if len(alive) == 1:
            self._win(alive[0], "aircraftextreme-last-plane")

    # ==========================================================================
    # Maneuvers
    # ==========================================================================

    def _action_barrel_roll(self, player: Player, action_id: str) -> None:
        """Dodge the next incoming shot."""
        if not self._flight_action_allowed(player):
            return
        player.actions_left -= 1
        player.barrel_roll = True
        self.play_sound("game_aircraftextreme/roll.ogg")
        self.broadcast_l("aircraftextreme-barrel-roll", player=player.name)
        self.broadcast_personal_l(
            player, "aircraftextreme-you-barrel-roll", "aircraftextreme-barrel-roll"
        )
        self._end_action(player)

    def _action_climb(self, player: Player, action_id: str) -> None:
        """Recharge the engine to full power."""
        if not self._flight_action_allowed(player):
            return
        was_full = player.power >= MAX_POWER
        player.actions_left -= 1
        player.power = MAX_POWER
        self.play_sound("game_aircraftextreme/climb.ogg")
        if was_full:
            # Full-power climb: a deliberate holding action. It always
            # consumes the action so pilots and bots can never get stuck.
            user = self.get_user(player)
            if user:
                user.speak_l("aircraftextreme-climb-nothing")
        else:
            self.broadcast_l("aircraftextreme-climb", player=player.name, power=player.power)
            self.broadcast_personal_l(
                player,
                "aircraftextreme-you-climb",
                "aircraftextreme-climb",
                power=player.power,
            )
        self._end_action(player)

    def _action_cloud(self, player: Player, action_id: str) -> None:
        """Absorb the next hit with cloud cover."""
        if not self._flight_action_allowed(player):
            return
        player.actions_left -= 1
        player.cloud_shield = True
        self.play_sound("game_aircraftextreme/cloud.ogg")
        self.broadcast_l("aircraftextreme-cloud-shield", player=player.name)
        self.broadcast_personal_l(
            player, "aircraftextreme-you-cloud", "aircraftextreme-cloud-shield"
        )
        self._end_action(player)

    def _flight_action_allowed(self, player: Player) -> bool:
        """Shared guard for turn actions (no error speech needed there)."""
        return (
            isinstance(player, AircraftExtremePlayer)
            and self.current_player == player
            and player.actions_left > 0
            and not player.downed
            and not self._is_out(player)
            and self.status == GameStatus.PLAYING
        )

    # ==========================================================================
    # Winning
    # ==========================================================================

    def _win(self, winner: AircraftExtremePlayer, reason: str) -> None:
        """Declare a winner and finish the game."""
        if self.winner_id:
            return
        self.winner_id = winner.id
        self.win_reason = reason
        self.play_sound("game_aircraftextreme/win.ogg")
        if reason == "aircraftextreme-last-plane":
            self.broadcast_l(reason, winner=winner.name)
        else:
            self.broadcast_l(reason, player=winner.name, laps=winner.laps)
        for p in self.players:
            user = self.get_user(p)
            if user:
                user.remove_menu("turn_menu")
        self.finish_game()

    def _check_win_by_landing(self, player: AircraftExtremePlayer) -> None:
        """Landing on home runway with all laps banked wins the game."""
        if player.laps < self.options.laps:
            return
        if self._at_base(player):
            self._win(player, "aircraftextreme-winner-laps")

    # ==========================================================================
    # Grid callbacks
    # ==========================================================================

    def get_cell_label(self, row: int, col: int, player: Player, locale: str) -> str:
        """Describe one sky square for speech output."""
        coord = self._grid_cell_coordinate(row, col)
        if in_storm(row, col):
            return Localization.get(locale, "aircraftextreme-cell-storm", coord=coord)
        plane = self._plane_at(row, col)
        if plane is not None:
            return Localization.get(
                locale, "aircraftextreme-cell-plane", coord=coord, plane=plane.name
            )
        return Localization.get(locale, "aircraftextreme-cell-empty", coord=coord)

    def on_grid_select(self, player: Player, row: int, col: int) -> None:
        """Selecting a square speaks its label via the cursor; read-only."""
        cursor = self._get_cursor(player)
        cursor.row, cursor.col = row, col
        user = self.get_user(player)
        if user:
            user.speak(self.get_cell_label(row, col, player, self._player_locale(player)), buffer="game")

    def is_grid_cell_enabled(self, player: Player, row: int, col: int) -> str | None:
        """Any pilot may inspect any square; it never advances the game."""
        if self.status != "playing":
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        return None

    def is_grid_cell_hidden(self, player: Player, row: int, col: int) -> Visibility:
        """Cells stay visible to active pilots between turns (status info)."""
        if self.status != "playing":
            return Visibility.HIDDEN
        if not isinstance(player, AircraftExtremePlayer):
            return Visibility.HIDDEN
        if player.downed or self._is_out(player):
            return Visibility.HIDDEN
        return Visibility.VISIBLE

    # ==========================================================================
    # Status readouts
    # ==========================================================================

    def _status_text(self, player: AircraftExtremePlayer, locale: str) -> str:
        """Localized status flags for one pilot."""
        if player.downed:
            return Localization.get(locale, "aircraftextreme-status-downed")
        if player.power <= 0:
            return Localization.get(locale, "aircraftextreme-status-no-power")
        for attr, key in STATUS_KEYS:
            if getattr(player, attr):
                return Localization.get(locale, key)
        return Localization.get(locale, "aircraftextreme-status-clear")

    def _action_pilot_status(self, player: Player, action_id: str) -> None:
        """Speak the pilot's own position, health, and engine state."""
        if not isinstance(player, AircraftExtremePlayer):
            return
        user = self.get_user(player)
        if not user:
            return
        locale = user.locale
        user.speak_l(
            "aircraftextreme-pilot-status",
            position=self._position_name(player),
            health=player.health,
            power=player.power,
            status=self._status_text(player, locale),
        )

    def _action_sky_status(self, player: Player, action_id: str) -> None:
        """Speak every pilot's position and condition."""
        user = self.get_user(player)
        if not user:
            return
        locale = user.locale
        parts = [Localization.get(locale, "aircraftextreme-sky-status")]
        for p in self.players:
            if not isinstance(p, AircraftExtremePlayer) or self._is_out(p):
                continue
            parts.append(
                Localization.get(
                    locale,
                    "aircraftextreme-sky-line",
                    name=p.name,
                    position=self._position_name(p),
                    health=p.health,
                    status=self._status_text(p, locale),
                )
            )
        parts.append(Localization.get(locale, "aircraftextreme-sky-storms"))
        user.speak(", ".join(parts))

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: AircraftExtremePlayer) -> str | None:
        """Choose the bot's next action (returns an action id or None).

        Returns None only when the bot genuinely has nothing useful to do,
        which lets the turn pass without the bot spamming pointless actions.
        """
        if not isinstance(player, AircraftExtremePlayer):
            return None

        # 1. Restart a dead engine - nothing else is possible.
        if player.power <= 0:
            return "climb"

        # 2. Fly home to win once all laps are banked (landing wins). A pilot
        # respawned on the runway with all laps banked must take off and land
        # again, so they re-arm by flying any clear direction first.
        if self._all_laps_done(player):
            if not self._at_base(player):
                direction = self._first_clear_step(player, BASE_CORNERS[player.base])
                if direction:
                    return f"fly_{direction}"
            else:
                for direction in DIRECTIONS:
                    if self._is_fly_clear(player, direction):
                        return f"fly_{direction}"

        # 3. Attack a target in range when it makes sense to shoot.
        target = self._nearest_target(player)
        if target is not None and self._in_firing_mood(player, target):
            return "fire"

        # 4. Duck into clouds when badly hurt with an enemy nearby.
        if target is not None and player.health <= 3 and not player.cloud_shield:
            return "cloud"

        # 5. Fly toward the goal corner (or toward the leader to hunt).
        goal = self._bot_goal(player)
        direction = self._first_clear_step(player, goal)
        if direction:
            return f"fly_{direction}"

        # 6. When boxed in, guard: clouds first, then barrel roll.
        if not player.cloud_shield:
            return "cloud"
        if not player.barrel_roll:
            return "barrel_roll"
        return "climb"

    def _in_firing_mood(self, player: AircraftExtremePlayer, target: AircraftExtremePlayer) -> bool:
        """Whether the bot prefers shooting over racing right now.

        Bots race by default; they only shoot for a kill, to disrupt a pilot
        who is about to win, or once their own laps are banked. This keeps
        games progressing instead of degenerating into endless firefights.
        """
        if target.health <= CANNON_DAMAGE:
            return True  # finish them off
        if self._all_laps_done(player):
            return True  # laps banked: hunt on the way home
        leader = self._leader()
        if leader is not None and leader.id != player.id and leader.laps >= self.options.laps:
            return target.id == leader.id  # disrupt only the pilot about to win
        return False  # race

    def _leader(self) -> AircraftExtremePlayer | None:
        """The active pilot with the most laps."""
        pilots = self._active_pilots()
        if not pilots:
            return None
        return max(pilots, key=lambda p: p.laps)

    def _bot_goal(self, player: AircraftExtremePlayer) -> tuple[int, int]:
        """Where the bot wants to fly: the far corner, or the leader."""
        leader = self._leader()
        if leader is not None and leader.id != player.id and leader.laps > player.laps:
            return leader.row, leader.col
        target = TARGET_CORNERS[player.base]
        if (player.row, player.col) == target and not self._all_laps_done(player):
            # Already on the target corner: step off so the next lap can be
            # banked by re-entering it.
            step = -1 if target[0] > 0 else 1
            return target[0] + step, target[1]
        return target

    def _all_laps_done(self, player: AircraftExtremePlayer) -> bool:
        return player.laps >= self.options.laps

    def _at_base(self, player: AircraftExtremePlayer) -> bool:
        row, col = BASE_CORNERS[player.base]
        return (player.row, player.col) == (row, col)

    def _is_fly_clear(self, player: AircraftExtremePlayer, direction: str) -> bool:
        dr, dc = DELTAS[direction]
        return self._direction_blocked_reason(player, dr, dc) is None

    def _first_clear_step(
        self, player: AircraftExtremePlayer, target: tuple[int, int]
    ) -> str | None:
        """Pick a clear direction that closes distance to the target square.

        Tries every distance-closing direction in preference order so the
        pilot routes around storms and other planes instead of stalling when
        the single preferred direction is blocked. Falls back to any clear
        direction when nothing makes progress (boxed in beside obstacles).
        """
        for direction in self._directions_toward(player, *target):
            if self._is_fly_clear(player, direction):
                return direction
        for direction in DIRECTIONS:
            if self._is_fly_clear(player, direction):
                return direction
        return None

    def _directions_toward(
        self, player: AircraftExtremePlayer, target_row: int, target_col: int
    ) -> list[str]:
        """Directions that close distance to a square, best first."""
        vertical: list[str] = []
        horizontal: list[str] = []
        if player.row > target_row:
            vertical.append("north")
        if player.row < target_row:
            vertical.append("south")
        if player.col > target_col:
            horizontal.append("west")
        if player.col < target_col:
            horizontal.append("east")
        # Prefer the axis with the larger remaining distance (natural pathing).
        if abs(player.row - target_row) >= abs(player.col - target_col):
            return vertical + horizontal
        return horizontal + vertical

    # ==========================================================================
    # Scores / result
    # ==========================================================================

    def _sync_team_scores(self) -> None:
        """Keep team scores in sync with pilot laps (powers check-scores)."""
        for team in self._team_manager.teams:
            team.total_score = 0
        for p in self.players:
            if p.is_spectator or not isinstance(p, AircraftExtremePlayer):
                continue
            team = self._team_manager.get_team(p.name)
            if team:
                team.total_score = p.laps

    def build_game_result(self) -> GameResult:
        active = [p for p in self.players if not p.is_spectator]
        winner = None
        if self.winner_id:
            winner = self.get_player_by_id(self.winner_id)
        if winner is None and active:
            winner = max(active, key=lambda p: p.laps)
        final_laps = {p.name: p.laps for p in active}
        return GameResult(
            game_type=self.get_type(),
            timestamp=datetime.now().isoformat(),
            duration_ticks=self.sound_scheduler_tick,
            player_results=[
                PlayerResult(
                    player_id=p.id,
                    player_name=p.name,
                    is_bot=p.is_bot,
                    is_virtual_bot=getattr(p, "is_virtual_bot", False),
                )
                for p in active
            ],
            custom_data={
                "winner_name": winner.name if winner else None,
                "win_reason": self.win_reason,
                "final_laps": final_laps,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        lines = [Localization.get(locale, "aircraftextreme-final-standings")]
        final_laps = result.custom_data.get("final_laps", {})
        winner_name = result.custom_data.get("winner_name")
        for name, laps in sorted(final_laps.items(), key=lambda item: item[1], reverse=True):
            marker = " *" if name == winner_name else ""
            health = 0
            for p in self.players:
                if p.name == name:
                    health = max(0, p.health)
            lines.append(
                Localization.get(
                    locale,
                    "aircraftextreme-standings-line",
                    name=name,
                    laps=laps,
                    health=health,
                )
                + marker
            )
        return lines
