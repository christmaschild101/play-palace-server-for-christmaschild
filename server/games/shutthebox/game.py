"""
Shut the Box Game Implementation for PlayPalace.

Players take turns rolling two dice (one die once only small tiles remain)
and flipping down open tiles whose values total the roll. A player who
cannot close any tiles scores the sum of the remaining open tiles; the
lowest total wins. Shutting every tile is an instant shut-out win.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.round_based_game_mixin import RoundBasedGameMixin
from ...game_utils.actions import Action, ActionSet, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.options import BoolOption, IntOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState


@dataclass
class ShutTheBoxPlayer(Player):
    """Player state for Shut the Box."""

    tiles: list[int] = field(default_factory=lambda: list(range(1, 13)))
    dice: list[int] = field(default_factory=list)  # Empty = waiting to roll
    total_score: int = 0


@dataclass
class ShutTheBoxOptions(GameOptions):
    """Options for Shut the Box."""

    rounds: int = option_field(
        IntOption(
            default=1,
            min_val=1,
            max_val=10,
            value_key="rounds",
            label="shutthebox-set-rounds",
            prompt="shutthebox-enter-rounds",
            change_msg="shutthebox-option-changed-rounds",
            description="shutthebox-desc-rounds",
        )
    )
    single_die_rule: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="shutthebox-set-single-die",
            change_msg="shutthebox-option-changed-single-die",
            description="shutthebox-desc-single-die",
        )
    )


@dataclass
@register_game
class ShutTheBoxGame(ActionGuardMixin, RoundBasedGameMixin, Game):
    """Shut the Box dice game."""

    players: list[ShutTheBoxPlayer] = field(default_factory=list)
    options: ShutTheBoxOptions = field(default_factory=ShutTheBoxOptions)

    @classmethod
    def get_name(cls) -> str:
        return "Shut the Box"

    @classmethod
    def get_type(cls) -> str:
        return "shutthebox"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 1

    @classmethod
    def get_max_players(cls) -> int:
        return 4

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> ShutTheBoxPlayer:
        """Create a new player."""
        return ShutTheBoxPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    # ==========================================================================
    # Game logic helpers
    # ==========================================================================

    def _player(self) -> ShutTheBoxPlayer | None:
        """Current player as the game-specific type."""
        current = self.current_player
        return current  # type: ignore[return-value]

    def _open_sum(self, player: ShutTheBoxPlayer) -> int:
        return sum(player.tiles)

    def _combos(self, player: ShutTheBoxPlayer, total: int) -> list[list[int]]:
        """All subsets of the player's open tiles that sum to total."""
        tiles = sorted(player.tiles)
        results: list[list[int]] = []

        def rec(i: int, remaining: int, chosen: list[int]) -> None:
            if remaining == 0:
                results.append(list(chosen))
                return
            if i >= len(tiles):
                return
            # Skip duplicates (tiles are unique values, but be safe)
            if i > 0 and tiles[i] == tiles[i - 1]:
                rec(i + 1, remaining, chosen)
                return
            if tiles[i] <= remaining:
                chosen.append(tiles[i])
                rec(i + 1, remaining - tiles[i], chosen)
                chosen.pop()
            rec(i + 1, remaining, chosen)

        rec(0, total, [])
        return results

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_roll(self, player: Player, action_id: str) -> None:
        """Roll the dice."""
        stb: ShutTheBoxPlayer = player  # type: ignore
        if stb.dice:
            return

        max_tile = max(stb.tiles)
        use_one_die = self.options.single_die_rule and max_tile <= 6
        self.play_standard_dice_roll_sound()
        stb.dice = [random.randint(1, 6) for _ in range(1 if use_one_die else 2)]  # nosec B311
        total = sum(stb.dice)
        self.broadcast_personal_l(
            player,
            "shutthebox-you-rolled",
            "shutthebox-rolled",
            dice=", ".join(str(d) for d in stb.dice),
        )

        if not self._combos(stb, total):
            self.play_sound("game_pig/lose.ogg")
            score = self._open_sum(stb)
            self.broadcast_l("shutthebox-bust", player=player.name, score=score)
            self._bank(stb, score)
            return

        self.rebuild_all_menus()

    def _action_close(self, player: Player, input_value: str, action_id: str) -> None:
        """Close the chosen combination of tiles."""
        stb: ShutTheBoxPlayer = player  # type: ignore
        if not stb.dice:
            return
        try:
            chosen = sorted((int(x) for x in input_value.split("+")), reverse=True)
        except ValueError:
            return

        if sum(chosen) != sum(stb.dice):
            return
        if any(t not in stb.tiles for t in chosen):
            return

        for tile in chosen:
            stb.tiles.remove(tile)

        self.play_sound("game_dominos/play.ogg")
        self.broadcast_l(
            "shutthebox-closed",
            player=player.name,
            tiles=", ".join(str(t) for t in chosen),
        )

        if not stb.tiles:
            # Shut the box!
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("shutthebox-shutout", player=player.name)
            self.finish_game()
            return

        stb.dice = []
        self.rebuild_all_menus()

    def _action_end_turn(self, player: Player, action_id: str) -> None:
        """Stop early and bank the current open sum."""
        stb: ShutTheBoxPlayer = player  # type: ignore
        score = self._open_sum(stb)
        self.play_sound("game_farkle/bank1.ogg")
        self.broadcast_l("shutthebox-stopped", player=player.name, score=score)
        self._bank(stb, score)

    def _bank(self, stb: ShutTheBoxPlayer, score: int) -> None:
        """Add a turn score to the player's total and end the turn."""
        stb.total_score += score
        self.broadcast_l(
            "shutthebox-banked",
            player=stb.name,
            score=score,
            total=stb.total_score,
        )
        self.end_turn()

    def end_turn(self, jolt_min: int = 10, jolt_max: int = 20) -> None:
        """End the current turn through the round-based flow."""
        BotHelper.jolt_bots(self, ticks=random.randint(jolt_min, jolt_max))  # nosec B311
        self._on_turn_end()

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_roll_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        stb: ShutTheBoxPlayer = player  # type: ignore
        if stb.dice:
            return "shutthebox-close-first"
        return None

    def _is_roll_hidden(self, player: Player) -> Visibility:
        stb: ShutTheBoxPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=not stb.dice)

    def _is_close_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        stb: ShutTheBoxPlayer = player  # type: ignore
        if not stb.dice:
            return "shutthebox-roll-first"
        if not self._combos(stb, sum(stb.dice)):
            return "shutthebox-no-combo"
        return None

    def _is_close_hidden(self, player: Player) -> Visibility:
        stb: ShutTheBoxPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=bool(stb.dice))

    def _is_end_turn_enabled(self, player: Player) -> str | None:
        return self.guard_turn_action_enabled(player)

    def _is_end_turn_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player)

    def _get_end_turn_label(self, player: Player, action_id: str) -> str:
        stb: ShutTheBoxPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "shutthebox-end-turn", score=self._open_sum(stb))

    def _get_status_label(self, player: Player, action_id: str) -> str:
        stb: ShutTheBoxPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "shutthebox-open-tiles", tiles=", ".join(str(t) for t in stb.tiles))

    def _action_status(self, player: Player, action_id: str) -> None:
        """Speak the current open tiles."""
        user = self.get_user(player)
        if user:
            user.speak_l("shutthebox-you-open", tiles=", ".join(str(t) for t in self._open_tiles_for(player)))

    def _open_tiles_for(self, player: Player) -> list[int]:
        stb: ShutTheBoxPlayer = player  # type: ignore
        return list(stb.tiles)

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _combo_options(self, player: Player) -> list[str]:
        stb: ShutTheBoxPlayer = player  # type: ignore
        combos = self._combos(stb, sum(stb.dice))
        encoded = sorted({"+".join(str(t) for t in sorted(combo, reverse=True)) for combo in combos})
        return encoded

    def _combo_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "shutthebox-combo", tiles=option)

    def _bot_select_combo(self, player: Player, options: list[str]) -> str | None:
        """Bot closes the combination covering the most tiles, then the most value."""
        best: list[str] = []
        best_score = -1
        for opt in options:
            tiles = [int(t) for t in opt.split("+")]
            score = len(tiles) * 10 + sum(tiles)
            if score > best_score:
                best_score = score
                best = [opt]
            elif score == best_score:
                best.append(opt)
        return random.choice(best) if best else (options[0] if options else None)

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: ShutTheBoxPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="status",
                label=Localization.get(locale, "shutthebox-status"),
                handler="_action_status",
                is_enabled="_is_end_turn_enabled",
                is_hidden="_is_end_turn_hidden",
                get_label="_get_status_label",
                show_in_actions_menu=False,
            )
        )
        action_set.add(
            Action(
                id="roll",
                label=Localization.get(locale, "shutthebox-roll"),
                handler="_action_roll",
                is_enabled="_is_roll_enabled",
                is_hidden="_is_roll_hidden",
            )
        )
        action_set.add(
            Action(
                id="close",
                label=Localization.get(locale, "shutthebox-close"),
                handler="_action_close",
                is_enabled="_is_close_enabled",
                is_hidden="_is_close_hidden",
                input_request=MenuInput(
                    prompt="shutthebox-pick-combo",
                    options="_combo_options",
                    option_label="_combo_option_label",
                    bot_select="_bot_select_combo",
                ),
            )
        )
        action_set.add(
            Action(
                id="end_turn",
                label=Localization.get(locale, "shutthebox-end-turn", score=0),
                handler="_action_end_turn",
                is_enabled="_is_end_turn_enabled",
                is_hidden="_is_end_turn_hidden",
                get_label="_get_end_turn_label",
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

    def _reset_player_for_game(self, player: ShutTheBoxPlayer) -> None:
        player.total_score = 0

    def _reset_player_for_turn(self, player: ShutTheBoxPlayer) -> None:
        player.tiles = list(range(1, 13))
        player.dice = []

    def _on_round_end(self) -> None:
        """Handle end of a round."""
        if self.round >= self.options.rounds:
            # Lowest total wins
            active = self.get_active_players()
            low = min((p.total_score for p in active), default=0)
            winners = [p.name for p in active if p.total_score == low]
            self.play_sound("game_pig/win.ogg")
            if len(winners) == 1:
                self.broadcast_l("shutthebox-winner", player=winners[0], score=low)
            else:
                for p in self.players:
                    user = self.get_user(p)
                    if user:
                        names_str = Localization.format_list_and(user.locale, winners)
                        user.speak_l("shutthebox-tie", players=names_str, score=low, buffer="table")
            self.finish_game()
            return
        self._start_round()

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: ShutTheBoxPlayer) -> str | None:
        """Bot AI: roll, close, or bank."""
        stb: ShutTheBoxPlayer = player  # type: ignore
        if stb.dice:
            if self._combos(stb, sum(stb.dice)):
                return "close"
            return "end_turn"
        return "roll"

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        active = self.get_active_players()
        scores = {p.name: p.total_score for p in active}
        winner_name = min(scores, key=scores.get) if scores else None

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
                "rounds": self.options.rounds,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: kv[1]):
            lines.append(Localization.get(locale, "shutthebox-score-line", player=name, score=score))
        return lines


__all__ = ["ShutTheBoxGame", "ShutTheBoxPlayer", "ShutTheBoxOptions"]