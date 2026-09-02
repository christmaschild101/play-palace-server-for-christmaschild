"""
Tests for the Hearts game.
"""

import json

from server.games.hearts.game import HeartsGame, HeartsPlayer, HeartsOptions
from server.game_utils.cards import Card, Suit
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


def make_card(card_id, rank, suit):
    return Card(id=card_id, rank=rank, suit=suit)


class TestHeartsUnit:
    """Unit tests for Hearts."""

    def test_game_creation(self):
        game = HeartsGame()
        assert game.get_name() == "Hearts"
        assert game.get_type() == "hearts"
        assert game.get_category() == "category-card-games"
        assert game.get_min_players() == 4
        assert game.get_max_players() == 4

    def test_player_creation(self):
        game = HeartsGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, HeartsPlayer)

    def test_options_defaults(self):
        game = HeartsGame()
        assert game.options.target_score == 100
        assert game.options.pass_mode == "left"

    def test_deal_thirteen(self):
        game = HeartsGame()
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.on_start()
        assert all(len(p.hand) == 13 for p in game.players)
        assert game.phase == "pass"

    def test_rank_value_ace_high(self):
        assert HeartsGame._rank_value(make_card(1, 1, 1)) == 14
        assert HeartsGame._rank_value(make_card(2, 2, 1)) == 2
        assert HeartsGame._rank_value(make_card(3, 13, 1)) == 13

    def test_pass_target_left(self):
        game = HeartsGame(options=HeartsOptions(pass_mode="left"))
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        assert game._pass_target(0) == 1
        assert game._pass_target(3) == 0

    def test_pass_target_right(self):
        game = HeartsGame(options=HeartsOptions(pass_mode="right"))
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        assert game._pass_target(0) == 3
        assert game._pass_target(1) == 0

    def test_pass_target_across(self):
        game = HeartsGame(options=HeartsOptions(pass_mode="across"))
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        assert game._pass_target(0) == 2
        assert game._pass_target(1) == 3

    def test_legal_cards_follow_suit(self):
        game = HeartsGame()
        p0 = game.add_player("P0", MockUser("P0"))
        for i in range(1, 4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.phase = "play"
        p0.hand = [
            make_card(1, 2, Suit.DIAMONDS),
            make_card(2, 5, Suit.CLUBS),
            make_card(3, 3, Suit.HEARTS),
        ]
        game.trick = [make_card(9, 7, Suit.CLUBS)]
        legal = game._legal_cards(p0)
        assert legal == [make_card(2, 5, Suit.CLUBS)]

    def test_cannot_lead_hearts_before_broken(self):
        game = HeartsGame()
        p0 = game.add_player("P0", MockUser("P0"))
        for i in range(1, 4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.phase = "play"
        p0.hand = [
            make_card(1, 3, Suit.HEARTS),
            make_card(2, 5, Suit.DIAMONDS),
        ]
        legal = game._legal_cards(p0)
        assert all(c.suit != Suit.HEARTS for c in legal)

    def test_point_counting(self):
        game = HeartsGame()
        p = game.add_player("P0", MockUser("P0"))
        for i in range(1, 4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        p.taken = [
            make_card(1, 2, Suit.HEARTS),
            make_card(2, 3, Suit.HEARTS),
            make_card(3, 12, Suit.SPADES),  # Queen of Spades
        ]
        assert game._count_hand_points(p) == 15

    def test_leaderboard_types(self):
        boards = HeartsGame.get_leaderboard_types()
        lowest = next(c for c in boards if c["id"] == "lowest_points")
        assert lowest["path"] == "final_scores.{player_name}"
        assert lowest["reverse"] is True
        assert any(c["id"] == "moon_shots" for c in boards)

    def test_result_carries_player_stats(self):
        game = HeartsGame()
        p0 = game.add_player("P0", MockUser("P0"))
        for i in range(1, 4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        p0.moons = 2
        result = game.build_game_result()
        stats = result.custom_data["player_stats"]
        assert stats["P0"]["moons"] == 2

    def test_serialization(self):
        game = HeartsGame()
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"][0]["hand"]) == 13
        loaded = HeartsGame.from_json(game.to_json())
        assert len(loaded.players[0].hand) == 13
        assert loaded.phase == "pass"


class TestHeartsPlay:
    """Integration tests for complete game play."""

    def test_four_bot_game_completes(self):
        game = HeartsGame(options=HeartsOptions(target_score=50))
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_no_pass_game_completes(self):
        game = HeartsGame(options=HeartsOptions(target_score=50, pass_mode="none"))
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_plays_a_card(self):
        game = HeartsGame(options=HeartsOptions(pass_mode="none"))
        user = MockUser("P0")
        p0 = game.add_player("P0", user)
        for i in range(1, 4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.on_start()
        # Skip to play phase
        game.phase = "play"
        game.trick = []
        game.trick_players = []
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        game._announce_trick()
        legal = game._legal_cards(p0)
        assert legal
        game.execute_action(p0, "play", input_value=str(legal[0].id))
        assert len(game.trick) == 1


class TestHeartsPersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = HeartsGame()
        for i in range(4):
            game.add_player(f"P{i}", MockUser(f"P{i}"))
        game.on_start()
        saved = game.to_json()
        loaded = HeartsGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.options.pass_mode == "left"