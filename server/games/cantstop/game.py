"""
Can't Stop Game Implementation for PlayPalace.

Push-your-luck dice game. Roll four dice, split them into two pairs, and
advance the two matching tracks (2-12) with up to three markers. Bank to
keep your progress or push on; bust and lose it all. First player to
complete the required number of tracks wins.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.options import IntOption, option_field
from ...game_utils.push_your_luck_mixin import PushYourLuckBotMixin
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

TRACKS = list(range(2, 13))  # 11 tracks


@dataclass
class CanTStopPlayer(Player):
    """Player state for Can't Stop."""

    progress: list[int] = field(default_factory=lambda: [0] * 11)  # Banked height per track
    markers: list[int] = field(default_factory=lambda: [0] * 11)  # This turn's extra height
    dice: list[int] = field(default_factory=list)  # Pending roll awaiting a choice
    has_rolled: bool = False  # True once at least one roll was bankable


@dataclass
class CanTStopOptions(GameOptions):
    """Options for Can't Stop."""

    win_tracks: int = option_field(
        IntOption(
            default=3,
            min_val=2,
            max_val=4,
            value_key="tracks",
            label="cantstop-set-win-tracks",
            prompt="cantstop-enter-win-tracks",
            change_msg="cantstop-option-changed-win-tracks",
            description="cantstop-desc-win-tracks",
        )
    )


