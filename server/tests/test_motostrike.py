"""
Tests for the Moto Strike game.
"""

import json

from server.games.motostrike.game import (
    MotoStrikeGame,
    MotoStrikePlayer,
    MotoStrikeOptions,
    HAND_SIZE,
    CHASE_WINDOW,
    DEADLY_KICK_MIN_DISTANCE,
    SMOKE_KNOCKBACK,
    QUICK_KICK_KNOCKBACK,
    SHOCK_RANGE,
)
from server.games.motostrike.cards import (
    Card,
    CardType,
    Deck,
    MOVEMENT_VALUES,
    MANEUVER_VALUES,
)
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


def _started_game(num_players=2, options=None):
    """Build a game with the given number of bot players and start it."""
    game = MotoStrikeGame(options=options or MotoStrikeOptions())
    for i in range(num_players):
        game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
    game.on_start()
    game.game_active = True
    game.status = "playing"
    return game


def _hand_of(*values):
    """Build a hand of cards with the given values."""
    return [Card(id=i, card_type=_type_for(v), value=v) for i, v in enumerate(values)]


def _type_for(value: str) -> str:
    if value in MOVEMENT_VALUES:
        return CardType.MOVEMENT
    if value in MANEUVER_VALUES:
        return CardType.MANEUVER
    if value in ("mud_trap", "spike_trap", "rock_trap"):
        return CardType.TRAP
    if value in ("smoke_bomb", "electric_shock", "police_chase"):
        return CardType.ATTACK
    if value in ("quick_kick", "deadly_kick", "kick_shield", "emergency_swerve"):
        return CardType.SPECIAL
    return CardType.RECOVERY


