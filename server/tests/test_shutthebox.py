"""
Tests for the Shut the Box game.
"""

import json

from server.games.shutthebox.game import (
    ShutTheBoxGame,
    ShutTheBoxPlayer,
    ShutTheBoxOptions,
)
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestShutTheBoxUnit:
    """Unit tests for Shut the Box."""

    def test_game_creation(self):
        game = ShutTheBoxGame()
        assert game.get_name() == "Shut the Box"
        assert game.get_type() == "shutthebox"
        assert game.get_category() == "category-dice-games"
        assert game.get_min_players() == 1
        assert game.get_max_players() == 4

    def test_player_creation(self):
        game = ShutTheBoxGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, ShutTheBoxPlayer)

    def test_options_defaults(self):
        game = ShutTheBoxGame()
        assert game.options.rounds == 1
        assert game.options.single_die_rule is True

    def test_combos(self):
        game = ShutTheBoxGame()
        game.add_player("Alice", MockUser("Alice"))
        player = game.add_player("Bob", MockUser("Bob"))
        player.tiles = [1, 2, 3, 4]
        combos = game._combos(player, 4)
        assert [4] in combos
        assert [1, 3] in combos

    def test_combos_empty_when_impossible(self):
        game = ShutTheBoxGame()
        game.add_player("Alice", MockUser("Alice"))
        player = game.add_player("Bob", MockUser("Bob"))
        player.tiles = [1, 2]
        assert game._combos(player, 5) == []

    def test_serialization(self):
        game = ShutTheBoxGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.round = 1
        data = json.loads(game.to_json())
        assert data["round"] == 1
        loaded = ShutTheBoxGame.from_json(game.to_json())
        assert loaded.round == 1
        assert loaded.players[0].tiles == list(range(1, 13))


class TestShutTheBoxPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = ShutTheBoxGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_three_round_game_completes(self):
        game = ShutTheBoxGame(options=ShutTheBoxOptions(rounds=3))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"
        assert game.round == 3

    def test_single_player_completes(self):
        game = ShutTheBoxGame()
        game.add_player("Alice", MockUser("Alice"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_close_action_removes_tiles(self):
        game = ShutTheBoxGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Force a roll of [3, 1] (total 4) and close 1+3
        game.players[0].dice = [3, 1]
        game.execute_action(alice, "close", input_value="3+1")
        assert 3 not in game.players[0].tiles
        assert 1 not in game.players[0].tiles
        assert game.players[0].dice == []

    def test_bust_scores_open_sum(self):
        from unittest.mock import patch

        game = ShutTheBoxGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Only tile 12 open (max > 6 so two dice); a roll totalling 7 is impossible
        game.players[0].tiles = [12]
        with patch("server.games.shutthebox.game.random.randint", side_effect=[5, 2]):
            game.execute_action(alice, "roll")
        assert game.status == "playing"
        assert game.players[0].total_score == 12


class TestShutTheBoxPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = ShutTheBoxGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.players[0].tiles = [5, 6]
        saved = game.to_json()
        loaded = ShutTheBoxGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.players[0].tiles == [5, 6]