@dataclass
@register_game
class CanTStopGame(PushYourLuckBotMixin, ActionGuardMixin, Game):
    """Can't Stop push-your-luck dice game."""

    players: list[CanTStopPlayer] = field(default_factory=list)
    options: CanTStopOptions = field(default_factory=CanTStopOptions)
    turn: int = 0
    track_height: int = 3  # Classic: 3 on any track reaches the top

    @classmethod
    def get_name(cls) -> str:
        return "Can't Stop"

    @classmethod
    def get_type(cls) -> str:
        return "cantstop"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 4

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> CanTStopPlayer:
        """Create a new player."""
        return CanTStopPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        self.set_turn_players(self.get_active_players())
        self.turn = 0
        self.play_sound("game_squares/start.ogg")
        self._start_player_turn()

    def get_active_players(self) -> list[CanTStopPlayer]:  # type: ignore[override]
        """Active (non-spectator) players."""
        return [p for p in self.players if not p.is_spectator]

    @property
    def current_player(self) -> "CanTStopPlayer | None":  # type: ignore[override]
        """Current player by turn index."""
        active = self.get_active_players()
        if not active:
            return None
        return active[self.turn % len(active)]

    # ==========================================================================
    # Core logic
    # ==========================================================================

    def _track_index(self, value: int) -> int:
        return value - 2

    def _height(self, player: CanTStopPlayer, value: int) -> int:
        return player.progress[self._track_index(value)] + player.markers[self._track_index(value)]

    def _partitions(self, dice: list[int]) -> list[tuple[int, int]]:
        """The three ways to split four dice into two pairs."""
        results: set[tuple[int, int]] = set()
        for i in (1, 2, 3):
            pair1 = dice[0] + dice[i]
            rest = [d for j, d in enumerate(dice) if j != 0 and j != i]
            pair2 = rest[0] + rest[1]
            results.add(tuple(sorted((pair1, pair2))))
        return sorted(results, key=lambda p: -sum(p))

    def _valid_partitions(self, player: CanTStopPlayer) -> list[tuple[int, int]]:
        """Partitions whose sums can all be advanced (no full tracks, ≤3 markers)."""
        active_markers = sum(1 for v in player.markers if v > 0)
        valid = []
        for pair in self._partitions(player.dice):
            ok = True
            for value in pair:
                height = self._height(player, value)
                if height >= self.track_height:
                    ok = False
                    break
                if player.markers[self._track_index(value)] == 0 and active_markers >= 3:
                    ok = False
                    break
            if ok:
                valid.append(pair)
        return valid

    def _marker_units(self, player: CanTStopPlayer) -> int:
        return sum(player.markers)

    def _winning_tracks(self, player: CanTStopPlayer) -> int:
        return sum(
            1
            for i in range(11)
            if player.progress[i] + player.markers[i] >= self.track_height
        )

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_roll(self, player: Player, action_id: str) -> None:
        """Roll the four dice."""
        cs: CanTStopPlayer = player  # type: ignore
        if cs.dice:
            return

        self.play_standard_dice_roll_sound()
        cs.dice = [random.randint(1, 6) for _ in range(4)]  # nosec B311
        self.broadcast_personal_l(
            player,
            "cantstop-you-rolled",
            "cantstop-rolled",
            dice=", ".join(str(d) for d in cs.dice),
        )

        if not self._valid_partitions(cs):
            # Bust
            self.play_sound("game_pig/lose.ogg")
            self.broadcast_l("cantstop-bust", player=player.name)
            cs.markers = [0] * 11
            cs.dice = []
            cs.has_rolled = False
            self._advance_turn()
            return

        cs.has_rolled = True
        self.rebuild_all_menus()

    def _action_choose(self, player: Player, input_value: str, action_id: str) -> None:
        """Advance the two tracks from the chosen partition."""
        cs: CanTStopPlayer = player  # type: ignore
        if not cs.dice:
            return
        try:
            sums = tuple(sorted((int(x) for x in input_value.split("+")), reverse=True))
        except ValueError:
            return
        if sums not in self._valid_partitions(cs):
            return

        for value in sums:
            cs.markers[self._track_index(value)] += 1
            if self._height(cs, value) >= self.track_height:
                self.play_sound("game_farkle/takepoint.ogg")
                self.broadcast_l("cantstop-top", player=player.name, value=value)

        self.play_sound("game_squares/token1.ogg")
        self.broadcast_l(
            "cantstop-advanced",
            player=player.name,
            values=", ".join(str(v) for v in sums),
        )
        cs.dice = []

        if self._winning_tracks(cs) >= self.options.win_tracks:
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l(
                "cantstop-winner",
                player=player.name,
                tracks=self._winning_tracks(cs),
            )
            self.finish_game()
            return

        self.rebuild_all_menus()

    def _action_bank(self, player: Player, action_id: str) -> None:
        """Bank the markers into permanent progress."""
        cs: CanTStopPlayer = player  # type: ignore
        if not cs.has_rolled:
            return
        for i in range(11):
            cs.progress[i] = min(self.track_height, cs.progress[i] + cs.markers[i])
        self.play_sound("game_farkle/bank1.ogg")
        self.broadcast_l(
            "cantstop-banked",
            player=player.name,
            progress=", ".join(
                str(TRACKS[i]) for i in range(11) if cs.progress[i] > 0
            ),
        )
        cs.markers = [0] * 11
        cs.dice = []
        cs.has_rolled = False
        self._advance_turn()

    def _start_player_turn(self) -> None:
        """Initialize the current player's turn."""
        player = self.current_player
        if not player:
            return
        if player.is_bot:
            self.prepare_push_bot_turn(player)
        self.announce_turn()
        self.rebuild_all_menus()

    def _advance_turn(self) -> None:
        self.turn += 1
        self._start_player_turn()

    def end_turn(self) -> None:
        """Base end_turn unused; turns advance through _advance_turn."""
        self._advance_turn()

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_roll_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        cs: CanTStopPlayer = player  # type: ignore
        if cs.dice:
            return "cantstop-choose-first"
        return None

    def _is_roll_hidden(self, player: Player) -> Visibility:
        cs: CanTStopPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=not cs.dice)

    def _is_choose_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        cs: CanTStopPlayer = player  # type: ignore
        if not cs.dice:
            return "cantstop-roll-first"
        if not self._valid_partitions(cs):
            return "cantstop-no-partition"
        return None

    def _is_choose_hidden(self, player: Player) -> Visibility:
        cs: CanTStopPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=bool(cs.dice))

    def _is_bank_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        cs: CanTStopPlayer = player  # type: ignore
        if not cs.has_rolled:
            return "cantstop-roll-first"
        return None

    def _is_bank_hidden(self, player: Player) -> Visibility:
        cs: CanTStopPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=cs.has_rolled)

    def _get_bank_label(self, player: Player, action_id: str) -> str:
        cs: CanTStopPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        tracks = ", ".join(str(TRACKS[i]) for i in range(11) if cs.markers[i] > 0)
        return Localization.get(locale, "cantstop-bank", tracks=tracks or "-")

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _partition_options(self, player: Player) -> list[str]:
        cs: CanTStopPlayer = player  # type: ignore
        return ["+".join(str(v) for v in pair) for pair in self._valid_partitions(cs)]

    def _partition_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "cantstop-partition", sums=option)

    def _bot_select_partition(self, player: Player, options: list[str]) -> str | None:
        """Bot prefers partitions that top a track, then central tracks."""
        cs: CanTStopPlayer = player  # type: ignore
        best: list[str] = []
        best_score = -1
        for opt in options:
            sums = [int(x) for x in opt.split("+")]
            score = 0
            for value in sums:
                height = self._height(cs, value)
                if height + 1 >= self.track_height:
                    score += 30
                if value in (6, 7, 8):
                    score += 5
                elif value in (5, 9):
                    score += 3
                score += 1
            score += random.randint(0, 3)  # nosec B311
            if score > best_score:
                best_score = score
                best = [opt]
            elif score == best_score:
                best.append(opt)
        return random.choice(best) if best else (options[0] if options else None)

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: CanTStopPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "cantstop-roll"),
                handler="_action_roll",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_roll_hidden",
            )
        )
        action_set.add(
            Action(
                id="choose",
                label=Localization.get(locale, "cantstop-choose"),
                handler="_action_choose",
                is_enabled="_is_choose_enabled",
                is_hidden="_is_choose_hidden",
                input_request=MenuInput(
                    prompt="cantstop-pick-partition",
                    options="_partition_options",
                    option_label="_partition_option_label",
                    bot_select="_bot_select_partition",
                ),
            )
        )
        action_set.add(
            Action(
                id="bank",
                label=Localization.get(locale, "cantstop-bank", tracks="-"),
                handler="_action_bank",
                is_enabled="_is_bank_enabled",
                is_hidden="_is_bank_hidden",
                get_label="_get_bank_label",
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("r", "Roll dice", ["roll"], state=KeybindState.ACTIVE)
        self.define_keybind("b", "Bank progress", ["bank"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def _calculate_push_bot_target(self, player: CanTStopPlayer) -> int:
        """Bank once markers total at least this many units (game-aware)."""
        # Classic strategy: bank fairly early unless behind
        leaders = [p for p in self.get_active_players() if p is not player]
        best_progress = max((sum(p.progress) for p in leaders), default=0)
        my_progress = sum(player.progress)
        base = random.randint(5, 7)  # nosec B311
        if best_progress >= my_progress + 3:
            return base + 3  # Push harder when behind
        if my_progress >= best_progress + 3:
            return max(3, base - 2)  # Relax a little when ahead
        return base

    def bot_think(self, player: CanTStopPlayer) -> str | None:
        """Bot AI: choose, bank, or push on."""
        if player.dice:
            return "choose"
        target = BotHelper.get_target(player)
        if player.has_rolled and target is not None and self._marker_units(player) >= target:
            return "bank"
        return "roll"

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        progress = {p.name: sum(p.progress) for p in self.get_active_players()}
        winner_name = max(progress, key=progress.get) if progress else None

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
                for p in self.get_active_players()
            ],
            custom_data={
                "winner_name": winner_name,
                "final_progress": progress,
                "win_tracks": self.options.win_tracks,
                "track_height": self.track_height,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_progress = result.custom_data.get("final_progress", {})
        for name, steps in sorted(final_progress.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "cantstop-score-line", player=name, steps=steps))
        return lines


__all__ = ["CanTStopGame", "CanTStopPlayer", "CanTStopOptions"]