class TestMotoStrikeUnit:
    """Unit tests for Moto Strike."""

    def test_game_creation(self):
        game = MotoStrikeGame()
        assert game.get_name() == "Moto Strike"
        assert game.get_type() == "motostrike"
        assert game.get_category() == "category-card-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 6

    def test_player_creation(self):
        game = MotoStrikeGame()
        user = MockUser("Alice")
        player = game.add_player("Alice", user)
        assert player.name == "Alice"
        assert player.is_bot is False
        assert isinstance(player, MotoStrikePlayer)

    def test_options_defaults(self):
        game = MotoStrikeGame()
        assert game.options.track_length == 2000
        assert game.options.deadly_kick is True

    def test_deck_composition(self):
        deck = Deck()
        deck.build_standard_deck()
        deck.shuffle()
        values = [c.value for c in deck.cards]
        assert len(deck.cards) == 93
        assert values.count("easy_ride") == 12
        assert values.count("power_dash") == 8
        assert values.count("mud_trap") == 4
        assert values.count("spike_trap") == 2
        assert values.count("rock_trap") == 2
        assert values.count("deadly_kick") == 1
        assert values.count("kick_shield") == 3
        assert values.count("emergency_swerve") == 4
        # Recovery cards outnumber trap cards so races keep moving
        assert values.count("rebalance") == 12
        assert values.count("repair") == 6
        assert values.count("escape") == 6
        assert values.count("rebalance") > values.count("mud_trap") + values.count("spike_trap") + values.count("rock_trap")
        # Four maneuver turns
        assert values.count("slight_left") == 3
        assert values.count("slight_right") == 3
        assert values.count("full_left") == 2
        assert values.count("full_right") == 2

    def test_start_deals_five_cards(self):
        game = _started_game(2)
        for p in game.players:
            assert len(p.hand) == HAND_SIZE
        assert game.deck.size() == 93 - 10

    def test_movement_advances(self):
        game = _started_game(2)
        alice = game.players[0]
        game.deck = Deck()  # prevent refill interference
        alice.hand = _hand_of("easy_ride", "speed_boost", "power_dash")
        game._play_movement(alice, 0, alice.hand[0])
        assert alice.distance == 25

    def test_can_play_movement_when_stuck(self):
        game = _started_game(2)
        alice = game.players[0]
        alice.hand = _hand_of("easy_ride")
        alice.stuck = True
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-stuck"

    def test_mud_trap_requires_rebalance(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.hand = _hand_of("mud_trap")
        bob.hand = _hand_of("rebalance", "easy_ride")
        game._play_trap(alice, 0, alice.hand[0], "Bot1 (0 meters)")
        assert bob.stuck is True
        assert bob.can_move() is False
        # Rebalance clears it
        game._play_recovery(bob, 0, bob.hand[0])
        assert bob.stuck is False
        assert bob.can_move() is True

    def test_spike_trap_requires_repair_and_rebalance(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.hand = _hand_of("spike_trap")
        bob.hand = _hand_of("repair", "rebalance", "easy_ride")
        game._play_trap(alice, 0, alice.hand[0], "Bot1 (0 meters)")
        assert bob.stuck is True
        assert bob.wheel_damaged is True
        # Repair alone is not enough
        game._play_recovery(bob, 0, bob.hand[0])
        assert bob.wheel_damaged is False
        assert bob.can_move() is False
        game._play_recovery(bob, 0, bob.hand[0])
        assert bob.can_move() is True

    def test_emergency_swerve_blocks_trap(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.hand = _hand_of("mud_trap")
        bob.hand = _hand_of("emergency_swerve")
        game._play_trap(alice, 0, alice.hand[0], "Bot1 (0 meters)")
        assert bob.stuck is False
        assert not any(c.value == "emergency_swerve" for c in bob.hand)

    def test_kick_shield_blocks_quick_kick(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 700
        bob.hand = _hand_of("kick_shield")
        alice.hand = _hand_of("quick_kick")
        game._play_special(alice, 0, alice.hand[0], "Bot1 (700 meters)")
        assert bob.distance == 700
        assert not any(c.value == "kick_shield" for c in bob.hand)

    def test_quick_kick_knocks_back_200(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 700
        alice.hand = _hand_of("quick_kick")
        game._play_special(alice, 0, alice.hand[0], "Bot1 (700 meters)")
        assert bob.distance == 700 - QUICK_KICK_KNOCKBACK

    def test_quick_kick_never_below_zero(self):
        game = _started_game(2)
        alice, bob = game.players
        bob.distance = 100
        alice.hand = _hand_of("quick_kick")
        game._play_special(alice, 0, alice.hand[0], "Bot1 (100 meters)")
        assert bob.distance == 0

    def test_smoke_bomb_slows_rider_behind(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 300
        alice.hand = _hand_of("smoke_bomb")
        game._play_attack(alice, 0, alice.hand[0])
        assert bob.distance == 300 - SMOKE_KNOCKBACK

    def test_smoke_bomb_no_target_behind(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 300
        bob.distance = 500
        alice.hand = _hand_of("smoke_bomb")
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-no-one-behind"

    def test_electric_shock_within_range(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 530
        bob.hand = _hand_of("easy_ride", "speed_boost", "power_dash", "mud_trap", "repair")
        alice.hand = _hand_of("electric_shock")
        game._play_attack(alice, 0, alice.hand[0])
        assert len(bob.hand) == 4  # one card discarded at random

    def test_electric_shock_out_of_range(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 600
        alice.hand = _hand_of("electric_shock")
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-no-one-within"
        assert SHOCK_RANGE == 50

    def test_police_chase_immobilizes_after_two_turns(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 700
        alice.hand = _hand_of("police_chase")
        game._play_attack(alice, 0, alice.hand[0])
        assert bob.police_chase_turns == CHASE_WINDOW
        assert bob.immobilized is False
        # Bob's first turn ends without a Maneuver
        game._finish_play(bob, played_maneuver=False)
        assert bob.police_chase_turns == 1
        assert bob.immobilized is False
        # Bob's second turn ends without a Maneuver
        game._finish_play(bob, played_maneuver=False)
        assert bob.police_chase_turns == 0
        assert bob.immobilized is True
        # Escape card clears it
        bob.hand = _hand_of("escape")
        game._play_recovery(bob, 0, bob.hand[0])
        assert bob.immobilized is False

    def test_maneuver_escapes_police_chase(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        bob.distance = 700
        bob.police_chase_turns = CHASE_WINDOW
        bob.hand = _hand_of("slight_left", "easy_ride")
        game._play_maneuver(bob, 0, bob.hand[0])
        assert bob.police_chase_turns == 0
        assert bob.immobilized is False

    def test_maneuver_moves_10_or_25(self):
        game = _started_game(2)
        alice = game.players[0]
        alice.hand = _hand_of("slight_right")
        game._play_maneuver(alice, 0, alice.hand[0])
        assert alice.distance == 10
        alice.hand = _hand_of("full_left")
        game._play_maneuver(alice, 0, alice.hand[0])
        assert alice.distance == 35

    def test_deadly_kick_requires_1000(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 500
        alice.hand = _hand_of("deadly_kick")
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-need-1000"
        assert DEADLY_KICK_MIN_DISTANCE == 1000

    def test_deadly_kick_eliminates(self):
        game = _started_game(2)
        alice, bob = game.players
        alice.distance = 1200
        bob.distance = 800
        bob.hand = _hand_of("easy_ride", "speed_boost", "power_dash", "mud_trap", "repair")
        alice.hand = _hand_of("deadly_kick")
        game._play_special(alice, 0, alice.hand[0], "Bot1 (800 meters)")
        assert bob.eliminated is True
        # Only one rider left: the kicker wins immediately
        assert game.status == "finished"
        assert game.race_winner_id == alice.id

    def test_deadly_kick_disabled(self):
        game = _started_game(2, options=MotoStrikeOptions(deadly_kick=False))
        alice, bob = game.players
        alice.distance = 1200
        alice.hand = _hand_of("deadly_kick")
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-disabled"

    def test_deadly_kick_blocked_by_shield(self):
        game = _started_game(3)
        alice, bob, carol = game.players
        alice.distance = 1200
        bob.distance = 800
        bob.hand = _hand_of("kick_shield")
        alice.hand = _hand_of("deadly_kick")
        game._play_special(alice, 0, alice.hand[0], "Bot1 (800 meters)")
        assert bob.eliminated is False
        assert game.status == "playing"

    def test_shields_cannot_be_played(self):
        game = _started_game(2)
        alice = game.players[0]
        alice.hand = _hand_of("kick_shield")
        playable, reason = game._can_play(alice, alice.hand[0])
        assert playable is False
        assert reason == "motostrike-reason-hold-only"

    def test_recovery_cards_only_when_needed(self):
        game = _started_game(2)
        alice = game.players[0]
        alice.hand = _hand_of("rebalance", "repair", "escape")
        for card in alice.hand:
            playable, _ = game._can_play(alice, card)
            assert playable is False

    def test_hand_refills_after_play(self):
        game = _started_game(2)
        alice = game.players[0]
        before = game.deck.size()
        alice.hand = _hand_of("easy_ride", "speed_boost", "power_dash", "mud_trap", "repair")
        game._play_movement(alice, 0, alice.hand[0])
        # One card was spent, so one is drawn back
        assert len(alice.hand) == HAND_SIZE
        assert game.deck.size() == before - 1

    def test_reshuffle_on_empty_deck(self):
        game = _started_game(2)
        alice = game.players[0]
        # Empty the deck and put a card in the discard pile
        game.deck = Deck()
        game.discard_pile = [Card(id=999, card_type=CardType.MOVEMENT, value="easy_ride")]
        card = game._draw_card()
        assert card is not None
        assert card.value == "easy_ride"
        assert game.deck.is_empty()
        assert game.discard_pile == []

    def test_target_options_format(self):
        game = _started_game(2)
        alice, bob = game.players
        bob.distance = 400
        alice.hand = _hand_of("mud_trap")
        game._pending_actions[alice.id] = "card_slot_1"
        options = game._target_options(alice)
        assert options == ["Bot1 (400 meters)"]

    def test_leaderboard_types(self):
        boards = MotoStrikeGame.get_leaderboard_types()
        by_id = {b["id"]: b for b in boards}
        assert by_id["best_finish"]["path"] == "final_distances.{player_name}"
        assert by_id["best_finish"]["aggregate"] == "max"
        assert by_id["avg_finish"]["aggregate"] == "avg"

    def test_result_carries_final_distances(self):
        game = MotoStrikeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        result = game.build_game_result()
        assert "final_distances" in result.custom_data
        assert result.custom_data["final_distances"]["Alice"] == 0
        assert result.custom_data["winner_name"] in ("Alice", "Bob")

    def test_serialization(self):
        game = MotoStrikeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        data = json.loads(game.to_json())
        assert len(data["players"]) == 2
        loaded = MotoStrikeGame.from_json(game.to_json())
        assert loaded.players[0].distance == 0
        assert loaded.options.track_length == 2000
        assert loaded.deck.size() == game.deck.size()


class TestMotoStrikePlay:
    """Integration tests for complete races."""

    def test_two_bot_game_completes(self):
        game = MotoStrikeGame()
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_four_bot_game_completes(self):
        game = MotoStrikeGame()
        for i in range(4):
            game.add_player(f"Bot{i}", Bot(f"Bot{i}"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_short_track_completes(self):
        game = MotoStrikeGame(options=MotoStrikeOptions(track_length=600))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_no_deadly_kick_game_completes(self):
        game = MotoStrikeGame(options=MotoStrikeOptions(deadly_kick=False))
        game.add_player("Bot1", Bot("Bot1"))
        game.add_player("Bot2", Bot("Bot2"))
        game.on_start()
        max_ticks = 60000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_human_cannot_play_unplayable_card(self):
        game = MotoStrikeGame()
        user = MockUser("Alice")
        alice = game.add_player("Alice", user)
        bob = game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        game.game_active = True
        game.status = "playing"
        game.set_turn_players(game.get_active_players())
        alice.hand = _hand_of("easy_ride", "speed_boost", "power_dash", "mud_trap", "rebalance")
        alice.stuck = True
        game.turn_index = 0
        # Playing a movement card while stuck keeps the card and the turn
        game.execute_action(alice, "card_slot_1")
        assert alice.stuck is True
        assert len(alice.hand) == HAND_SIZE
        assert game.current_player == alice
        # The recovery card is playable when stuck
        assert game._can_play(alice, alice.hand[4])[0] is True


class TestMotoStrikePersistence:
    """Tests for game persistence."""

    def test_full_state_preserved(self):
        game = MotoStrikeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.on_start()
        saved = game.to_json()
        loaded = MotoStrikeGame.from_json(saved)
        assert loaded.game_active is True
        assert loaded.players[0].hand == game.players[0].hand
        assert loaded.turn_player_ids == game.turn_player_ids
        assert loaded.discard_pile == game.discard_pile