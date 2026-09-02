"""
Tests for the Liar's Dice game.
"""

import json

from server.games.liarsdice.game import LiarsDiceGame, LiarsDicePlayer, LiarsDiceOptions
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestLiarsDiceUnit:
    """Unit tests for Liar's Dice."""

    def test_game_creation(self):
        game = LiarsDiceGame()
        assert game.get_name() == "Liar's Dice"
        assert game.get_type() == "liarsdice"
        assert game.get_category() == "category-dice-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 6

    def test_player_creation(self):
        game = LiarsDiceGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, LiarsDicePlayer)

    def test_options_defaults(self):
        game = LiarsDiceGame()
        assert game.options.wild_ones is True

    def test_deal_five_dice(self):
        game = LiarsDiceGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert len(game.players[0].dice) == 5
        assert len(game.players[1].dice) == 5

    def test_bid_ordering(self):
        game = LiarsDiceGame()
        assert game._bid_beats_current(3, 6) is True  # no current bid
        game.bid_qty = 3
        game.bid_face = 4
        assert game._bid_beats_current(3, 5) is True
        assert game._bid_beats_current(3, 4) is False
        assert game._bid_beats_current(2, 6) is False
        assert game._bid_beats_current(4, 2) is True

    def test_wild_ones_counted(self):
        game = LiarsDiceGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.dice = [1, 1, 2, 4, 6]
        counts = game._my_face_counts(alice)
        assert counts[2] == 3  # two wilds + one 2

    def test_challenge_loser_loses_die(self):
        game = LiarsDiceGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Alice bids 4 sixes; the dice say otherwise, so Alice (bidder) loses
        alice.dice = [1, 2, 3, 4, 5]
        bob.dice = [2, 3, 4, 5, 6]
        game.bid_qty = 4
        game.bid_face = 6
        game.bidder_id = alice.id
        game._resolve_challenge(bob)
        assert len(alice.dice) == 4
        assert bob.eliminated is False

    def test_challenge_truth_bidder_keeps_die(self):
        game = LiarsDiceGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.dice = [1, 5, 5, 5, 5]
        bob.dice = [2, 3, 4, 5, 6]
        game.bid_qty = 3
        game.bid_face = 5
        game.bidder_id = alice.id
        game._resolve_challenge(bob)
        # 4 fives + wild one = 5 >= 3, bidder was right: challenger loses
        assert len(bob.dice) == 4
        assert len(alice.dice) == 5

    def test_wild_ones_off(self):
        game = LiarsDiceGame(options=LiarsDiceOptions(wild_ones=False))
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.dice = [1, 5, 5, 5, 5]
        bob.dice = [2, 3, 4, 5, 6]
        game.bid_qty = 3
        game.bid_face = 5
        game.bidder_id = alice.id
        game._resolve_challenge(bob)
        # 4 fives (no wild) >= 3: challenger still loses
        assert len(bob.dice) == 4

    def test_leaderboard_types(self):
        boards = LiarsDiceGame.get_leaderboard_types()
        assert any(
            c["id"] == "dice_remaining"
            and c["path"] == "dice_left.{player_name}"
            and c["aggregate"] == "avg"
            for c in boards
        )

    def test_result_carries_dice_left(self):
        game = LiarsDiceGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.players[0].dice = [2, 3]
        result = game.build_game_result()
        assert result.custom_data["dice_left"]["Alice"] == 2

    def test_serialization(self):
        game = LiarsDiceGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"][0]["dice"]) == 5
        loaded = LiarsDiceGame.from_json(game.to_json())
        assert len(loaded.players[0].dice) == 5
        assert loaded.bid_qty == 0


class TestLiarsDicePlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = LiarsDiceGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_three_bot_game_completes(self):
        game = LiarsDiceGame()
        for i in range(3):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"


class TestLiarsDicePersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = LiarsDiceGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.bid_qty = 2
        game.bid_face = 4
        saved = game.to_json()
        loaded = LiarsDiceGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.bid_qty == 2
        assert loaded.bid_face == 4