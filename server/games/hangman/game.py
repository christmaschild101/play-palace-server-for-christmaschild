"""
Hangman Game Implementation for PlayPalace.

One player is the word keeper (chosen each round from the built-in bank or a
set word); the others take turns guessing letters. Wrong guesses count
against each guesser; six misses and you're out of the round. The guesser
who completes the word scores a point. If every guesser is out first, the
keeper scores.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet, EditboxInput, Visibility
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.game_status import GameStatus
from ...game_utils.options import IntOption, option_field
from ...messages.localization import Localization
from server.core.ui.keybinds import KeybindState

# Common English words of moderate length (screen-reader friendly)
WORD_BANK = [
    "apple", "breeze", "castle", "dragon", "ember", "forest", "garden",
    "harbor", "island", "jacket", "kitten", "lantern", "meadow", "needle",
    "ocean", "puzzle", "quartz", "river", "silver", "tunnel", "umbrella",
    "valley", "window", "yellow", "zephyr", "anchor", "bottle", "candle",
    "diamond", "elephant", "feather", "guitar", "harvest", "igloo",
    "jungle", "knight", "mirror", "notebook", "orchard", "pencil",
    "quiver", "rocket", "shadow", "tiger", "universe", "victory",
    "whisper", "zebra", "balloon", "chicken",
]

MAX_WRONG = 6


@dataclass
class HangmanPlayer(Player):
    """Player state for Hangman."""

    wrong: int = 0  # Wrong guesses this round
    out: bool = False  # Out of this round (too many wrong guesses)
    score: int = 0  # Points across rounds


@dataclass
class HangmanOptions(GameOptions):
    """Options for Hangman."""

    rounds: int = option_field(
        IntOption(
            default=5,
            min_val=1,
            max_val=20,
            value_key="rounds",
            label="hangman-set-rounds",
            prompt="hangman-enter-rounds",
            change_msg="hangman-option-changed-rounds",
            description="hangman-desc-rounds",
        )
    )
    max_wrong: int = option_field(
        IntOption(
            default=6,
            min_val=3,
            max_val=10,
            value_key="misses",
            label="hangman-set-misses",
            prompt="hangman-enter-misses",
            change_msg="hangman-option-changed-misses",
            description="hangman-desc-misses",
        )
    )


@dataclass
@register_game
class HangmanGame(ActionGuardMixin, Game):
    """Hangman word game."""

    players: list[HangmanPlayer] = field(default_factory=list)
    options: HangmanOptions = field(default_factory=HangmanOptions)
    word: str = ""
    revealed: list[str] = field(default_factory=list)
    guessed: list[str] = field(default_factory=list)
    keeper_id: str = ""
    turn: int = 0

    @classmethod
    def get_name(cls) -> str:
        return "Hangman"

    @classmethod
    def get_type(cls) -> str:
        return "hangman"

    @classmethod
    def get_category(cls) -> str:
        return "category-party-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 6

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> HangmanPlayer:
        """Create a new player."""
        return HangmanPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        for player in self.players:
            player.score = 0
        self._start_round()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    def get_active_players(self) -> list[HangmanPlayer]:  # type: ignore[override]
        """Players who have not been eliminated (spectators excluded)."""
        return [p for p in self.players if not p.is_spectator]

    def _guessers(self) -> list[HangmanPlayer]:
        """Players eligible to guess (not the keeper, not out)."""
        return [p for p in self.get_active_players() if p.id != self.keeper_id and not p.out]

    @property
    def current_player(self) -> "HangmanPlayer | None":  # type: ignore[override]
        """Current guesser by turn index."""
        guessers = self._guessers()
        if not guessers:
            return None
        return guessers[self.turn % len(guessers)]

    def _keeper(self) -> HangmanPlayer | None:
        return self.get_player_by_id(self.keeper_id)

    # ==========================================================================
    # Round flow
    # ==========================================================================

    def _start_round(self) -> None:
        """Begin a new round with a fresh word."""
        self.round += 1
        active = self.get_active_players()
        keeper = active[self.round % len(active)]
        self.keeper_id = keeper.id
        for p in active:
            p.wrong = 0
            p.out = False

        self.word = random.choice(WORD_BANK).upper()  # nosec B311
        self.revealed = ["_"] * len(self.word)
        self.guessed = []
        self.turn = 0

        keeper_user = self.get_user(keeper)
        if keeper_user:
            keeper_user.speak_l(
                "hangman-you-are-keeper",
                word=self.word,
                buffer="table",
            )
        self.broadcast_l(
            "hangman-round-start",
            round=self.round,
            player=keeper.name,
            letters=len(self.word),
        )
        self.play_sound("game_cards/shuffle1.ogg")
        self.play_music("game_pig/mus.ogg")
        self._announce_next_turn()

    def _announce_next_turn(self) -> None:
        """Announce whose turn it is and the current mask."""
        player = self.current_player
        if not player:
            return
        mask = " ".join(self.revealed)
        self.broadcast_personal_l(
            player,
            "hangman-your-turn",
            "hangman-turn-start",
            mask=mask,
        )
        self.rebuild_all_menus()

    def _advance_turn(self) -> None:
        self.turn += 1
        if not self._guessers():
            self._keeper_scores()
            return
        self._announce_next_turn()

    # ==========================================================================
    # Guessing
    # ==========================================================================

    def _apply_guess(self, player: HangmanPlayer, guess: str) -> None:
        """Process a guessed letter or word."""
        guess = guess.strip().upper()
        if not guess:
            return
        if any(not c.isalpha() for c in guess):
            user = self.get_user(player)
            if user:
                user.speak_l("hangman-letters-only")
            return

        if len(guess) == 1:
            letter = guess
            if letter in self.guessed:
                user = self.get_user(player)
                if user:
                    user.speak_l("hangman-already-guessed", letter=letter)
                return
            self.guessed.append(letter)
            if letter in self.word:
                self.revealed = [
                    ch if ch == letter else cur
                    for ch, cur in zip(self.word, self.revealed)
                ]
                self.play_sound("game_cards/draw1.ogg")
                self.broadcast_l("hangman-correct", player=player.name, letter=letter)
                if "_" not in self.revealed:
                    self._word_completed(player)
                    return
            else:
                player.wrong += 1
                self.play_sound("game_pig/lose.ogg")
                guessed_text = Localization.format_list_and(self._locale_for(player), self.guessed)
                self.broadcast_l(
                    "hangman-wrong",
                    player=player.name,
                    wrong=player.wrong,
                    max_wrong=self.options.max_wrong,
                    guessed=guessed_text,
                )
                if player.wrong >= self.options.max_wrong:
                    player.out = True
                    self.broadcast_l("hangman-out", player=player.name)
                    self.play_sound("game_chess/capture2.ogg")
            self._advance_turn()
            return

        # Whole-word guess
        if guess == self.word:
            self.play_sound("game_cards/play1.ogg")
            self.broadcast_l("hangman-solved", player=player.name, word=self.word)
            self._word_completed(player)
        else:
            player.wrong += 1
            self.play_sound("game_pig/lose.ogg")
            self.broadcast_l(
                "hangman-wrong-word",
                player=player.name,
                word=guess,
                wrong=player.wrong,
                max_wrong=self.options.max_wrong,
            )
            if player.wrong >= self.options.max_wrong:
                player.out = True
                self.broadcast_l("hangman-out", player=player.name)
            self._advance_turn()

    def _word_completed(self, player: HangmanPlayer) -> None:
        """A guesser completed the word: they score a point."""
        player.score += 1
        player.out = True  # Can't guess again this round
        self.play_sound("game_pig/win.ogg")
        self.broadcast_l("hangman-word-finished", player=player.name, word=self.word)
        self._end_round()

    def _keeper_scores(self) -> None:
        """All guessers are out: the keeper takes the point."""
        keeper = self._keeper()
        if keeper:
            keeper.score += 1
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("hangman-keeper-wins", player=keeper.name, word=self.word)
        self._end_round()

    def _end_round(self) -> None:
        """Move to the next round or finish the game."""
        active = self.get_active_players()
        if self.round >= self.options.rounds:
            scores = {p.name: p.score for p in active}
            high = max(scores.values()) if scores else 0
            winners = [name for name, s in scores.items() if s == high]
            self.play_sound("game_pig/win.ogg")
            if len(winners) == 1:
                self.broadcast_l("hangman-winner", player=winners[0], score=high)
            else:
                for p in self.players:
                    user = self.get_user(p)
                    if user:
                        names_str = Localization.format_list_and(user.locale, winners)
                        user.speak_l("hangman-tie", players=names_str, score=high, buffer="table")
            self.finish_game()
            return
        keeper = self._keeper()
        self.broadcast_l("hangman-scores", scores=self._scores_text())
        self._start_round()

    def _scores_text(self) -> str:
        names = []
        for p in self.get_active_players():
            names.append(f"{p.name}: {p.score}")
        return ", ".join(names)

    def _locale_for(self, player: Player) -> str:
        user = self.get_user(player)
        return user.locale if user else "en"

    # ==========================================================================
    # Action handlers
    # ==========================================================================

    def _action_guess_letter(self, player: Player, input_value: str, action_id: str) -> None:
        self._apply_guess(player, input_value)  # type: ignore[arg-type]

    def _action_guess_word(self, player: Player, input_value: str, action_id: str) -> None:
        self._apply_guess(player, input_value)  # type: ignore[arg-type]

    # ==========================================================================
    # Declarative action state callbacks
    # ==========================================================================

    def _is_guess_enabled(self, player: Player) -> str | None:
        error = self.guard_turn_action_enabled(player)
        if error:
            return error
        if player.id == self.keeper_id:
            return "hangman-keeper-cannot-guess"
        hp: HangmanPlayer = player  # type: ignore
        if hp.out:
            return "hangman-out-already"
        if "_" not in self.revealed:
            return "hangman-word-done"
        return None

    def _is_guess_hidden(self, player: Player) -> Visibility:
        if player.id == self.keeper_id:
            return Visibility.HIDDEN
        hp: HangmanPlayer = player  # type: ignore
        return self.turn_action_visibility(
            player,
            extra_condition=not hp.out and "_" in self.revealed,
        )

    def _get_guess_label(self, player: Player, action_id: str) -> str:
        user = self.get_user(player)
        locale = user.locale if user else "en"
        hp: HangmanPlayer = player  # type: ignore
        mask = " ".join(self.revealed)
        label_key = "hangman-guess-letter-label" if action_id == "guess_letter" else "hangman-guess-word-label"
        return Localization.get(locale, label_key, mask=mask, wrong=hp.wrong, max_wrong=self.options.max_wrong)

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    # Most frequent English letters, in order
    LETTER_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"

    def _bot_guess_letter(self, player: Player) -> str:
        for letter in self.LETTER_ORDER:
            if letter not in self.guessed:
                return letter
        return "A"

    def _bot_guess_word(self, player: Player) -> str:
        # Only attempt a whole word when the mask is fully determined
        if "_" not in self.revealed:
            return self.word
        if self.revealed.count("_") <= 1:
            for word in WORD_BANK:
                w = word.upper()
                if all(
                    self.revealed[i] == "_" or self.revealed[i] == w[i]
                    for i in range(len(self.word))
                ) and len(w) == len(self.word):
                    return w
        return ""

    def bot_think(self, player: HangmanPlayer) -> str | None:
        """Bot AI: guess a letter (occasionally a word when confident)."""
        if "_" not in self.revealed:
            return None
        if self.revealed.count("_") <= 1 and random.random() < 0.3:  # nosec B311
            return "guess_word"
        return "guess_letter"

    # ==========================================================================
    # Action sets and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: HangmanPlayer) -> ActionSet:
        """Create the turn action set."""
        user = self.get_user(player)
        locale = user.locale if user else "en"

        action_set = ActionSet(name="turn")
        action_set.add(
            Action(
                id="guess_letter",
                label=Localization.get(locale, "hangman-guess-letter"),
                handler="_action_guess_letter",
                is_enabled="_is_guess_enabled",
                is_hidden="_is_guess_hidden",
                get_label="_get_guess_label",
                input_request=EditboxInput(
                    prompt="hangman-enter-letter",
                    default="",
                    bot_input="_bot_guess_letter",
                ),
            )
        )
        action_set.add(
            Action(
                id="guess_word",
                label=Localization.get(locale, "hangman-guess-word"),
                handler="_action_guess_word",
                is_enabled="_is_guess_enabled",
                is_hidden="_is_guess_hidden",
                get_label="_get_guess_label",
                input_request=EditboxInput(
                    prompt="hangman-enter-word",
                    default="",
                    bot_input="_bot_guess_word",
                ),
            )
        )
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.define_keybind("g", "Guess a letter", ["guess_letter"], state=KeybindState.ACTIVE)

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        scores = {p.name: p.score for p in self.get_active_players()}
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
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        final_scores = result.custom_data.get("final_scores", {})
        for name, score in sorted(final_scores.items(), key=lambda kv: -kv[1]):
            lines.append(Localization.get(locale, "hangman-score-line", player=name, score=score))
        return lines


__all__ = ["HangmanGame", "HangmanPlayer", "HangmanOptions"]