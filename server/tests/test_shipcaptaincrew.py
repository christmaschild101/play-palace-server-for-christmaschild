"""
Tests for the Ship, Captain & Crew game.
"""

import json

from server.games.shipcaptaincrew.game import (
    ShipCaptainCrewGame,
    ShipCaptainCrewPlayer,
    ShipCaptainCrewOptions,
)
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestShipCaptainCrewUnit:
    """Unit tests for Ship, Captain & Crew."""

    def test_game_creation(self):
        game = ShipCaptainCrewGame()
        assert game.get_name() == "Ship, Captain & Crew"
        assert game.get_type() == "shipcaptaincrew"
        assert game.get_category() == "category-dice-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 6

    def test_player_creation(self):
        game = ShipCaptainCrewGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert player.rolls_left == 3
        assert player.dice == [0, 0, 0, 0, 0]
        assert isinstance(player, ShipCaptainCrewPlayer)

    def test_options_defaults(self):
        game = ShipCaptainCrewGame()
        assert game.options.target_score == 21
        assert game.options.rounds == 0

    def test_kept_indices(self):
        game = ShipCaptainCrewGame()
        game.add_player("Alice", MockUser("Alice"))
        player = game.add_player("Bob", MockUser("Bob"))
        player.dice = [4, 6, 5, 2, 3]
        assert game._kept_indices(player) == [1, 2, 0]

    def test_turn_score_requires_full_crew(self):
        game = ShipCaptainCrewGame()
        game.add_player("Alice", MockUser("Alice"))
        player = game.add_player("Bob", MockUser("Bob"))
        player.dice = [6, 5, 2, 2, 2]
        assert game._turn_score(player) == 0
        player.dice = [6, 5, 4, 2, 3]
        assert game._turn_score(player) == 5

    def test_roll_keeps_set_aside_dice(self):
        game = ShipCaptainCrewGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        player.dice = [6, 5, 4, 1, 1]
        player.rolls_left = 2
        user.clear_messages()
        game.execute_action(player, "roll")
        # Kept values persist
        assert all(v in player.dice for v in (6, 5, 4))
        assert player.rolls_left == 1

    def test_serialization(self):
        game = ShipCaptainCrewGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.round = 2
        data = json.loads(game.to_json())
        assert data["round"] == 2
        loaded = ShipCaptainCrewGame.from_json(game.to_json())
        assert loaded.round == 2

    def test_custom_options(self):
        options = ShipCaptainCrewOptions(target_score=50, rounds=3)
        game = ShipCaptainCrewGame(options=options)
        assert game.options.target_score == 50
        assert game.options.rounds == 3


class TestShipCaptainCrewPlay:
    """Integration tests for complete game play."""

    def test_two_player_game_completes(self):
        game = ShipCaptainCrewGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_four_player_game_completes(self):
        game = ShipCaptainCrewGame()
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_fixed_rounds_completes(self):
        game = ShipCaptainCrewGame(options=ShipCaptainCrewOptions(rounds=2))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 20000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"