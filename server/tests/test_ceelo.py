"""
Tests for the Cee-lo game.
"""

import json

from server.games.ceelo.game import CeeLoGame, CeeLoPlayer, CeeLoOptions
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestCeeLoUnit:
    """Unit tests for Cee-lo."""

    def test_game_creation(self):
        game = CeeLoGame()
        assert game.get_name() == "Cee-lo"
        assert game.get_type() == "ceelo"
        assert game.get_category() == "category-dice-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 8

    def test_player_creation(self):
        game = CeeLoGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, CeeLoPlayer)

    def test_options_defaults(self):
        game = CeeLoGame()
        assert game.options.ante == 10
        assert game.options.rounds == 10

    def test_evaluate_best(self):
        game = CeeLoGame()
        rank, key = game.evaluate_roll([4, 5, 6])
        assert rank == 0
        assert key == "ceelo-best"

    def test_evaluate_trips(self):
        game = CeeLoGame()
        rank, key = game.evaluate_roll([4, 4, 4])
        assert rank == 1
        assert key == "ceelo-trips"

    def test_evaluate_point(self):
        game = CeeLoGame()
        rank, key = game.evaluate_roll([2, 2, 5])
        assert rank == 2
        assert key == "ceelo-point-5"
        rank, key = game.evaluate_roll([4, 3, 4])
        assert rank == 2
        assert key == "ceelo-point-3"

    def test_evaluate_worst(self):
        game = CeeLoGame()
        rank, key = game.evaluate_roll([1, 2, 3])
        assert rank == 3
        assert key == "ceelo-worst"

    def test_evaluate_no_combo(self):
        game = CeeLoGame()
        rank, key = game.evaluate_roll([1, 4, 6])
        assert rank is None
        assert key == "ceelo-no-combo"

    def test_combo_sort_key(self):
        """Trips 6-6-6 beat trips 2-2-2; points 6 beat points 2."""
        game = CeeLoGame()
        p1 = CeeLoPlayer(id="a", name="A", dice=[6, 6, 6], combo_rank=1)
        p2 = CeeLoPlayer(id="b", name="B", dice=[2, 2, 2], combo_rank=1)
        assert game._combo_sort_key(p1) < game._combo_sort_key(p2)
        p3 = CeeLoPlayer(id="c", name="C", dice=[2, 2, 6], combo_rank=2)
        p4 = CeeLoPlayer(id="d", name="D", dice=[5, 5, 2], combo_rank=2)
        assert game._combo_sort_key(p3) < game._combo_sort_key(p4)

    def test_leaderboard_types(self):
        boards = CeeLoGame.get_leaderboard_types()
        assert any(
            c["id"] == "total_winnings"
            and c["path"] == "final_scores.{player_name}"
            and c["aggregate"] == "sum"
            for c in boards
        )

    def test_serialization(self):
        game = CeeLoGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.round = 3
        data = json.loads(game.to_json())
        assert data["round"] == 3
        loaded = CeeLoGame.from_json(game.to_json())
        assert loaded.round == 3


class TestCeeLoPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = CeeLoGame(options=CeeLoOptions(rounds=3, ante=10))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_five_bot_game_completes(self):
        game = CeeLoGame(options=CeeLoOptions(rounds=2))
        for i in range(5):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"


class TestCeeLoPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = CeeLoGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = CeeLoGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.ante == 10