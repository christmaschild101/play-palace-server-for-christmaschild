"""
Tests for the Can't Stop game.
"""

import json

from server.games.cantstop.game import CanTStopGame, CanTStopPlayer, CanTStopOptions
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestCanTStopUnit:
    """Unit tests for Can't Stop."""

    def test_game_creation(self):
        game = CanTStopGame()
        assert game.get_name() == "Can't Stop"
        assert game.get_type() == "cantstop"
        assert game.get_category() == "category-dice-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 4

    def test_player_creation(self):
        game = CanTStopGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, CanTStopPlayer)

    def test_options_defaults(self):
        game = CanTStopGame()
        assert game.options.win_tracks == 3
        assert game.track_height == 3

    def test_partitions(self):
        game = CanTStopGame()
        partitions = set(game._partitions([2, 3, 4, 5]))
        assert (5, 9) in partitions
        assert (6, 8) in partitions
        assert (7, 7) in partitions
        assert len(partitions) == 3

    def test_winning_tracks(self):
        game = CanTStopGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.progress = [0] * 11
        player.progress[0] = 3  # track 2
        player.progress[5] = 2  # track 7
        player.markers[5] = 1  # tops track 7
        assert game._winning_tracks(player) == 2

    def test_valid_partitions_respects_full_tracks(self):
        game = CanTStopGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.progress[5] = 3  # track 7 is full
        player.dice = [2, 5, 2, 5]  # partitions: (7,7),(7,7),(4,10)
        valid = game._valid_partitions(player)
        assert all(7 not in pair for pair in valid)

    def test_marker_limit(self):
        """Three markers mean a fourth track cannot be started."""
        game = CanTStopGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.markers[0] = 1  # track 2
        player.markers[1] = 1  # track 3
        player.markers[2] = 1  # track 4
        player.dice = [1, 1, 2, 2]
        valid = game._valid_partitions(player)
        assert valid
        for pair in valid:
            for value in pair:
                assert player.markers[value - 2] > 0

    def test_all_new_tracks_invalid_with_full_markers(self):
        game = CanTStopGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.markers[0] = 1  # track 2
        player.markers[1] = 1  # track 3
        player.markers[2] = 1  # track 4
        player.dice = [1, 6, 1, 6]  # only (2,12) and (7,7) - all need a new track
        assert game._valid_partitions(player) == []

    def test_serialization(self):
        game = CanTStopGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"]) == 2
        loaded = CanTStopGame.from_json(game.to_json())
        assert loaded.track_height == 3


class TestCanTStopPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = CanTStopGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 50000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_win_on_three_tracks(self):
        """Topping three tracks ends the game immediately."""
        game = CanTStopGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.progress = [0] * 11
        alice.progress[0] = 3
        alice.progress[1] = 3
        alice.markers[2] = 2  # about to top track 4 (index 2)
        alice.dice = [2, 2, 2, 2]  # only partition (4, 4)
        game.game_active = True
        game.status = "playing"
        game.turn = 0
        game.execute_action(alice, "choose", input_value="4+4")
        assert game.status == "finished"


class TestCanTStopPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = CanTStopGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = CanTStopGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.win_tracks == 3