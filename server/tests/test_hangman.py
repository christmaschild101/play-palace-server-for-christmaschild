"""
Tests for the Hangman game.
"""

import json

from server.games.hangman.game import HangmanGame, HangmanPlayer, HangmanOptions
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestHangmanUnit:
    """Unit tests for Hangman."""

    def test_game_creation(self):
        game = HangmanGame()
        assert game.get_name() == "Hangman"
        assert game.get_type() == "hangman"
        assert game.get_category() == "category-party-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 6

    def test_player_creation(self):
        game = HangmanGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, HangmanPlayer)

    def test_options_defaults(self):
        game = HangmanGame()
        assert game.options.rounds == 5
        assert game.options.max_wrong == 6

    def test_round_start(self):
        game = HangmanGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game.round == 1
        assert game.word
        assert "_" in game.revealed
        assert game.keeper_id in {p.id for p in game.players}

    def test_correct_guess_reveals(self):
        game = HangmanGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.word = "APPLE"
        game.revealed = ["_", "_", "_", "_", "_"]
        game._apply_guess(alice, "p")
        assert game.revealed == ["_", "P", "P", "_", "_"]

    def test_wrong_guess_counts(self):
        game = HangmanGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.word = "APPLE"
        game.revealed = ["_"] * 5
        game._apply_guess(alice, "z")
        assert alice.wrong == 1
        assert "_" in game.revealed

    def test_word_solve_scores(self):
        game = HangmanGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.word = "APPLE"
        game.revealed = ["_"] * 5
        game._apply_guess(alice, "apple")
        assert alice.score == 1

    def test_elimination_on_max_wrong(self):
        game = HangmanGame(options=HangmanOptions(max_wrong=3))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.word = "APPLE"
        for letter in "xyz":
            game._apply_guess(alice, letter)
        assert alice.out is True

    def test_serialization(self):
        game = HangmanGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert data["word"]
        loaded = HangmanGame.from_json(game.to_json())
        assert loaded.word == game.word
        assert loaded.revealed == game.revealed


class TestHangmanPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = HangmanGame(options=HangmanOptions(rounds=2))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_with_bot_completes(self):
        game = HangmanGame(options=HangmanOptions(rounds=2))
        user = MockUser("Alice")
        game.add_player("Alice", user)
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        # Alice takes a letter guess when it's her turn
        if game.current_player and game.current_player.name == "Alice":
            game.execute_action(game.current_player, "guess_letter", input_value="a")
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"


class TestHangmanPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = HangmanGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = HangmanGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.rounds == 5