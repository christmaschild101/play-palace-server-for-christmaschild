"""
Mancala (Kalah) Game Implementation for PlayPalace.

Two players sow stones around a 14-pit board. Landing in your own store
grants a bonus turn; landing in your own empty pit captures the stones
opposite. The game ends when one side is empty; the most stones wins.
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
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState


@dataclass
class MancalaPlayer(Player):
    """Player state for Mancala."""


@dataclass
class MancalaOptions(GameOptions):
    """Options for Mancala."""

    stones_per_pit: int = option_field(
        IntOption(
            default=4,
            min_val=3,
            max_val=6,
            value_key="stones",
            label="mancala-set-stones",
            prompt="mancala-enter-stones",
            change_msg="mancala-option-changed-stones",
            description="mancala-desc-stones",
        )
    )


@dataclass
@register_game
class MancalaGame(ActionGuardMixin, Game):
    """Mancala (Kalah) board game."""

    players: list[MancalaPlayer] = field(default_factory=list)
    options: MancalaOptions = field(default_factory=MancalaOptions)
    board: list[int] = field(default_factory=lambda: [4, 4, 4, 4, 4, 4, 0, 4, 4, 4, 4, 4, 4, 0])
    turn: int = 0

    @classmethod
    def get_name(cls) -> str:
        return "Mancala"

    @classmethod
    def get_type(cls) -> str:
        return "mancala"

    @classmethod
    def get_category(cls) -> str:
        return "category-board-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 2

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> MancalaPlayer:
        """Create a new player."""
        return MancalaPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        stones = self.options.stones_per_pit
        self.board = [stones] * 6 + [0] + [stones] * 6 + [0]
        self.set_turn_players(self.get_active_players())
        self.turn = 0
        self.play_sound("game_squares/start.ogg")
        self._announce_turn()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def get_active_players(self) -> list[MancalaPlayer]:  # type: ignore[override]
        """Active (non-spectator) players."""
        return [p for p in self.players if not p.is_spectator]

    @property
    def current_player(self) -> "MancalaPlayer | None":  # type: ignore[override]
        """Current player by turn index."""
        active = self.get_active_players()
        if not active:
            return None
        return active[self.turn % len(active)]

    # ==========================================================================
    # Board helpers
    # ==========================================================================

    def _side_start(self, player: Player) -> int:
        """Return the index of the first pit on the player's side."""
        if self.turn_player_ids and player.id == self.turn_player_ids[0]:
            return 0
        return 7

    def _my_store(self, player: Player) -> int:
        return self._side_start(player) + 6

    def _opp_store(self, player: Player) -> int:
        return 13 if self._side_start(player) == 0 else 6

    def _side_pits(self, player: Player) -> list[int]:
        start = self._side_start(player)
        return list(range(start, start + 6))

    def _side_is_empty(self, start: int) -> bool:
        return all(self.board[i] == 0 for i in range(start, start + 6))

    def _announce_turn(self) -> None:
        self.announce_turn()

    def _advance_turn(self) -> None:
        self.turn += 1
        self._announce_turn()
        self.rebuild_all_menus()

    # ==========================================================================
    # Move logic
    # ==========================================================================

    def _play_pit(self, player: Player, pit: int) -> None:
        """Sow the stones from a pit and resolve bonus/capture."""
        if self.board[pit] == 0:
            return

        self.play_sound("game_dominos/play.ogg")
        my_store = self._my_store(player)
        opp_store = self._opp_store(player)
        stones = self.board[pit]
        self.board[pit] = 0

        idx = pit
        while stones > 0:
            idx = (idx + 1) % 14
            if idx == opp_store:
                continue
            self.board[idx] += 1
            stones -= 1

        self.broadcast_l("mancala-move", player=player.name, pit=pit + 1)

        bonus = idx == my_store
        captured = 0
        side_start = self._side_start(player)
        if not bonus and side_start <= idx < side_start + 6 and self.board[idx] == 1:
            opp = 12 - idx
            if self.board[opp] > 0:
                captured = self.board[opp] + 1
                self.board[opp] = 0
                self.board[idx] = 0
                self.board[my_store] += captured
                self.play_sound("game_chess/capture1.ogg")
                self.broadcast_l("mancala-capture", player=player.name, stones=captured)

        if self._side_is_empty(0) or self._side_is_empty(7):
            self._finish_game()
            return

        if bonus:
            self.play_sound("game_farkle/takepoint.ogg")
            self.broadcast_l("mancala-bonus", player=player.name)
            self.rebuild_all_menus()
        else:
            self._advance_turn()

    def _finish_game(self) -> None:
        """Collect remaining stones and determine the winner."""
        for start, store in ((0, 6), (7, 13)):
            remaining = sum(self.board[start:start + 6])
            if remaining:
                self.board[store] += remaining
                for i in range(start, start + 6):
                    self.board[i] = 0

        active = self.get_active_players()
        scores = {p.name: self.board[self._my_store(p)] for p in active}
        high = max(scores.values()) if scores else 0
        winners = [name for name, s in scores.items() if s == high]

        self.play_sound("game_pig/win.ogg")
        if len(winners) == 1:
            self.broadcast_l("mancala-winner", player=winners[0], score=high)
        else:
            for p in self.players:
                user = self.get_user(p)
                if user:
                    names_str = Localization.format_list_and(user.locale, winners)
                    user.speak_l("mancala-tie", players=names_str, score=high, buffer="table")
        self.finish_game()

    def _evaluate_move(self, player: Player, start_pit: int) -> tuple[int, bool, int]:
        """Simulate a move: returns (store_gain, bonus, captured)."""
        board = list(self.board)
        my_store = self._my_store(player)
        opp_store = self._opp_store(player)
        stones = board[start_pit]
        board[start_pit] = 0
        idx = start_pit
        while stones > 0:
            idx = (idx + 1) % 14
            if idx == opp_store:
                continue
            board[idx] += 1
            stones -= 1
        gain = board[my_store] - self.board[my_store]
        bonus = idx == my_store
        captured = 0
        side_start = self._side_start(player)
        if not bonus and side_start <= idx < side_start + 6 and board[idx] == 1:
            opp = 12 - idx
            if board[opp] > 0:
                captured = board[opp] + 1
        return gain, bonus, captured

    # ==========================================================================
    # Action handlers and callbacks
    # ==========================================================================

    def _action_move(self, player: Player, input_value: str, action_id: str) -> None:
        """Handle a pit selection."""
        try:
            pit_num = int(input_value)
        except ValueError:
            return
        side_start = self._side_start(player)
        pit = side_start + pit_num - 1
        if pit < side_start or pit >= side_start + 6 or self.board[pit] == 0:
            return
        self._play_pit(player, pit)

    def _is_move_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if not any(self.board[i] for i in self._side_pits(player)):
            return "mancala-no-stones"
        return None

    def _is_move_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player)

    def _pit_options(self, player: Player) -> list[str]:
        pits = [(i - self._side_start(player) + 1, self.board[i]) for i in self._side_pits(player)]
        return [str(n) for n, stones in pits if stones > 0]

    def _pit_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "mancala-pit", n=option)

    def _bot_select_pit(self, player: Player, options: list[str]) -> str | None:
        """Bot picks the move with the best immediate outcome."""
        best: list[str] = []
        best_score = -1
        for opt in options:
            try:
                pit = self._side_start(player) + int(opt) - 1
            except ValueError:
                continue
            gain, bonus, captured = self._evaluate_move(player, pit)
            score = gain * 2 + captured * 3 + (12 if bonus else 0)
            score += random.randint(0, 2)  # nosec B311
            if score > best_score:
                best_score = score
                best = [opt]
            elif score == best_score:
                best.append(opt)
        return random.choice(best) if best else (options[0] if options else None)

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: MancalaPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="move",
                label=Localization.get(locale, "mancala-move-action"),
                handler="_action_move",
                is_enabled="_is_move_enabled",
                is_hidden="_is_move_hidden",
                input_request=MenuInput(
                    prompt="mancala-pick-pit",
                    options="_pit_options",
                    option_label="_pit_option_label",
                    bot_select="_bot_select_pit",
                ),
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("m", "Move stones", ["move"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: MancalaPlayer) -> str | None:
        """Bot AI: choose a pit."""
        return "move"

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        active = self.get_active_players()
        scores = {p.name: self.board[self._my_store(p)] for p in active}
        winner_name = max(scores, key=scores.get) if scores else None

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
                "winner_name": winner_name,
                "winner_score": scores.get(winner_name, 0) if winner_name else 0,
                "final_scores": scores,
                "stones_per_pit": self.options.stones_per_pit,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "mancala-score-line", player=name, score=score))
        return lines


__all__ = ["MancalaGame", "MancalaPlayer", "MancalaOptions"]