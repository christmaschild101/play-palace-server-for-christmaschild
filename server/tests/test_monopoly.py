"""
Tests for the Monopoly game.
"""

import json

from server.games.monopoly.game import (
    MonopolyGame,
    MonopolyPlayer,
    MonopolyOptions,
    PROPERTY_PRICES,
    RENT_TABLE,
    SPACE_NAMES,
    SPACE_NAMES_UK,
    CHANCE_CARDS,
    CHEST_CARDS,
    BAIL,
    SALARY,
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
        assert game.options.board_variant == "us"
        assert game.options.rent_source == "classic"
        assert game.options.free_parking_jackpot is False
        assert game.options.income_tax_10pct is False
        assert game.options.auction_start_10pct is False

    def test_board_structure(self):
        assert len(SPACE_NAMES) == 40
        assert len(SPACE_NAMES_UK) == 40
        assert PROPERTY_PRICES[1] == 60
        assert PROPERTY_PRICES[39] == 400
        # 22 properties, 4 railroads, 2 utilities
        assert len(PROPERTY_PRICES) == 22
        # UK board names
        assert SPACE_NAMES_UK[39] == "monopoly-space-mayfair"
        assert SPACE_NAMES_UK[38] == "monopoly-space-super-tax"
        assert SPACE_NAMES_UK[5] == "monopoly-space-kings-cross"
        # US board keeps classic names
        assert SPACE_NAMES[39] == "monopoly-space-boardwalk"

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

    def test_rent_classic_with_houses(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1]
        alice.houses = {1: 2}
        # Classic chart: Mediterranean with 2 houses = 30
        assert game._rent_due(1, alice, 7) == RENT_TABLE[1][2] == 30
        alice.houses = {1: 5}  # hotel
        assert game._rent_due(1, alice, 7) == RENT_TABLE[1][5] == 250

    def test_rent_simplified_with_houses(self):
        game = MonopolyGame(options=MonopolyOptions(rent_source="simplified"))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1]
        alice.houses = {1: 2}
        # Simplified ladder: base * 2^houses = 2 * 4
        assert game._rent_due(1, alice, 7) == 8

    def test_rent_classic_on_uk_board(self):
        game = MonopolyGame(options=MonopolyOptions(board_variant="uk"))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1]
        alice.houses = {1: 3}
        assert game._rent_due(1, alice, 7) == RENT_TABLE[1][3] == 90

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

    def test_money_currency(self):
        us = MonopolyGame()
        uk = MonopolyGame(options=MonopolyOptions(board_variant="uk"))
        assert us._money(200) == "$200"
        assert uk._money(200) == "£200"
        assert uk._symbol() == "£"

    def test_uk_space_names_resolve(self):
        game = MonopolyGame(options=MonopolyOptions(board_variant="uk"))
        assert game._space_name(39, "en") == "Mayfair"
        assert game._space_name(38, "en") == "Super Tax"
        us = MonopolyGame()
        assert us._space_name(39, "en") == "Boardwalk"

    def test_total_assets(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.money = 1000
        alice.properties = [1, 39]  # 60 + 400
        alice.houses = {39: 1}  # darkblue house cost 200
        assert game._total_assets(alice) == 1000 + 60 + 400 + 200

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
        assert alice.houses_built == 1
        alice.money -= 100  # Simulate a purchase elsewhere
        game._action_mortgage(alice, "3", "mortgage")
        assert 3 in alice.mortgaged
        assert alice.money == 1380  # 1500 - 50 (build) - 100 + 30 (mortgage)
        assert 1 not in alice.mortgaged

    def test_sell_house_refund(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 1000
        alice.houses = {1: 2}  # brown: house cost 50
        game.phase = "roll"
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._action_sell_house(alice, "1", "sell_house")
        assert alice.money == 1000 + 25
        assert alice.houses[1] == 1

    def test_pay_bail(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.in_jail = True
        alice.jail_turns = 1
        game.phase = "roll"
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._action_pay_bail(alice, "pay_bail")
        assert alice.in_jail is False
        assert alice.money == 1500 - BAIL

    def test_use_jail_free_card(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.in_jail = True
        alice.jail_free_cards = 1
        alice.jail_free_decks = ["chance"]
        game.phase = "roll"
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._action_use_jail_free(alice, "use_jail_free")
        assert alice.in_jail is False
        assert alice.jail_free_cards == 0

    def test_jail_free_card_returned_on_bankruptcy(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 10
        alice.jail_free_cards = 1
        alice.jail_free_decks = ["chance"]
        game._charge(alice, 500, bob)
        assert alice.bankrupt is True
        assert alice.jail_free_cards == 0
        assert game.chance_deck[-1]["kind"] == "goojf"

    def test_full_card_decks(self):
        assert len(CHANCE_CARDS) == 16
        assert len(CHEST_CARDS) == 16
        chance_kinds = {c["kind"] for c in CHANCE_CARDS}
        chest_kinds = {c["kind"] for c in CHEST_CARDS}
        assert "goojf" in chance_kinds
        assert "goojf" in chest_kinds
        assert "repairs" in chance_kinds
        assert "repairs" in chest_kinds
        assert "collect_from_all" in chest_kinds

    def test_decks_built_on_start(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        assert len(game.chance_deck) == 16
        assert len(game.chest_deck) == 16

    def test_goojf_card_held(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game._apply_card(alice, {"kind": "goojf", "value": 0}, "chance")
        assert alice.jail_free_cards == 1
        assert alice.jail_free_decks == ["chance"]

    def test_repairs_charges_per_house(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 1000
        alice.houses = {1: 2, 39: 5}  # 2 houses + 1 hotel (hotel = 4 houses + 1 hotel)
        game._apply_card(alice, {"kind": "repairs", "value": 25, "value2": 100}, "chance")
        # 6 houses * 25 + 1 hotel * 100 = 250
        assert alice.money == 1000 - 250

    def test_advance_to_go_card_collects_salary(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.position = 39
        alice.money = 0
        game.last_dice = [1, 1]
        game._apply_card(alice, {"kind": "move_to", "value": 0}, "chance")
        assert alice.position == 0
        assert alice.money == SALARY

    # --- Free Parking jackpot ---

    def test_jackpot_accumulates_and_pays(self):
        game = MonopolyGame(options=MonopolyOptions(free_parking_jackpot=True))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 1500
        # Land on Income Tax -> tax goes to the jackpot
        alice.position = 4
        game.last_dice = [1, 1]
        game._resolve_landing(alice, 4)
        assert game.jackpot == 200
        assert alice.money == 1500
        # Land on Free Parking -> collect the jackpot
        alice.position = 20
        game._resolve_landing(alice, 20)
        assert alice.money == 1700
        assert game.jackpot == 0

    def test_card_fines_feed_jackpot(self):
        game = MonopolyGame(options=MonopolyOptions(free_parking_jackpot=True))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 1000
        game._apply_card(alice, {"kind": "pay", "value": 15}, "chance")
        assert alice.money == 1000
        assert game.jackpot == 15

    # --- Income tax 10% ---

    def test_income_tax_10pct(self):
        game = MonopolyGame(options=MonopolyOptions(income_tax_10pct=True))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.money = 1000
        alice.properties = [39]  # worth 400 -> total assets 1400 -> tax 140
        alice.position = 4
        game.last_dice = [1, 1]
        game._resolve_landing(alice, 4)
        assert alice.money == 1000 - 140

    def test_income_tax_flat_default(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        alice.position = 4
        game.last_dice = [1, 1]
        game._resolve_landing(alice, 4)
        assert alice.money == 1300

    # --- Auction start price ---

    def test_auction_start_10pct(self):
        game = MonopolyGame(options=MonopolyOptions(auction_start_10pct=True))
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._start_auction(6)  # Oriental Avenue: 100 -> opening bid 10
        assert game.auction_bid == 10
        assert game.phase == "auction"

    def test_auction_start_zero_default(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0
        game._start_auction(6)
        assert game.auction_bid == 0

    # --- Two-way trades ---

    def _start_rolled_game(self, game):
        game.on_start()
        game.phase = "roll"
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game.turn_index = 0

    def test_trade_offer_accept(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        bob.properties = [3]
        # Alice offers Mediterranean for Bob's Baltic
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "3", "trade_get_property")
        game._action_trade_get_cash(alice, "0", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        assert game.pending_offer is not None
        assert game.pending_offer["to_id"] == bob.id
        # Bob accepts on his turn
        game.turn_index = 1
        game._action_accept_trade(bob, "accept_trade")
        assert game.pending_offer is None
        assert alice.properties == [3]
        assert bob.properties == [1]

    def test_trade_offer_with_cash(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        bob.properties = []
        # Alice sells Mediterranean for $80 cash
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "0", "trade_get_property")
        game._action_trade_get_cash(alice, "80", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        game.turn_index = 1
        game._action_accept_trade(bob, "accept_trade")
        assert alice.money == 1500 + 80
        assert bob.money == 1500 - 80
        assert bob.properties == [1]
        assert alice.properties == []

    def test_trade_reject(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "0", "trade_get_property")
        game._action_trade_get_cash(alice, "500", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        game.turn_index = 1
        game._action_reject_trade(bob, "reject_trade")
        assert game.pending_offer is None
        assert alice.properties == [1]

    def test_trade_offerer_cancel(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "0", "trade_get_property")
        game._action_trade_get_cash(alice, "0", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        assert game.pending_offer is not None
        game._action_cancel_offer(alice, "cancel_offer")
        assert game.pending_offer is None

    def test_trade_offer_expires_on_target_turn_end(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "0", "trade_get_property")
        game._action_trade_get_cash(alice, "0", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        # Bob's turn arrives and ends without deciding
        game.turn_index = 1
        game.advance_turn()
        assert game.pending_offer is None

    def test_trade_post_rejects_unaffordable_cash(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        bob.properties = [39]
        alice.money = 100
        # Alice tries to offer 500 cash she doesn't have
        game._action_trade_property(alice, "0", "trade_property")
        game._action_trade_cash(alice, "500", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "39", "trade_get_property")
        game._action_trade_get_cash(alice, "0", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        assert game.pending_offer is None  # rejected at post
        assert bob.properties == [39]

    def test_trade_accept_requires_target_cash(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [39]
        bob.properties = []
        bob.money = 10
        # Alice offers Boardwalk for 500 cash Bob can't pay
        game._action_trade_property(alice, "39", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "0", "trade_get_property")
        game._action_trade_get_cash(alice, "500", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        assert game.pending_offer is not None
        game.turn_index = 1
        game._action_accept_trade(bob, "accept_trade")
        assert game.pending_offer is not None  # still pending, can't afford
        assert alice.properties == [39]
        assert bob.properties == []

    def test_trade_draft_cancel(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        assert alice.trade_property == 1
        game._action_trade_cancel(alice, "trade_cancel")
        assert alice.trade_property is None

    def test_cash_only_trade_option(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        self._start_rolled_game(game)
        alice.properties = [1]
        bob.properties = [3]
        # Cash-only receive: Alice gives 100 cash for Baltic
        game._action_trade_property(alice, "0", "trade_property")
        game._action_trade_cash(alice, "100", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_get_property(alice, "3", "trade_get_property")
        game._action_trade_get_cash(alice, "0", "trade_get_cash")
        game._action_trade_post(alice, "trade_post")
        game.turn_index = 1
        game._action_accept_trade(bob, "accept_trade")
        assert alice.properties == [3]
        assert bob.properties == []
        assert alice.money == 1500 - 100
        assert bob.money == 1500 + 100

    # --- Trade start / stop announcements ---

    def _speak_texts(self, user):
        return [m.data["text"] for m in user.messages if m.type == "speak"]

    def _count_speaks(self, user, phrase):
        return sum(1 for text in self._speak_texts(user) if phrase in text)

    def test_trade_start_broadcast(self):
        game = MonopolyGame()
        alice_user = MockUser("Alice")
        bob_user = MockUser("Bob")
        carol_user = MockUser("Carol")
        alice = game.add_player("Alice", alice_user)
        game.add_player("Bob", bob_user)
        game.add_player("Carol", carol_user)
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        # Everyone at the table (Alice included) learns a trade has begun.
        for user in (alice_user, bob_user, carol_user):
            assert self._count_speaks(user, "Alice has started a trade with Bob.") == 1

    def test_trade_start_not_repeated_for_same_target(self):
        game = MonopolyGame()
        bob_user = MockUser("Bob")
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", bob_user)
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_target(alice, "Bob", "trade_target")  # re-pick, same target
        assert self._count_speaks(bob_user, "Alice has started a trade with Bob.") == 1

    def test_trade_start_not_sent_for_invalid_target(self):
        game = MonopolyGame()
        bob_user = MockUser("Bob")
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", bob_user)
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Alice", "trade_target")  # self
        game._action_trade_target(alice, "Nobody", "trade_target")  # not at the table
        assert alice.trade_target_id == ""
        assert self._count_speaks(bob_user, "started a trade with") == 0

    def test_trade_stop_broadcast_on_cancel(self):
        game = MonopolyGame()
        alice_user = MockUser("Alice")
        bob_user = MockUser("Bob")
        alice = game.add_player("Alice", alice_user)
        game.add_player("Bob", bob_user)
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_target(alice, "Bob", "trade_target")
        game._action_trade_cancel(alice, "trade_cancel")
        assert alice.trade_target_id == ""
        for user in (alice_user, bob_user):
            assert self._count_speaks(user, "Alice stopped working on a trade.") == 1

    def test_trade_cancel_before_target_keeps_table_silent(self):
        game = MonopolyGame()
        bob_user = MockUser("Bob")
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", bob_user)
        self._start_rolled_game(game)
        alice.properties = [1]
        game._action_trade_property(alice, "1", "trade_property")
        game._action_trade_cash(alice, "0", "trade_cash")
        game._action_trade_cancel(alice, "trade_cancel")
        assert self._count_speaks(bob_user, "started a trade with") == 0
        assert self._count_speaks(bob_user, "stopped working on a trade") == 0

    # --- Bot AI ---

    def test_bot_even_build_choice(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        alice.properties = [1, 3]
        alice.houses = {1: 1}
        choice = game._bot_build_choice(alice, ["1", "3"])
        assert choice == "3"  # build on the least-developed property

    def test_bot_buy_valuation(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        # Cheap property with plenty of cash
        assert game._bot_wants_buy(alice, 1) is True
        # Boardwalk with low cash
        alice.money = 500
        assert game._bot_wants_buy(alice, 39) is False
        # Completing a group stretches the budget
        alice.money = 700
        alice.properties = [11, 13]  # missing 14 (worth 160)
        assert game._bot_wants_buy(alice, 14) is True

    def test_bot_accepts_fair_offer(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.pending_offer = {
            "from_id": alice.id,
            "to_id": bob.id,
            "give_space": 3,
            "give_cash": 0,
            "receive_space": 1,
            "receive_cash": 0,
        }
        assert game._bot_trade_decision(bob) == "accept_trade"

    def test_bot_rejects_bad_offer(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        bob.properties = [1]
        game.pending_offer = {
            "from_id": alice.id,
            "to_id": bob.id,
            "give_space": 3,
            "give_cash": 0,
            "receive_space": 1,
            "receive_cash": 500,  # Bob must pay 500 for a 60 property
        }
        assert game._bot_trade_decision(bob) == "reject_trade"

    def test_bot_offer_plan_group_completion(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        alice.properties = [11, 13]
        alice.money = 1500
        bob.properties = [14]
        plan = game._bot_offer_plan(alice)
        assert plan is not None
        assert plan[0] == 0  # cash only
        assert plan[3] == 14  # wants the missing pink member
        assert plan[2] == bob.id

    # --- Leaderboards and stats ---

    def test_leaderboard_types(self):
        boards = MonopolyGame.get_leaderboard_types()
        assert len(boards) == 4
        by_id = {c["id"]: c for c in boards}
        assert by_id["most_money"]["path"] == "money.{player_name}"
        assert by_id["properties_owned"]["path"] == "stats.{player_name}.properties"
        assert by_id["houses_built"]["path"] == "stats.{player_name}.houses_built"
        assert by_id["rent_collected"]["path"] == "stats.{player_name}.rent_collected"
        for config in boards:
            assert config["aggregate"] == "max"
            assert config["format"] == "score"

    def test_result_carries_money_and_stats(self):
        game = MonopolyGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        result = game.build_game_result()
        assert "money" in result.custom_data
        assert result.custom_data["money"]["Alice"] == 1500
        assert "stats" in result.custom_data
        assert result.custom_data["stats"]["Alice"]["properties"] == 0
        assert result.custom_data["board_variant"] == "us"

    def test_rent_collected_tracked(self):
        game = MonopolyGame()
        alice = game.add_player("Alice", MockUser("Alice"))
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        bob.properties = [39]
        alice.position = 39
        game.last_dice = [3, 4]
        game._resolve_landing(alice, 39)
        assert bob.rent_collected == 50

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
        assert loaded.pending_offer is None
        assert loaded.jackpot == 0


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

    def test_uk_board_bot_game_completes(self):
        game = MonopolyGame(
            options=MonopolyOptions(board_variant="uk", rent_source="classic", max_rounds=60)
        )
        for i in range(3):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 120000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_house_rules_bot_game_completes(self):
        game = MonopolyGame(
            options=MonopolyOptions(
                free_parking_jackpot=True,
                income_tax_10pct=True,
                auction_start_10pct=True,
                max_rounds=60,
            )
        )
        for i in range(3):
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