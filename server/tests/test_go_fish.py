"""
Tests for the Go Fish game.
"""

import json

from server.games.go_fish.game import GoFishGame, GoFishPlayer, GoFishOptions
from server.game_utils.cards import Card
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestGoFishUnit:
    """Unit tests for Go Fish."""

    def test_game_creation(self):
        game = GoFishGame()
        assert game.get_name() == "Go Fish"
        assert game.get_type() == "go_fish"
        assert game.get_category() == "category-card-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 6

    def test_player_creation(self):
        game = GoFishGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, GoFishPlayer)

    def test_options_defaults(self):
        game = GoFishGame()
        assert game.options.books_to_win == 5

    def test_dealing_two_players(self):
        game = GoFishGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert len(game.players[0].hand) == 7
        assert len(game.players[1].hand) == 7
        assert game.deck.size() == 52 - 14

    def test_dealing_six_players(self):
        game = GoFishGame()
        for i in range(6):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.on_start()
        assert all(len(p.hand) == 5 for p in game.players)

    def test_book_detection(self):
        game = GoFishGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.hand = [
            Card(id=i, rank=7, suit=1) for i in range(4)
        ]
        game._check_books(player)
        assert player.books == 1
        assert player.hand == []

    def test_book_two_kinds(self):
        game = GoFishGame()
        player = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        player.hand = [Card(id=i, rank=2, suit=1) for i in range(4)]
        player.hand += [Card(id=10 + i, rank=9, suit=2) for i in range(4)]
        game._check_books(player)
        assert player.books == 2

    def test_serialization(self):
        game = GoFishGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"][0]["hand"]) == 7
        loaded = GoFishGame.from_json(game.to_json())
        assert len(loaded.players[0].hand) == 7
        assert loaded.deck.size() == 52 - 14


class TestGoFishPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = GoFishGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_four_bot_game_completes(self):
        game = GoFishGame()
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_query_transfer(self):
        """Asking for a rank another player holds transfers it and keeps the turn."""
        game = GoFishGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        # Give Alice a 5 and Bob three 5s, strip the rest of Bob's hand
        alice.hand = [Card(id=100, rank=5, suit=1)]
        bob.hand = [Card(id=101 + i, rank=5, suit=i + 1) for i in range(3)]
        game.turn_player_ids = [alice.id, bob.id]
        game.turn = 0
        game._resolve_query(alice, bob, 5)
        assert alice.books == 1
        assert len(alice.hand) == 0


class TestGoFishPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = GoFishGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = GoFishGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.books_to_win == 5
        assert len(loaded.players[0].hand) == 7