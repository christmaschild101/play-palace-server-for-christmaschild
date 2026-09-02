"""
Go Fish Game Implementation for PlayPalace.

Classic card game: ask other players for a rank you hold. If they have it,
you take all of it and go again; if not, you draw (go fish). Four of a kind
makes a book. First player to the book target wins; otherwise the most
books when the deck runs out (or a hand empties) wins.
"""

from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet, MenuInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.cards import Card, Deck, DeckFactory, RANK_KEYS
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState


@dataclass
class GoFishPlayer(Player):
    """Player state for Go Fish."""

    hand: list[Card] = field(default_factory=list)
    books: int = 0
    asking_rank: int | None = None  # Set while choosing whom to ask


@dataclass
class GoFishOptions(GameOptions):
    """Options for Go Fish."""

    books_to_win: int = option_field(
        IntOption(
            default=5,
            min_val=2,
            max_val=10,
            value_key="books",
            label="gofish-set-books",
            prompt="gofish-enter-books",
            change_msg="gofish-option-changed-books",
            description="gofish-desc-books",
        )
    )


@dataclass
@register_game
class GoFishGame(ActionGuardMixin, Game):
    """Go Fish card game."""

    players: list[GoFishPlayer] = field(default_factory=list)
    options: GoFishOptions = field(default_factory=GoFishOptions)
    deck: Deck = field(default_factory=Deck)
    turn: int = 0  # Current player index

    @classmethod
    def get_name(cls) -> str:
        return "Go Fish"

    @classmethod
    def get_type(cls) -> str:
        return "go_fish"

    @classmethod
    def get_category(cls) -> str:
        return "category-card-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> GoFishPlayer:
        """Create a new player."""
        return GoFishPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game: shuffle and deal."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        self.deck, _ = DeckFactory.standard_deck()
        active = self.get_active_players()
        self.set_turn_players(active)
        self.turn = 0

        hand_size = 7 if len(active) <= 3 else 5
        for player in active:
            player.hand = self.deck.draw(hand_size)
            player.books = 0
            player.asking_rank = None

        self.play_sound("game_cards/shuffle1.ogg")
        self.broadcast_l("gofish-dealt", cards=hand_size)
        self._announce_turn()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def get_active_players(self) -> list[GoFishPlayer]:
        """Override return type for convenience."""
        return [p for p in self.players if not p.is_spectator]

    @property
    def current_player(self) -> "GoFishPlayer | None":  # type: ignore[override]
        """Current player by turn index."""
        active = self.get_active_players()
        if not active:
            return None
        return active[self.turn % len(active)]

    def _advance_turn(self) -> None:
        """Move to the next player and reset ask state."""
        for p in self.players:
            p.asking_rank = None
        self.turn += 1
        self._announce_turn()
        self.rebuild_all_menus()

    def _announce_turn(self) -> None:
        self.announce_turn()

    # ==========================================================================
    # Localization helpers
    # ==========================================================================

    def _rank_name(self, rank: int, locale: str) -> str:
        key = RANK_KEYS.get(rank)
        return Localization.get(locale, key) if key else str(rank)

    def _broadcast_ranked(self, message_id: str, rank: int, **kwargs) -> None:
        """Broadcast a localized message with a per-locale rank name."""
        for p in self.players:
            user = self.get_user(p)
            if user:
                user.speak_l(message_id, buffer="table", rank=self._rank_name(rank, user.locale), **kwargs)

    # ==========================================================================
    # Core game logic
    # ==========================================================================

    def _check_books(self, player: GoFishPlayer) -> bool:
        """Turn any 4-of-a-kind into a book. Returns True if a book was made."""
        counts = Counter(card.rank for card in player.hand)
        made = False
        for rank, count in counts.items():
            while count >= 4:
                to_remove = 4
                new_hand: list[Card] = []
                for card in player.hand:
                    if card.rank == rank and to_remove > 0:
                        to_remove -= 1
                    else:
                        new_hand.append(card)
                player.hand = new_hand
                player.books += 1
                count -= 4
                made = True
                self.play_sound("game_cards/discard1.ogg")
                self._broadcast_ranked("gofish-book", rank, player=player.name)
        return made

    def _resolve_query(self, player: GoFishPlayer, target: GoFishPlayer, rank: int) -> None:
        """Execute the ask: transfer cards, else go fish."""
        given = [c for c in target.hand if c.rank == rank]
        if given:
            self.play_sound("game_cards/play1.ogg")
            self._broadcast_ranked(
                "gofish-gave", rank, asker=player.name, target=target.name, count=len(given)
            )
            target.hand = [c for c in target.hand if c.rank != rank]
            player.hand.extend(given)
            self._check_books(player)
            # Asker goes again (books may have emptied the hand)
            if self._check_game_over(player):
                return
            user = self.get_user(player)
            if user:
                user.speak_l("gofish-ask-again")
            self.rebuild_all_menus()
            return

        # Go fish
        self.play_sound("game_cards/draw1.ogg")
        self.broadcast_l("gofish-go-fish", player=player.name, target=target.name)
        if self.deck.is_empty():
            self._finish_game()
            return
        drawn = self.deck.draw_one()
        if drawn:
            player.hand.append(drawn)
            self._check_books(player)
            if drawn.rank == rank:
                self._broadcast_ranked("gofish-fished-wanted", rank, player=player.name)
                if self._check_game_over(player):
                    return
                self.rebuild_all_menus()
                return
            self._broadcast_ranked("gofish-fished", rank, player=player.name)
            if self._check_game_over(player):
                return
        self._advance_turn()

    def _check_game_over(self, player: GoFishPlayer) -> bool:
        """Return True and finish the game if it should end now."""
        active = self.get_active_players()
        if player.books >= self.options.books_to_win:
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("gofish-winner-books", player=player.name, books=player.books)
            self.finish_game()
            return True
        if self.deck.is_empty():
            self._finish_game()
            return True
        if any(not p.hand for p in active):
            self._finish_game()
            return True
        return False

    def _finish_game(self) -> None:
        """Finish by most books."""
        active = self.get_active_players()
        high = max((p.books for p in active), default=0)
        winners = [p.name for p in active if p.books == high]
        self.play_sound("game_pig/win.ogg")
        if len(winners) == 1:
            self.broadcast_l("gofish-winner", player=winners[0], books=high)
        else:
            for p in self.players:
                user = self.get_user(p)
                if user:
                    names_str = Localization.format_list_and(user.locale, winners)
                    user.speak_l("gofish-tie", players=names_str, books=high, buffer="table")
        self.finish_game()

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_ask(self, player: Player, input_value: str, action_id: str) -> None:
        """First step of asking: pick a rank, then pick a target."""
        gf_player: GoFishPlayer = player  # type: ignore
        try:
            gf_player.asking_rank = int(input_value)
        except ValueError:
            return
        self.update_player_menu(player)

    def _action_ask_player(self, player: Player, input_value: str, action_id: str) -> None:
        """Second step: pick the player to ask."""
        gf_player: GoFishPlayer = player  # type: ignore
        rank = gf_player.asking_rank
        if rank is None:
            return
        gf_player.asking_rank = None
        target = self.get_player_by_name(input_value)
        if target is None or target is player or target.is_spectator:
            return
        self._resolve_query(gf_player, target, rank)

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_ask_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        gf_player: GoFishPlayer = player  # type: ignore
        if not gf_player.hand:
            return "gofish-no-cards"
        return None

    def _is_ask_hidden(self, player: Player) -> Visibility:
        gf_player: GoFishPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=gf_player.asking_rank is None)

    def _is_ask_player_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        gf_player: GoFishPlayer = player  # type: ignore
        if gf_player.asking_rank is None:
            return "gofish-pick-rank-first"
        return None

    def _is_ask_player_hidden(self, player: Player) -> Visibility:
        gf_player: GoFishPlayer = player  # type: ignore
        return self.turn_action_visibility(player, extra_condition=gf_player.asking_rank is not None)

    def _get_ask_label(self, player: Player, action_id: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        gf_player: GoFishPlayer = player  # type: ignore
        if gf_player.asking_rank is not None:
            return Localization.get(locale, "gofish-ask-rank", rank=self._rank_name(gf_player.asking_rank, locale))
        return Localization.get(locale, "gofish-ask")

    # ==========================================================================
    # Menu input helpers
    # ==========================================================================

    def _rank_options(self, player: Player) -> list[str]:
        gf_player: GoFishPlayer = player  # type: ignore
        ranks = sorted({card.rank for card in gf_player.hand})
        return [str(r) for r in ranks]

    def _rank_option_label(self, player: Player, option: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        return self._rank_name(int(option), locale)

    def _target_options(self, player: Player) -> list[str]:
        return [p.name for p in self.get_active_players() if p is not player]

    def _bot_select_rank(self, player: Player, options: list[str]) -> str | None:
        """Bot asks for its most common held rank."""
        gf_player: GoFishPlayer = player  # type: ignore
        counts = Counter(card.rank for card in gf_player.hand)
        if not counts:
            return options[0] if options else None
        best_rank = max(counts, key=counts.get)
        best_str = str(best_rank)
        return best_str if best_str in options else options[0]

    def _bot_select_target(self, player: Player, options: list[str]) -> str | None:
        """Bot asks the player holding the most cards."""
        others = [p for p in self.get_active_players() if p is not player and p.name in options]
        if not others:
            return options[0] if options else None
        return max(others, key=lambda p: len(p.hand)).name

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: GoFishPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="ask",
                label=Localization.get(locale, "gofish-ask"),
                handler="_action_ask",
                is_enabled="_is_ask_enabled",
                is_hidden="_is_ask_hidden",
                get_label="_get_ask_label",
                input_request=MenuInput(
                    prompt="gofish-pick-rank",
                    options="_rank_options",
                    option_label="_rank_option_label",
                    bot_select="_bot_select_rank",
                ),
            )
        )
        action_set.add(
            Action(
                id="ask_player",
                label=Localization.get(locale, "gofish-ask-whom"),
                handler="_action_ask_player",
                is_enabled="_is_ask_player_enabled",
                is_hidden="_is_ask_player_hidden",
                input_request=MenuInput(
                    prompt="gofish-pick-player",
                    options="_target_options",
                    bot_select="_bot_select_target",
                ),
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("a", "Ask", ["ask"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def bot_think(self, player: GoFishPlayer) -> str | None:
        """Bot AI: ask a rank, then pick a target."""
        if player.asking_rank is None:
            return "ask"
        return "ask_player"

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        active = self.get_active_players()
        books = {p.name: p.books for p in active}
        winner_name = max(books, key=books.get) if books else None

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
                "winner_books": books.get(winner_name, 0) if winner_name else 0,
                "books": books,
                "books_to_win": self.options.books_to_win,
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        books = result.custom_data.get("books", {})
        for name, count in sorted(books.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "gofish-score-line", player=name, books=count))
        return lines


__all__ = ["GoFishGame", "GoFishPlayer", "GoFishOptions"]