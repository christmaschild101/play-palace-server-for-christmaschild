"""
Tests for the Reversi game.
"""

import json

from server.games.reversi.game import ReversiGame, ReversiPlayer, _idx
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestReversiUnit:
    """Unit tests for Reversi."""

    def test_game_creation(self):
        game = ReversiGame()
        assert game.get_name() == "Reversi"
        assert game.get_type() == "reversi"
        assert game.get_category() == "category-board-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 2

    def test_player_creation(self):
        game = ReversiGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, ReversiPlayer)

    def test_initial_setup(self):
        game = ReversiGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game.board[_idx(3, 3)] == "W"
        assert game.board[_idx(3, 4)] == "B"
        assert game.board[_idx(4, 3)] == "B"
        assert game.board[_idx(4, 4)] == "W"
        assert game._count_discs("B") == 2
        assert game._count_discs("W") == 2

    def test_initial_legal_moves(self):
        game = ReversiGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        legal = game._legal_moves("B")
        assert legal == {_idx(2, 3), _idx(3, 2), _idx(4, 5), _idx(5, 4)}

    def test_apply_move_flips(self):
        game = ReversiGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        flips = game._apply_move(_idx(2, 3), "B")
        assert flips == 1
        assert game.board[_idx(3, 3)] == "B"
        assert game.board[_idx(2, 3)] == "B"

    def test_marker_assignment(self):
        game = ReversiGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game._marker_for_player(alice) == "B"
        assert game._marker_for_player(bob) == "W"

    def test_serialization(self):
        game = ReversiGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert data["board"][_idx(3, 3)] == "W"
        loaded = ReversiGame.from_json(game.to_json())
        assert loaded.board == game.board
        assert loaded.grid_rows == 8


class TestReversiPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = ReversiGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_first_move(self):
        game = ReversiGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        game.execute_action(alice, "grid_cell_2_3")
        assert game.board[_idx(2, 3)] == "B"
        assert game.board[_idx(3, 3)] == "B"


class TestReversiPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = ReversiGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = ReversiGame.from_json(saved)
        assert loaded.game_active is True