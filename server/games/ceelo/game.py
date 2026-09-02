"""
Cee-lo Game Implementation for PlayPalace.

Three-dice gambling game. Roll a 4-5-6 for an instant win, three of a kind
for a strong roll (higher triplet beats lower), a pair for a point roll
(the odd die is the point), and 1-2-3 for an instant loss. Each player
rolls once per round; the best combination wins the ante.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.round_based_game_mixin import RoundBasedGameMixin
from ...game_utils.actions import Action, ActionSet, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState


@dataclass
class CeeLoPlayer(Player):
    """Player state for Cee-lo."""

    dice: list[int] = field(default_factory=list)  # Current round roll
    combo_rank: int | None = None  # Lower is better
    combo_key: str = ""  # Localization key for the combo name
    total_points: int = 0
    rerolled: bool = False  # True if this round already rolled


@dataclass
class CeeLoOptions(GameOptions):
    """Options for Cee-lo."""

    ante: int = option_field(
        IntOption(
            default=10,
            min_val=1,
            max_val=100,
            value_key="points",
            label="ceelo-set-ante",
            prompt="ceelo-enter-ante",
            change_msg="ceelo-option-changed-ante",
            description="ceelo-desc-ante",
        )
    )
    rounds: int = option_field(
        IntOption(
            default=10,
            min_val=1,
            max_val=30,
            value_key="rounds",
            label="ceelo-set-rounds",
            prompt="ceelo-enter-rounds",
            change_msg="ceelo-option-changed-rounds",
            description="ceelo-desc-rounds",
        )
    )


@dataclass
@register_game
class CeeLoGame(ActionGuardMixin, RoundBasedGameMixin, Game):
    """Cee-lo dice game."""

    players: list[CeeLoPlayer] = field(default_factory=list)
    options: CeeLoOptions = field(default_factory=CeeLoOptions)

    @classmethod
    def get_name(cls) -> str:
        return "Cee-lo"

    @classmethod
    def get_type(cls) -> str:
        return "ceelo"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 8

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        """Cee-lo-specific leaderboard: total points won."""
        return [
            {
                "id": "total_winnings",
                "path": "final_scores.{player_name}",
                "aggregate": "sum",
                "format": "score",
            },
        ]

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> CeeLoPlayer:
        """Create a new player."""
        return CeeLoPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    # ==========================================================================
    # Combination evaluation
    # ==========================================================================

    def evaluate_roll(self, dice: list[int]) -> tuple[int | None, str]:
        """Classify a roll into (rank, localization key). Lower rank is better.

        Returns (None, "ceelo-no-combo") when the dice must be re-rolled.
        """
        d = sorted(dice)
        if d == [4, 5, 6]:
            return (0, "ceelo-best")
        if d[0] == d[1] == d[2]:
            return (1, "ceelo-trips")
        if d == [1, 2, 3]:
            return (3, "ceelo-worst")
        if d[0] == d[1]:
            return (2, f"ceelo-point-{d[2]}")
        if d[1] == d[2]:
            return (2, f"ceelo-point-{d[0]}")
        return (None, "ceelo-no-combo")

    def _combo_sort_key(self, player: CeeLoPlayer) -> tuple:
        """Sort key: (rank, -triplet/point value, -uniqueness)."""
        rank = player.combo_rank if player.combo_rank is not None else 99
        d = sorted(player.dice or [])
        value = 0
        if rank == 1:  # trips - higher is better
            value = d[0] if d else 0
        elif rank == 2:  # point - higher is better
            if d and len(d) >= 3:
                value = d[2] if d[0] == d[1] else d[0]
        return (rank, -value)

    def _roll_for_player(self, player: CeeLoPlayer) -> None:
        """Roll three dice until a valid combination appears."""
        for _ in range(20):  # Safety bound; a valid roll always appears
            dice = [random.randint(1, 6) for _ in range(3)]  # nosec B311
            rank, key = self.evaluate_roll(dice)
            if rank is not None:
                player.dice = dice
                player.combo_rank = rank
                player.combo_key = key
                return

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_roll(self, player: Player, action_id: str) -> None:
        """Roll the dice once per round."""
        cl: CeeLoPlayer = player  # type: ignore
        if cl.rerolled:
            return

        self.play_standard_dice_roll_sound()
        self._roll_for_player(cl)
        cl.rerolled = True
        self.play_combo_sound(cl)

        user = self.get_user(player)
        locale = user.locale if user else "en"
        combo_text = Localization.get(locale, cl.combo_key, dice=", ".join(str(d) for d in cl.dice))
        self.broadcast_personal_l(
            player,
            "ceelo-you-rolled",
            "ceelo-rolled",
            dice=", ".join(str(d) for d in cl.dice),
        )
        if user:
            user.speak_l(cl.combo_key, buffer="game", dice=", ".join(str(d) for d in cl.dice))

        self.end_turn()

    def play_combo_sound(self, player: CeeLoPlayer) -> None:
        """Play a sound matching the roll's strength."""
        if player.combo_rank == 0:
            self.play_sound("game_farkle/hotdice.ogg")
        elif player.combo_rank == 1:
            self.play_sound("game_farkle/3kind.ogg")
        elif player.combo_rank == 2:
            self.play_sound("game_farkle/takepoint.ogg")
        else:
            self.play_sound("game_pig/lose.ogg")

    def end_turn(self, jolt_min: int = 10, jolt_max: int = 20) -> None:
        """End the current player's turn through the round-based flow."""
        BotHelper.jolt_bots(self, ticks=random.randint(jolt_min, jolt_max))  # nosec B311
        self._on_turn_end()

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_roll_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        cl: CeeLoPlayer = player  # type: ignore
        if cl.rerolled:
            return "ceelo-already-rolled"
        return None

    def _is_roll_hidden(self, player: Player) -> Visibility:
        cl: CeeLoPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=not cl.rerolled)

    def _get_roll_label(self, player: Player, action_id: str) -> str:
        cl: CeeLoPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        if cl.rerolled:
            return Localization.get(locale, cl.combo_key, dice=", ".join(str(d) for d in cl.dice))
        return Localization.get(locale, "ceelo-roll")

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: CeeLoPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "ceelo-roll"),
                handler="_action_roll",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_roll_hidden",
                get_label="_get_roll_label",
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("r", "Roll dice", ["roll"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Round hooks
    # ==========================================================================

    def _reset_player_for_game(self, player: CeeLoPlayer) -> None:
        player.total_points = 0

    def _reset_player_for_round(self, player: CeeLoPlayer) -> None:
        player.dice = []
        player.combo_rank = None
        player.combo_key = ""
        player.rerolled = False

    def _on_round_end(self) -> None:
        """All players rolled: resolve the round."""
        rolled = [p for p in self.get_active_players() if p.combo_rank is not None]
        if not rolled:
            self._start_round()
            return

        best = min(rolled, key=self._combo_sort_key)
        winners = [p for p in rolled if self._combo_sort_key(p) == self._combo_sort_key(best)]

        if len(winners) == 1:
            winner = winners[0]
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("ceelo-round-winner", player=winner.name, points=self.options.ante)
            winner.total_points += self.options.ante
        else:
            # Tie - re-roll the tied players to break it
            self.broadcast_l("ceelo-tie-roll", players=", ".join(p.name for p in winners))
            for p in winners:
                p.rerolled = False
                self._roll_for_player(p)
            self.broadcast_l(
                "ceelo-tie-result",
                winner=", ".join(p.name for p in winners),
            )
            self.play_sound("game_farkle/3kind.ogg")
            # Resolve recursively until unique
            self._on_round_end()
            return

        if self.round >= self.options.rounds:
            # Game over - most points wins
            scores = [(p.name, p.total_points) for p in self.get_active_players()]
            high = max(s for _, s in scores)
            final_winners = [name for name, s in scores if s == high]
            self.play_sound("game_pig/win.ogg")
            if len(final_winners) == 1:
                self.broadcast_l("ceelo-winner", player=final_winners[0], score=high)
            else:
                for p in self.players:
                    user = self.get_user(p)
                    if user:
                        names_str = Localization.format_list_and(user.locale, final_winners)
                        user.speak_l("ceelo-tie", players=names_str, score=high, buffer="table")
            self.finish_game()
            return

        self._start_round()

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: CeeLoPlayer) -> str | None:
        """Bot AI: roll when it's their turn."""
        return "roll"

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        scores = {p.name: p.total_points for p in self.get_active_players()}
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
                for p in self.get_active_players()
            ],
            custom_data={
                "winner_name": winner_name,
                "winner_score": scores.get(winner_name, 0) if winner_name else 0,
                "final_scores": scores,
                "rounds": self.options.rounds,
                "ante": self.options.ante,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "ceelo-score-line", player=name, score=score))
        return lines


__all__ = ["CeeLoGame", "CeeLoPlayer", "CeeLoOptions"]