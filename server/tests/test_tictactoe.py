"""
Tests for the Tic-Tac-Toe game.
"""

import json

from server.games.tictactoe.game import (
    TicTacToeGame,
    TicTacToePlayer,
    TicTacToeOptions,
)
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestTicTacToeUnit:
    """Unit tests for Tic-Tac-Toe."""

    def test_game_creation(self):
        game = TicTacToeGame()
        assert game.get_name() == "Tic-Tac-Toe"
        assert game.get_type() == "tictactoe"
        assert game.get_category() == "category-board-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 2

    def test_player_creation(self):
        game = TicTacToeGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, TicTacToePlayer)

    def test_winner_detection(self):
        assert TicTacToeGame._winner_of(["X", "X", "X", "", "", "", "", "", ""]) == "X"
        assert TicTacToeGame._winner_of(["O", "", "", "O", "", "", "O", "", ""]) == "O"
        assert TicTacToeGame._winner_of(["X", "", "", "", "X", "", "", "", "X"]) == "X"
        assert TicTacToeGame._winner_of(["X", "", "O", "", "X", "", "O", "", ""]) is None

    def test_serialization(self):
        game = TicTacToeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.board = ["X", "O", "", "", "", "", "", "", ""]
        data = json.loads(game.to_json())
        assert data["board"][0] == "X"
        loaded = TicTacToeGame.from_json(game.to_json())
        assert loaded.board[1] == "O"
        assert loaded.grid_rows == 3

    def test_marker_assignment(self):
        game = TicTacToeGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game._marker_for_player(alice) == "X"
        assert game._marker_for_player(bob) == "O"

    def test_cell_labels_localized(self):
        game = TicTacToeGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        label = game.get_cell_label(0, 0, player, "en")
        assert "A1" in label
        game.board[0] = "X"
        label = game.get_cell_label(0, 0, player, "en")
        assert "X" in label


class TestTicTacToePlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = TicTacToeGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 2000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_vs_bot_completes(self):
        game = TicTacToeGame()
        user = MockUser("Alice")
        game.add_player("Alice", user)
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        # Alice plays the center as her first move
        game.execute_action(game.players[0], "grid_cell_1_1")
        max_ticks = 2000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_draw_detection(self):
        game = TicTacToeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        assert game._winner_of(game.board) is None
        assert all(game.board)


class TestTicTacToePersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = TicTacToeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.execute_action(game.players[0], "grid_cell_0_0")
        saved = game.to_json()
        loaded = TicTacToeGame.from_json(saved)
        assert loaded.board[0] == "X"
        assert loaded.game_active is True