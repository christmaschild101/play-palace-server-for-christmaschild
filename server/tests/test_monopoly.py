"""
Tests for the Monopoly game.
"""

import json

from server.games.monopoly.game import (
    MonopolyGame,
    MonopolyPlayer,
    MonopolyOptions,
    PROPERTY_PRICES,
    SPACE_NAMES,
)
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


class TestMonopolyUnit:
    """Unit tests for Monopoly."""

    def test_game_creation(self):
        game = MonopolyGame()
        assert game.get_name() == "Monopoly"
        assert game.get_type() == "monopoly"
        assert game.get_category() == "category-board-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 8

    def test_player_creation(self):
        game = MonopolyGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, MonopolyPlayer)

    def test_options_defaults(self):
        game = MonopolyGame()
        assert game.options.starting_money == 1500
        assert game.options.max_rounds == 0

    def test_board_structure(self):
        assert len(SPACE_NAMES) == 40
        assert PROPERTY_PRICES[1] == 60
        assert PROPERTY_PRICES[39] == 400
        # 22 properties, 4 railroads, 2 utilities
        assert len(PROPERTY_PRICES) == 22

    def test_start_money(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert game.players[0].money == 1500
        assert game.players[0].position == 0

    def test_rent_full_set(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1, 3]  # full brown set
        assert game._rent_due(1, alice, 7) == 4
        assert game._rent_due(3, alice, 7) == 8

    def test_rent_with_houses(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1]
        alice.houses = {1: 2}
        assert game._rent_due(1, alice, 7) == 8  # 2 * 4

    def test_rent_railroads(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [5, 15]
        assert game._rent_due(5, alice, 7) == 50
        alice.properties = [5, 15, 25, 35]
        assert game._rent_due(5, alice, 7) == 200

    def test_rent_utilities(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [12]
        assert game._rent_due(12, alice, 8) == 32
        alice.properties = [12, 28]
        assert game._rent_due(12, alice, 8) == 80

    def test_move_salary_on_wrap(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.position = 38
        alice.money = 1000
        game._move(alice, 5)
        assert alice.position == 3
        assert alice.money == 1200  # salary collected

    def test_send_to_jail(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game._send_to_jail(alice)
        assert alice.in_jail is True
        assert alice.position == 10

    def test_bankruptcy_transfers_assets(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        alice.money = 60
        alice.properties = [1]
        bankrupt = game._charge(alice, 200, bob)
        assert bankrupt is True
        assert alice.bankrupt is True
        assert 1 in bob.properties

    def test_build_and_mortgage(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.properties = [1, 3]
        alice.money = 1500
        game.phase = "roll"
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._action_build(alice, "1", "build")
        assert alice.houses.get(1) == 1
        alice.money -= 100  # Simulate a purchase elsewhere
        game._action_mortgage(alice, "3", "mortgage")
        assert 3 in alice.mortgaged
        assert alice.money == 1380  # 1500 - 50 (build) - 100 + 30 (mortgage)
        assert 1 not in alice.mortgaged

    def test_leaderboard_types(self):
        boards = MonopolyGame.get_leaderboard_types()
        assert any(
            c["id"] == "most_money"
            and c["path"] == "money.{player_name}"
            and c["aggregate"] == "max"
            for c in boards
        )

    def test_result_carries_money(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        result = game.build_game_result()
        assert "money" in result.custom_data
        assert result.custom_data["money"]["Alice"] == 1500

    def test_serialization(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"]) == 2
        loaded = MonopolyGame.from_json(game.to_json())
        assert loaded.players[0].money == 1500
        assert loaded.phase == "roll"


class TestMonopolyPlay:
    """Integration tests for complete game play."""

    def test_two_bot_game_completes(self):
        game = MonopolyGame(options=MonopolyOptions(max_rounds=80))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 120000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_four_bot_game_completes(self):
        game = MonopolyGame(options=MonopolyOptions(max_rounds=60))
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 120000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_buy_and_decline_auction(self):
        game = MonopolyGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        # Alice lands on an unowned space and buys it
        alice.position = 1
        game.phase = "buy"
        game.execute_action(alice, "buy")
        assert 1 in alice.properties
        assert alice.money == 1500 - 60

    def test_auction_flow(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game._start_auction(6)
        assert game.phase == "auction"
        # Alice bids, Bob passes, Alice wins
        game._action_auction_bid(alice, "30", "auction_bid")
        game._action_auction_pass(bob, "auction_pass")
        assert game.phase == "roll"
        assert 6 in alice.properties
        assert alice.money == 1500 - 30

    def test_rent_charge_during_roll(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        # Bob owns Boardwalk; Alice lands on it and pays
        bob.properties = [39]
        alice.position = 39
        game.last_dice = [3, 4]
        game._resolve_landing(alice, 39)
        assert alice.money == 1500 - 50


class TestMonopolyPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = MonopolyGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.starting_money == 1500