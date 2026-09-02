"""
Ship, Captain & Crew Game Implementation for PlayPalace.

Classic dice game: roll a 6 (ship), then a 5 (captain), then a 4 (crew),
each set aside in order. Remaining dice score their face values. First
player to the target score wins (or play a fixed number of rounds and
the highest total wins).
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

NUM_DICE = 5
MAX_ROLLS = 3


@dataclass
class ShipCaptainCrewPlayer(Player):
    """Player state for Ship, Captain & Crew."""

    dice: list[int] = field(default_factory=lambda: [0] * NUM_DICE)
    rolls_left: int = MAX_ROLLS
    turn_score: int = 0
    total_score: int = 0


@dataclass
class ShipCaptainCrewOptions(GameOptions):
    """Options for Ship, Captain & Crew."""

    target_score: int = option_field(
        IntOption(
            default=21,
            min_val=10,
            max_val=1000,
            value_key="score",
            label="shipcaptaincrew-set-target",
            prompt="shipcaptaincrew-enter-target",
            change_msg="shipcaptaincrew-option-changed-target",
            description="shipcaptaincrew-desc-target",
        )
    )
    rounds: int = option_field(
        IntOption(
            default=0,
            min_val=0,
            max_val=20,
            value_key="rounds",
            label="shipcaptaincrew-set-rounds",
            prompt="shipcaptaincrew-enter-rounds",
            change_msg="shipcaptaincrew-option-changed-rounds",
            description="shipcaptaincrew-desc-rounds",
        )
    )


@dataclass
@register_game
class ShipCaptainCrewGame(ActionGuardMixin, RoundBasedGameMixin, Game):
    """Ship, Captain & Crew dice game."""

    players: list[ShipCaptainCrewPlayer] = field(default_factory=list)
    options: ShipCaptainCrewOptions = field(default_factory=ShipCaptainCrewOptions)

    @classmethod
    def get_name(cls) -> str:
        return "Ship, Captain & Crew"

    @classmethod
    def get_type(cls) -> str:
        return "shipcaptaincrew"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> ShipCaptainCrewPlayer:
        """Create a new player with game-specific state."""
        return ShipCaptainCrewPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    # ==========================================================================
    # Game logic helpers
    # ==========================================================================

    def _kept_indices(self, player: ShipCaptainCrewPlayer) -> list[int]:
        """Indices of the set-aside dice: first 6, then first 5, then first 4."""
        kept: list[int] = []
        for value in (6, 5, 4):
            for i, v in enumerate(player.dice):
                if v == value and i not in kept:
                    kept.append(i)
                    break
        return kept

    def _has_full_crew(self, player: ShipCaptainCrewPlayer) -> bool:
        """True when ship, captain, and crew have all been set aside."""
        return len(self._kept_indices(player)) == 3

    def _turn_score(self, player: ShipCaptainCrewPlayer) -> int:
        """Sum of the dice not set aside (0 without a full crew)."""
        if not self._has_full_crew(player):
            return 0
        kept = set(self._kept_indices(player))
        return sum(v for i, v in enumerate(player.dice) if i not in kept)

    def _action_roll(self, player: Player, action_id: str) -> None:
        """Handle the roll action."""
        sc_player: ShipCaptainCrewPlayer = player  # type: ignore
        kept = set(self._kept_indices(sc_player))
        previous_count = len(kept)

        sc_player.rolls_left -= 1
        new_values: list[int] = []
        for i in range(NUM_DICE):
            if i in kept:
                new_values.append(sc_player.dice[i])
            else:
                new_values.append(random.randint(1, 6))  # nosec B311
        sc_player.dice = new_values

        self.play_standard_dice_roll_sound()
        self.broadcast_personal_l(
            player,
            "shipcaptaincrew-you-rolled",
            "shipcaptaincrew-rolled",
            dice=", ".join(str(v) for v in sc_player.dice),
        )
        BotHelper.jolt_bot(player, ticks=random.randint(10, 20))  # nosec B311

        # Announce newly found elements of the crew
        new_count = len(self._kept_indices(sc_player))
        if new_count > previous_count:
            if previous_count == 0:
                self.play_sound("game_farkle/takepoint.ogg")
                self.broadcast_l("shipcaptaincrew-ship-found", player=player.name)
            elif previous_count == 1:
                self.play_sound("game_farkle/takepoint.ogg")
                self.broadcast_l("shipcaptaincrew-captain-found", player=player.name)
            elif previous_count == 2:
                self.play_sound("game_farkle/takepoint.ogg")
                self.broadcast_l("shipcaptaincrew-crew-found", player=player.name)

        if sc_player.rolls_left <= 0:
            self.broadcast_l("shipcaptaincrew-no-rolls-left", player=player.name)

    def _action_bank(self, player: Player, action_id: str) -> None:
        """Handle the bank/end-turn action."""
        sc_player: ShipCaptainCrewPlayer = player  # type: ignore
        score = self._turn_score(sc_player)

        if score > 0:
            self.play_sound("game_farkle/bank1.ogg")
        else:
            self.play_sound("game_pig/lose.ogg")

        sc_player.turn_score = score
        sc_player.total_score += score

        self.broadcast_personal_l(
            player,
            "shipcaptaincrew-you-banked",
            "shipcaptaincrew-banked",
            score=score,
            total=sc_player.total_score,
        )

        if self.options.rounds == 0 and sc_player.total_score >= self.options.target_score:
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l(
                "shipcaptaincrew-winner",
                player=player.name,
                score=sc_player.total_score,
            )
            self.finish_game()
            return

        self.end_turn()

    def end_turn(self, jolt_min: int = 10, jolt_max: int = 20) -> None:
        """End the current player's turn, advancing the round-based flow."""
        BotHelper.jolt_bots(self, ticks=random.randint(jolt_min, jolt_max))  # nosec B311
        self._on_turn_end()

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_roll_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        sc_player: ShipCaptainCrewPlayer = player  # type: ignore
        if sc_player.rolls_left <= 0:
            return "shipcaptaincrew-no-rolls"
        return None

    def _is_roll_hidden(self, player: Player) -> Visibility:
        sc_player: ShipCaptainCrewPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=sc_player.rolls_left > 0)

    def _is_bank_enabled(self, player: Player) -> str | None:
        return self.guard_turn_action_enabled(player)

    def _is_bank_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player)

    def _get_bank_label(self, player: Player, action_id: str) -> str:
        sc_player: ShipCaptainCrewPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        score = self._turn_score(sc_player)
        return Localization.get(locale, "shipcaptaincrew-bank", score=score)

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: ShipCaptainCrewPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "shipcaptaincrew-roll"),
                handler="_action_roll",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_roll_hidden",
            )
        )
        action_set.add(
            Action(
                id="bank",
                label=Localization.get(locale, "shipcaptaincrew-bank", score=0),
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
        self.define_keybind("b", "Bank and end turn", ["bank"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Round hooks
    # ==========================================================================

    def _reset_player_for_game(self, player: ShipCaptainCrewPlayer) -> None:
        player.total_score = 0

    def _reset_player_for_turn(self, player: ShipCaptainCrewPlayer) -> None:
        player.dice = [0] * NUM_DICE
        player.rolls_left = MAX_ROLLS
        player.turn_score = 0

    def _on_round_end(self) -> None:
        """Handle end of a round (fixed-rounds mode only)."""
        if self.options.rounds > 0 and self.round >= self.options.rounds:
            # Fixed rounds complete - highest total wins
            scores = [(p.name, p.total_score) for p in self.get_active_players()]
            high_score = max(s for _, s in scores)
            winners = [name for name, s in scores if s == high_score]
            self.play_sound("game_pig/win.ogg")
            if len(winners) == 1:
                self.broadcast_l(
                    "shipcaptaincrew-winner",
                    player=winners[0],
                    score=high_score,
                )
            else:
                for player in self.players:
                    user = self.get_user(player)
                    if user:
                        names_str = Localization.format_list_and(user.locale, winners)
                        user.speak_l(
                            "shipcaptaincrew-tie",
                            players=names_str,
                            score=high_score,
                            buffer="table",
                        )
            self.finish_game()
            return
        self._start_round()

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        scores = {p.name: p.total_score for p in self.get_active_players()}
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
                "target_score": self.options.target_score,
                "rounds": self.options.rounds,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "shipcaptaincrew-score-line", player=name, score=score))
        return lines

    def bot_think(self, player: ShipCaptainCrewPlayer) -> str | None:
        """Bot AI: roll until the crew is complete or the score is good enough."""
        if player.rolls_left <= 0:
            return "bank"
        if not self._has_full_crew(player):
            return "roll"
        score = self._turn_score(player)
        needed = max(1, self.options.target_score - player.total_score)
        if score >= needed:
            return "bank"
        return "roll"


__all__ = ["ShipCaptainCrewGame", "ShipCaptainCrewPlayer", "ShipCaptainCrewOptions"]