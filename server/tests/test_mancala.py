"""
Tests for the Mancala (Kalah) game.
"""

import json

from server.games.mancala.game import MancalaGame, MancalaPlayer, MancalaOptions
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestMancalaUnit:
    """Unit tests for Mancala."""

    def test_game_creation(self):
        game = MancalaGame()
        assert game.get_name() == "Mancala"
        assert game.get_type() == "mancala"
        assert game.get_category() == "category-board-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 2

    def test_player_creation(self):
        game = MancalaGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, MancalaPlayer)

    def test_options_defaults(self):
        game = MancalaGame()
        assert game.options.stones_per_pit == 4

    def test_initial_board(self):
        game = MancalaGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game.board == [4, 4, 4, 4, 4, 4, 0, 4, 4, 4, 4, 4, 4, 0]

    def test_side_start(self):
        game = MancalaGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game._side_start(alice) == 0
        assert game._side_start(bob) == 7

    def test_capture_evaluation(self):
        """A move landing in an own empty pit with stones opposite captures."""
        game = MancalaGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Alice plays pit 4 (index 3); arrange so the move lands in pit 5 empty
        # with stones opposite (index 7).
        game.board = [0, 0, 0, 2, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0]
        game.turn_player_ids = [alice.id, game.players[1].id]
        gain, bonus, captured = game._evaluate_move(alice, 3)
        assert captured == 4  # 3 opposite + own stone
        assert bonus is False

    def test_serialization(self):
        game = MancalaGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.board[0] = 0
        data = json.loads(game.to_json())
        assert data["board"][0] == 0
        loaded = MancalaGame.from_json(game.to_json())
        assert loaded.board == game.board


class TestMancalaPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = MancalaGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 10000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_custom_stones_completes(self):
        game = MancalaGame(options=MancalaOptions(stones_per_pit=5))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 10000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_move_bonus_turn(self):
        """Landing in your own store grants another turn."""
        game = MancalaGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Force a simple layout: pit 0 has exactly 6 stones, so sowing lands
        # the last stone in Alice's store (index 6).
        game.board = [6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        game.game_active = True
        game.status = "playing"
        game.turn = 0
        game.execute_action(alice, "move", input_value="1")
        assert game.current_player == alice
        assert game.board[6] == 1


class TestMancalaPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = MancalaGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = MancalaGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.stones_per_pit == 4