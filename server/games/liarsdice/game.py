"""
Liar's Dice Game Implementation for PlayPalace.

Each player rolls a private hand of five dice. Turn by turn, bid a higher
quantity of a face value, or challenge the previous bid. Ones are wild
(option). The loser of a challenge loses a die; players are eliminated at
zero dice, and the last player standing wins.
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
from ...game_utils.options import BoolOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

DICE_PER_PLAYER = 5


@dataclass
class LiarsDicePlayer(Player):
    """Player state for Liar's Dice."""

    dice: list[int] = field(default_factory=list)
    eliminated: bool = False
    pending_qty: int | None = None  # Set while choosing a face for the bid


@dataclass
class LiarsDiceOptions(GameOptions):
    """Options for Liar's Dice."""

    wild_ones: bool = option_field(
        BoolOption(
            default=True,
            value_key="enabled",
            label="liarsdice-set-wild-ones",
            change_msg="liarsdice-option-changed-wild-ones",
            description="liarsdice-desc-wild-ones",
        )
    )


@dataclass
@register_game
class LiarsDiceGame(ActionGuardMixin, Game):
    """Liar's Dice bluffing dice game."""

    players: list[LiarsDicePlayer] = field(default_factory=list)
    options: LiarsDiceOptions = field(default_factory=LiarsDiceOptions)
    round: int = 1
    bid_qty: int = 0
    bid_face: int = 0
    bidder_id: str = ""

    @classmethod
    def get_name(cls) -> str:
        return "Liar's Dice"

    @classmethod
    def get_type(cls) -> str:
        return "liarsdice"

    @classmethod
    def get_category(cls) -> str:
        return "category-dice-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        """Liar's Dice-specific leaderboard: average dice remaining."""
        return [
            {
                "id": "dice_remaining",
                "path": "dice_left.{player_name}",
                "aggregate": "avg",
                "format": "avg",
                "decimals": 1,
            },
        ]

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> LiarsDicePlayer:
        """Create a new player."""
        return LiarsDicePlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        for player in self.get_active_players():
            player.dice = [random.randint(1, 6) for _ in range(DICE_PER_PLAYER)]  # nosec B311
        self.round = 1
        self.bid_qty = 0
        self.bid_face = 0
        self.bidder_id = ""
        for player in self.players:
            player.pending_qty = None
        self.set_turn_players(self.get_active_players())
        self.play_standard_dice_roll_sound()
        self._announce_round_start()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def get_active_players(self) -> list[LiarsDicePlayer]:  # type: ignore[override]
        """Players who have not been eliminated."""
        return [p for p in self.players if not p.is_spectator and not p.eliminated]

    # ==========================================================================
    # Round flow
    # ==========================================================================

    def _announce_round_start(self) -> None:
        """Roll dice and tell each player their hand."""
        alive = self.get_active_players()
        self.broadcast_l("liarsdice-round-start", round=self.round)
        for player in alive:
            user = self.get_user(player)
            if user:
                user.speak_l(
                    "liarsdice-your-dice",
                    dice=", ".join(str(d) for d in player.dice),
                    buffer="table",
                )
        self.announce_turn()

    def _start_new_round(self, after_player: LiarsDicePlayer | None) -> None:
        """Begin a fresh round with new rolls, ordered after the given player."""
        alive = self.get_active_players()
        if after_player is not None and after_player in alive:
            idx = alive.index(after_player)
            order = alive[idx + 1:] + alive[:idx + 1]
        else:
            order = alive
        self.round += 1
        for player in alive:
            player.dice = [random.randint(1, 6) for _ in range(len(player.dice))]  # nosec B311
            player.pending_qty = None
        self.bid_qty = 0
        self.bid_face = 0
        self.bidder_id = ""
        self.set_turn_players(order)
        self.play_standard_dice_roll_sound()
        self._announce_round_start()

    # ==========================================================================
    # Bidding
    # ==========================================================================

    def _bid_beats_current(self, qty: int, face: int) -> bool:
        """A bid beats the current one if it is a higher quantity of any face,
        or the same quantity of a higher face."""
        if self.bid_qty == 0:
            return True
        if qty > self.bid_qty:
            return True
        if qty == self.bid_qty and face > self.bid_face:
            return True
        return False

    def _place_bid(self, player: LiarsDicePlayer, qty: int, face: int) -> bool:
        if not self._bid_beats_current(qty, face):
            user = self.get_user(player)
            if user:
                user.speak_l("liarsdice-lower-bid")
            return False
        self.bid_qty = qty
        self.bid_face = face
        self.bidder_id = player.id
        self.play_sound("game_farkle/takepoint.ogg")
        self.broadcast_l("liarsdice-bid", player=player.name, qty=qty, face=face)
        self.pending_qty_clear()
        self.advance_turn()
        return True

    def pending_qty_clear(self) -> None:
        for p in self.players:
            p.pending_qty = None

    # ==========================================================================
    # Challenges
    # ==========================================================================

    def _resolve_challenge(self, challenger: LiarsDicePlayer) -> None:
        """Count the dice and remove one from the loser."""
        alive = self.get_active_players()
        actual = 0
        for p in alive:
            for die in p.dice:
                if die == self.bid_face or (self.options.wild_ones and die == 1):
                    actual += 1

        bidder = self.get_player_by_id(self.bidder_id)
        truth = actual >= self.bid_qty
        loser = challenger if truth else bidder

        self.play_sound("game_chess/capture1.ogg")
        if truth:
            self.broadcast_l(
                "liarsdice-challenge-true",
                challenger=challenger.name,
                bidder=bidder.name if bidder else "?",
                qty=self.bid_qty,
                face=self.bid_face,
                actual=actual,
            )
        else:
            self.broadcast_l(
                "liarsdice-challenge-false",
                challenger=challenger.name,
                bidder=bidder.name if bidder else "?",
                qty=self.bid_qty,
                face=self.bid_face,
                actual=actual,
            )

        if loser is None:
            self._start_new_round(challenger)
            return

        loser.dice.pop()
        if not loser.dice:
            loser.eliminated = True
            self.play_sound("game_pig/lose.ogg")
            self.broadcast_l("liarsdice-eliminated", player=loser.name)
        else:
            self.broadcast_l("liarsdice-lost-die", player=loser.name, dice=len(loser.dice))

        remaining = self.get_active_players()
        if len(remaining) == 1:
            winner = remaining[0]
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("liarsdice-winner", player=winner.name)
            self.finish_game()
            return

        self._start_new_round(loser)

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_bid_qty(self, player: Player, input_value: str, action_id: str) -> None:
        """First step of bidding: choose the quantity."""
        ld: LiarsDicePlayer = player  # type: ignore
        try:
            qty = int(input_value)
        except ValueError:
            return
        if qty < 1 or qty > self._total_dice() + 2:
            return
        ld.pending_qty = qty
        self.update_player_menu(player)

    def _action_bid_face(self, player: Player, input_value: str, action_id: str) -> None:
        """Second step of bidding: choose the face and place the bid."""
        ld: LiarsDicePlayer = player  # type: ignore
        qty = ld.pending_qty
        if qty is None:
            return
        try:
            face = int(input_value)
        except ValueError:
            return
        if face < 2 or face > 6:
            return
        self._place_bid(ld, qty, face)

    def _action_challenge(self, player: Player, action_id: str) -> None:
        """Challenge the current bid."""
        ld: LiarsDicePlayer = player  # type: ignore
        if self.bid_qty == 0:
            return
        self._resolve_challenge(ld)

    def _total_dice(self) -> int:
        return sum(len(p.dice) for p in self.get_active_players())

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_bid_qty_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        ld: LiarsDicePlayer = player  # type: ignore
        if ld.pending_qty is not None:
            return "liarsdice-pick-face-first"
        return None

    def _is_bid_qty_hidden(self, player: Player) -> Visibility:
        ld: LiarsDicePlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=ld.pending_qty is None)

    def _is_bid_face_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        ld: LiarsDicePlayer = player  # type: ignore
        if ld.pending_qty is None:
            return "liarsdice-pick-qty-first"
        return None

    def _is_bid_face_hidden(self, player: Player) -> Visibility:
        ld: LiarsDicePlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=ld.pending_qty is not None)

    def _is_challenge_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.bid_qty == 0:
            return "liarsdice-no-bid"
        return None

    def _is_challenge_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.bid_qty > 0)

    def _get_challenge_label(self, player: Player, action_id: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        if self.bid_qty:
            return Localization.get(locale, "liarsdice-challenge", qty=self.bid_qty, face=self.bid_face)
        return Localization.get(locale, "liarsdice-challenge-no-bid")

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _qty_options(self, player: Player) -> list[str]:
        return [str(q) for q in range(1, self._total_dice() + 2)]

    def _face_options(self, player: Player) -> list[str]:
        return [str(f) for f in range(2, 7)]

    def _face_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        from ...game_utils.cards import RANK_KEYS
        key = RANK_KEYS.get(int(option))
        return Localization.get(locale, key) if key else option

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def _my_face_counts(self, player: LiarsDicePlayer) -> dict[int, int]:
        counts = {f: 0 for f in range(2, 7)}
        for die in player.dice:
            if die == 1:
                if self.options.wild_ones:
                    for f in range(2, 7):
                        counts[f] += 1
            elif die in counts:
                counts[die] += 1
        return counts

    def _bot_bid_plan(self, player: LiarsDicePlayer) -> tuple[int, int] | None:
        """Decide a (qty, face) bid, or None to challenge."""
        counts = self._my_face_counts(player)
        others_dice = self._total_dice() - len(player.dice)
        estimate_others = others_dice / 3.0  # face or wild one chance per die

        best_face = max(counts, key=counts.get)
        proposed_qty = max(1, int(counts[best_face] + estimate_others))

        if self.bid_qty == 0:
            # First bid of the round: safest plausible bid
            return (max(1, counts[best_face]), best_face)

        if proposed_qty > self.bid_qty:
            return (proposed_qty, best_face)
        if proposed_qty == self.bid_qty:
            # Try a higher face with the same quantity
            for face in range(self.bid_face + 1, 7):
                if face in counts and counts[face] >= counts[best_face] - 1:
                    return (proposed_qty, face)
        # The bid looks too strong; challenge unless we hold a lot of that face
        my_bid_face_count = counts.get(self.bid_face, 0) + (len([d for d in player.dice if d == 1]) if self.options.wild_ones else 0)
        if self.bid_qty > my_bid_face_count + others_dice / 2:
            return None
        return (self.bid_qty + 1, best_face)

    def _bot_select_qty(self, player: Player, options: list[str]) -> str | None:
        ld: LiarsDicePlayer = player  # type: ignore
        plan = self._bot_bid_plan(ld)
        qty = plan[0] if plan else 1
        qty_str = str(qty)
        if qty_str in options:
            return qty_str
        return max(options, key=int)

    def _bot_select_face(self, player: Player, options: list[str]) -> str | None:
        ld: LiarsDicePlayer = player  # type: ignore
        plan = self._bot_bid_plan(ld)
        face = plan[1] if plan else 2
        face_str = str(face)
        if face_str in options:
            return face_str
        return options[0]

    def bot_think(self, player: LiarsDicePlayer) -> str | None:
        """Bot AI: bid or challenge."""
        if player.pending_qty is None:
            if self.bid_qty == 0 or self._bot_bid_plan(player) is not None:
                return "bid_qty"
            return "challenge"
        return "bid_face"

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: LiarsDicePlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="bid_qty",
                label=Localization.get(locale, "liarsdice-bid"),
                handler="_action_bid_qty",
                is_enabled="_is_bid_qty_enabled",
                is_hidden="_is_bid_qty_hidden",
                input_request=MenuInput(
                    prompt="liarsdice-pick-qty",
                    options="_qty_options",
                    option_label="_qty_option_label",
                    bot_select="_bot_select_qty",
                ),
            )
        )
        action_set.add(
            Action(
                id="bid_face",
                label=Localization.get(locale, "liarsdice-bid-face"),
                handler="_action_bid_face",
                is_enabled="_is_bid_face_enabled",
                is_hidden="_is_bid_face_hidden",
                input_request=MenuInput(
                    prompt="liarsdice-pick-face",
                    options="_face_options",
                    option_label="_face_option_label",
                    bot_select="_bot_select_face",
                ),
            )
        )
        action_set.add(
            Action(
                id="challenge",
                label=Localization.get(locale, "liarsdice-challenge-no-bid"),
                handler="_action_challenge",
                is_enabled="_is_challenge_enabled",
                is_hidden="_is_challenge_hidden",
                get_label="_get_challenge_label",
            )
        )
        return action_set

    def _qty_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "liarsdice-qty", qty=option)

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("b", "Bid", ["bid_qty"], state=KeybindState.ACTIVE)
        self.define_keybind("c", "Challenge", ["challenge"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        winner_name = None
        alive = self.get_active_players()
        if len(alive) == 1:
            winner_name = alive[0].name
        dice_left = {p.name: len(p.dice) for p in self.players}

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
                for p in self.players
                if not p.is_spectator
            ],
            custom_data={
                "winner_name": winner_name,
                "dice_left": dice_left,
                "rounds_played": self.round,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        dice_left = result.custom_data.get("dice_left", {})
        for name, count in sorted(dice_left.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "liarsdice-score-line", player=name, dice=count))
        return lines


__all__ = ["LiarsDiceGame", "LiarsDicePlayer", "LiarsDiceOptions"]