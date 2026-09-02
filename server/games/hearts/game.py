"""
Hearts Game Implementation for PlayPalace.

Four players, thirteen cards each. Before each hand, pass three cards to a
neighbor (left by default). Take tricks following suit; hearts cost one point
each and the Queen of Spades costs thirteen. Shooting the moon takes all
twenty-six points as a negative score. When any player crosses the target,
the lowest total wins.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.cards import Card, Deck, DeckFactory, Suit, card_name
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.options import IntOption, MenuOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

HEARTS = int(Suit.HEARTS)
SPADES = int(Suit.SPADES)
QUEEN_SPADES_RANK = 12
TRICKS_PER_ROUND = 13


@dataclass
class HeartsPlayer(Player):
    """Player state for Hearts."""

    hand: list[Card] = field(default_factory=list)
    taken: list[Card] = field(default_factory=list)
    pass_picks: list[int] = field(default_factory=list)
    total: int = 0  # Points across hands (lower is better)
    moons: int = 0  # Shooting-the-moon count


@dataclass
class HeartsOptions(GameOptions):
    """Options for Hearts."""

    target_score: int = option_field(
        IntOption(
            default=100,
            min_val=10,
            max_val=500,
            value_key="score",
            label="hearts-set-target",
            prompt="hearts-enter-target",
            change_msg="hearts-option-changed-target",
            description="hearts-desc-target",
        )
    )
    pass_mode: str = option_field(
        MenuOption(
            default="left",
            value_key="mode",
            choices=["left", "right", "across", "none"],
            choice_labels={
                "left": "hearts-pass-left",
                "right": "hearts-pass-right",
                "across": "hearts-pass-across",
                "none": "hearts-pass-none",
            },
            label="hearts-set-pass",
            prompt="hearts-select-pass",
            change_msg="hearts-option-changed-pass",
            description="hearts-desc-pass",
        )
    )


@dataclass
@register_game
class HeartsGame(ActionGuardMixin, Game):
    """Hearts trick-taking card game."""

    players: list[HeartsPlayer] = field(default_factory=list)
    options: HeartsOptions = field(default_factory=HeartsOptions)
    deck: Deck = field(default_factory=Deck)
    phase: str = "pass"  # "pass" | "play"
    trick: list[Card] = field(default_factory=list)
    trick_players: list[str] = field(default_factory=list)
    hearts_broken: bool = False
    round_tricks: int = 0

    @classmethod
    def get_name(cls) -> str:
        return "Hearts"

    @classmethod
    def get_type(cls) -> str:
        return "hearts"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 4

    @classmethod
    def get_max_players(cls) -> int:
        return 4

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> HeartsPlayer:
        """Create a new player."""
        return HeartsPlayer(id=player_id, name=name, is_bot=is_bot)

    @classmethod
    def get_leaderboard_types(cls) -> list[dict]:
        """Hearts-specific leaderboards: lowest points + moon shots."""
        return [
            {
                "id": "lowest_points",
                "path": "final_scores.{player_name}",
                "aggregate": "avg",
                "format": "avg",
                "decimals": 1,
                "reverse": True,  # Fewer points is better
            },
            {
                "id": "moon_shots",
                "path": "player_stats.{player_name}.moons",
                "aggregate": "sum",
                "format": "score",
            },
        ]

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        for player in self.players:
            player.total = 0
            player.moons = 0
        self.play_music("game_pig/mus.ogg")
        self._start_hand()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def get_active_players(self) -> list[HeartsPlayer]:  # type: ignore[override]
        """Active (non-spectator) players."""
        return [p for p in self.players if not p.is_spectator]

    @staticmethod
    def _rank_value(card: Card) -> int:
        """Ace is high."""
        return card.rank if card.rank != 1 else 14

    def _card_by_id(self, card_id: int) -> Card | None:
        for card in self.deck.cards:
            if card.id == card_id:
                return card
        for player in self.get_active_players():
            for card in player.hand:
                if card.id == card_id:
                    return card
        return None

    # ==========================================================================
    # Hand (round) setup
    # ==========================================================================

    def _start_hand(self) -> None:
        """Deal a fresh hand and begin the pass phase (or play)."""
        self.round += 1
        active = self.get_active_players()
        self.deck, _ = DeckFactory.standard_deck()
        for player in active:
            player.hand = self.deck.draw(13)
            player.taken = []
            player.pass_picks = []
        self.hearts_broken = False
        self.round_tricks = 0
        self.trick = []
        self.trick_players = []

        leader = active[self.round % len(active)]
        self.set_turn_players(active)
        # Rotate turn order so the leader plays first this hand
        self.set_turn_players(self._rotation_starting_at(leader))

        self.play_sound("game_cards/shuffle1.ogg")
        self.broadcast_l("hearts-hand-start", round=self.round)

        if self.options.pass_mode == "none":
            self.phase = "play"
            self.broadcast_l("hearts-no-pass")
            self._announce_trick()
            return

        self.phase = "pass"
        for p in self.players:
            user = self.get_user(p)
            if user:
                user.speak_l(
                    "hearts-pass-now",
                    mode=Localization.get(user.locale, self._pass_mode_text()),
                    buffer="table",
                )
        self.announce_turn()

    def _rotation_starting_at(self, leader: HeartsPlayer) -> list[HeartsPlayer]:
        active = self.get_active_players()
        idx = active.index(leader)
        return active[idx:] + active[:idx]

    def _pass_mode_text(self) -> str:
        mode = self.options.pass_mode
        return {
            "left": "hearts-pass-left",
            "right": "hearts-pass-right",
            "across": "hearts-pass-across",
            "none": "hearts-pass-none",
        }.get(mode, mode)

    def _complete_passes(self) -> None:
        """Distribute the selected cards and move to play."""
        active = self.get_active_players()
        lookup: dict[int, Card] = {}
        for p in active:
            for card in p.hand:
                lookup[card.id] = card

        passes = {p.id: list(p.pass_picks) for p in active}
        for p in active:
            p.hand = [c for c in p.hand if c.id not in passes[p.id]]

        incoming: dict[str, list[int]] = {p.id: [] for p in active}
        for sender in active:
            target = active[self._pass_target(active.index(sender))]
            incoming[target.id].extend(passes[sender.id])

        for p in active:
            for card_id in incoming[p.id]:
                card = lookup.get(card_id)
                if card:
                    p.hand.append(card)
            p.pass_picks = []

        self.phase = "play"
        self.trick = []
        self.trick_players = []
        self.play_sound("game_cards/small_shuffle.ogg")
        self.broadcast_l("hearts-pass-complete")
        self._announce_trick()

    def _pass_target(self, index: int) -> int:
        n = len(self.get_active_players())
        mode = self.options.pass_mode
        if mode == "left":
            return (index + 1) % n
        if mode == "right":
            return (index - 1) % n
        if mode == "across":
            return (index + n // 2) % n
        return index

    def _announce_trick(self) -> None:
        """Announce the leader and start the trick."""
        self.turn_index = 0
        self.broadcast_l(
            "hearts-trick-lead",
            player=self.current_player.name if self.current_player else "?",
        )
        self.announce_turn()
        self.rebuild_all_menus()

    # ==========================================================================
    # Trick play
    # ==========================================================================

    def _legal_cards(self, player: HeartsPlayer) -> list[Card]:
        """Cards the player may play this trick."""
        if not player.hand:
            return []
        if not self.trick:
            # Leading: may not lead hearts before hearts are broken
            if not self.hearts_broken:
                non_hearts = [c for c in player.hand if c.suit != HEARTS]
                if non_hearts:
                    return non_hearts
            return list(player.hand)
        led_suit = self.trick[0].suit
        matching = [c for c in player.hand if c.suit == led_suit]
        return matching if matching else list(player.hand)

    def _play_card(self, player: HeartsPlayer, card_id: int) -> None:
        card = self._card_by_id(card_id)
        if card is None or card not in player.hand:
            return
        if card not in self._legal_cards(player):
            user = self.get_user(player)
            if user:
                user.speak_l("hearts-must-follow")
            return
        player.hand.remove(card)
        self.trick.append(card)
        self.trick_players.append(player.id)

        locale = self._locale_for(player)
        self.broadcast_l(
            "hearts-played",
            player=player.name,
            card=card_name(card, locale),
        )
        self.play_sound("game_cards/play1.ogg")

        if len(self.trick) == 4:
            self._resolve_trick()
        else:
            self.advance_turn()

    def _resolve_trick(self) -> None:
        """Award the trick to the highest card of the led suit."""
        led_suit = self.trick[0].suit
        best_index = 0
        for i, card in enumerate(self.trick):
            if card.suit == led_suit and self._rank_value(card) > self._rank_value(self.trick[best_index]):
                best_index = i
            if card.suit == HEARTS:
                self.hearts_broken = True

        winner_id = self.trick_players[best_index]
        winner = self.get_player_by_id(winner_id)
        if winner:
            winner.taken.extend(self.trick)
            self.play_sound("game_chess/capture2.ogg")
            self.broadcast_l("hearts-trick-won", player=winner.name)

        self.round_tricks += 1
        self.trick = []
        self.trick_players = []

        if self.round_tricks >= TRICKS_PER_ROUND:
            self._end_hand()
            return

        if self.hearts_broken:
            self.broadcast_l("hearts-broken")
        if winner:
            self.set_turn_players(self._rotation_starting_at(winner))
        self._announce_trick()

    # ==========================================================================
    # Scoring
    # ==========================================================================

    def _count_hand_points(self, player: HeartsPlayer) -> int:
        points = 0
        for card in player.taken:
            if card.suit == HEARTS:
                points += 1
            elif card.suit == SPADES and card.rank == QUEEN_SPADES_RANK:
                points += 13
        return points

    def _end_hand(self) -> None:
        """Score the hand and decide whether the game continues."""
        active = self.get_active_players()
        points = {p.id: self._count_hand_points(p) for p in active}
        total_points = sum(points.values())

        # Shooting the moon: one player took everything
        shooter = None
        for p in active:
            if points[p.id] == total_points and total_points == 26:
                shooter = p
                break

        if shooter is not None:
            shooter.total += -26
            shooter.moons += 1
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("hearts-moon", player=shooter.name)
        else:
            for p in active:
                p.total += points[p.id]

        self.broadcast_l("hearts-hand-scores", scores=self._scores_text())

        if any(p.total >= self.options.target_score for p in active):
            # Game over: lowest total wins
            low = min(p.total for p in active)
            winners = [p.name for p in active if p.total == low]
            self.play_sound("game_pig/win.ogg")
            if len(winners) == 1:
                self.broadcast_l("hearts-winner", player=winners[0], score=low)
            else:
                for p in self.players:
                    user = self.get_user(p)
                    if user:
                        names_str = Localization.format_list_and(user.locale, winners)
                        user.speak_l("hearts-tie", players=names_str, score=low, buffer="table")
            self.finish_game()
            return

        self._start_hand()

    def _scores_text(self) -> str:
        return ", ".join(f"{p.name}: {p.total}" for p in self.get_active_players())

    def _locale_for(self, player: Player) -> str:
        user = self.get_user(player)
        return user.locale if user else "en"

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_pass(self, player: Player, input_value: str, action_id: str) -> None:
        """Pick a card to pass."""
        hp: HeartsPlayer = player  # type: ignore
        try:
            card_id = int(input_value)
        except ValueError:
            return
        if card_id in hp.pass_picks:
            return
        if any(c.id == card_id for c in hp.hand):
            hp.pass_picks.append(card_id)
            self.play_sound("game_cards/discard1.ogg")
            if len(hp.pass_picks) == 3:
                self.broadcast_l("hearts-picked-three", player=player.name)
                if all(len(p.pass_picks) == 3 for p in self.get_active_players()):
                    self._complete_passes()
                    return
            self.advance_turn()

    def _action_pass_done(self, player: Player, action_id: str) -> None:
        """Pass control when this player's picks are complete but not everyone's."""
        hp: HeartsPlayer = player  # type: ignore
        if self.phase != "pass":
            return
        if len(hp.pass_picks) != 3:
            return
        if all(len(p.pass_picks) == 3 for p in self.get_active_players()):
            self._complete_passes()
            return
        self.advance_turn()

    def _action_play(self, player: Player, input_value: str, action_id: str) -> None:
        """Play a card to the current trick."""
        hp: HeartsPlayer = player  # type: ignore
        try:
            card_id = int(input_value)
        except ValueError:
            return
        self._play_card(hp, card_id)

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_pass_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "pass":
            return "hearts-not-passing"
        hp: HeartsPlayer = player  # type: ignore
        if len(hp.pass_picks) >= 3:
            return "hearts-already-picked-three"
        return None

    def _is_pass_hidden(self, player: Player) -> Visibility:
        hp: HeartsPlayer = player  # type: ignore
        return self.turn_action_visibility(
            player,
            extra_condition=self.phase == "pass" and len(hp.pass_picks) < 3,
        )

    def _is_pass_done_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "pass":
            return "hearts-not-passing"
        hp: HeartsPlayer = player  # type: ignore
        if len(hp.pass_picks) != 3:
            return "hearts-pick-three-first"
        return None

    def _is_pass_done_hidden(self, player: Player) -> Visibility:
        hp: HeartsPlayer = player  # type: ignore
        return self.turn_action_visibility(
            player,
            extra_condition=self.phase == "pass" and len(hp.pass_picks) == 3,
        )

    def _is_play_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if self.phase != "play":
            return "hearts-not-playing"
        return None

    def _is_play_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player, extra_condition=self.phase == "play")

    def _get_pass_label(self, player: Player, action_id: str) -> str:
        hp: HeartsPlayer = player  # type: ignore
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return Localization.get(locale, "hearts-pass", count=3 - len(hp.pass_picks))

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _pass_options(self, player: Player) -> list[str]:
        hp: HeartsPlayer = player  # type: ignore
        return [str(c.id) for c in hp.hand if c.id not in hp.pass_picks]

    def _play_options(self, player: Player) -> list[str]:
        hp: HeartsPlayer = player  # type: ignore
        return [str(c.id) for c in self._legal_cards(hp)]

    def _card_option_label(self, player: Player, option: str) -> str:
        locale = self._locale_for(player)
        try:
            card_id = int(option)
        except ValueError:
            return option
        card = self._card_by_id(card_id)
        return card_name(card, locale) if card else option

    def _bot_pass_pick(self, player: Player, options: list[str]) -> str | None:
        """Bot passes the Queen of Spades, then high hearts, then high cards."""
        hp: HeartsPlayer = player  # type: ignore
        option_ids = set(map(int, options))

        def priority(card: Card) -> tuple:
            if card.suit == SPADES and card.rank == QUEEN_SPADES_RANK:
                return (0, 15, card.id)
            if card.suit == HEARTS:
                return (1, self._rank_value(card), card.id)
            if card.suit == SPADES and self._rank_value(card) >= 12:
                return (2, self._rank_value(card), card.id)
            return (3, self._rank_value(card), card.id)

        best = sorted(hp.hand, key=priority)[:3]
        for card in best:
            if card.id in option_ids:
                return str(card.id)
        return options[0] if options else None

    def _bot_play_card(self, player: Player, options: list[str]) -> str | None:
        """Bot plays the lowest legal card, dumping the Queen of Spades when possible."""
        hp: HeartsPlayer = player  # type: ignore
        legal = self._legal_cards(hp)
        options_set = set(map(int, options))

        # Can't follow suit: dump the Queen of Spades if held
        if self.trick and hp.hand:
            led_suit = self.trick[0].suit
            has_suit = any(c.suit == led_suit for c in hp.hand)
            if not has_suit:
                queen = next((c for c in hp.hand if c.suit == SPADES and c.rank == QUEEN_SPADES_RANK), None)
                if queen and queen.id in options_set:
                    return str(queen.id)
                hearts = [c for c in hp.hand if c.suit == HEARTS and self.hearts_broken]
                if hearts:
                    best = min(hearts, key=lambda c: (c.suit, self._rank_value(c)))
                    if best.id in options_set:
                        return str(best.id)
                non_hearts = [c for c in hp.hand if c.suit != HEARTS]
                if non_hearts:
                    best = max(non_hearts, key=self._rank_value)
                    if best.id in options_set:
                        return str(best.id)

        # Otherwise play the lowest card that follows the suit (or lowest overall)
        if legal:
            best = min(legal, key=lambda c: (c.suit, self._rank_value(c)))
            return str(best.id) if best.id in options_set else options[0]
        return options[0] if options else None

    def bot_think(self, player: HeartsPlayer) -> str | None:
        """Bot AI: pass three cards, then play."""
        if self.phase == "pass":
            if len(player.pass_picks) >= 3:
                return "pass_done"
            return "pass"
        return "play" if self._legal_cards(player) else None

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: HeartsPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="status",
                label=Localization.get(locale, "hearts-status"),
                handler="_action_status",
                is_enabled="_is_status_enabled",
                is_hidden="_is_status_hidden",
                get_label="_get_status_label",
                show_in_actions_menu=False,
            )
        )
        action_set.add(
            Action(
                id="pass",
                label=Localization.get(locale, "hearts-pass", count=3),
                handler="_action_pass",
                is_enabled="_is_pass_enabled",
                is_hidden="_is_pass_hidden",
                get_label="_get_pass_label",
                input_request=MenuInput(
                    prompt="hearts-pick-pass-card",
                    options="_pass_options",
                    option_label="_card_option_label",
                    bot_select="_bot_pass_pick",
                ),
            )
        )
        action_set.add(
            Action(
                id="pass_done",
                label=Localization.get(locale, "hearts-pass-done"),
                handler="_action_pass_done",
                is_enabled="_is_pass_done_enabled",
                is_hidden="_is_pass_done_hidden",
            )
        )
        action_set.add(
            Action(
                id="play",
                label=Localization.get(locale, "hearts-play"),
                handler="_action_play",
                is_enabled="_is_play_enabled",
                is_hidden="_is_play_hidden",
                input_request=MenuInput(
                    prompt="hearts-pick-card",
                    options="_play_options",
                    option_label="_card_option_label",
                    bot_select="_bot_play_card",
                ),
            )
        )
        return action_set

    def _is_status_enabled(self, player: Player) -> str | None:
        return self.guard_turn_action_enabled(player)

    def _is_status_hidden(self, player: Player) -> Visibility:
        return self.turn_action_visibility(player)

    def _get_status_label(self, player: Player, action_id: str) -> str:
        locale = self._locale_for(player)
        trick_text = ", ".join(card_name(c, locale) for c in self.trick)
        return Localization.get(
            locale,
            "hearts-status-label",
            trick=trick_text or "-",
            broken="yes" if self.hearts_broken else "no",
        )

    def _action_status(self, player: Player, action_id: str) -> None:
        """Speak the current trick and broken state."""
        user = self.get_user(player)
        if not user:
            return
        locale = user.locale
        trick_text = ", ".join(card_name(c, locale) for c in self.trick)
        user.speak_l(
            "hearts-status-info",
            trick=trick_text or "-",
            broken="yes" if self.hearts_broken else "no",
        )

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("p", "Play a card", ["play"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        totals = {p.name: p.total for p in self.get_active_players()}
        winner_name = min(totals, key=totals.get) if totals else None

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
                "winner_score": totals.get(winner_name, 0) if winner_name else 0,
                "final_scores": totals,
                "player_stats": {
                    p.name: {"moons": p.moons} for p in self.get_active_players()
                },
                "target_score": self.options.target_score,
                "pass_mode": self.options.pass_mode,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: kv[1]):
            lines.append(Localization.get(locale, "hearts-score-line", player=name, score=score))
        return lines


__all__ = ["HeartsGame", "HeartsPlayer", "HeartsOptions"]