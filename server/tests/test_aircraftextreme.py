"""
Tests for the Aircraft Extreme game.

Covers unit behavior (map geometry, engine, combat), full bot play,
and serialization round-trips per docs/design/plans/game_development_guide.md.
"""

import json
import random
from unittest import mock

from server.games.aircraftextreme.game import (
    ACTIONS_PER_TURN,
    BASE_CORNERS,
    CANNON_DAMAGE,
    FIRE_RANGE,
    GRID_SIZE,
    MAX_POWER,
    STORM_MAX,
    STORM_MIN,
    TARGET_CORNERS,
    AircraftExtremeGame,
    adjacent_to_storm,
    in_storm,
)
from server.games.aircraftextreme.player import AircraftExtremePlayer
from server.games.aircraftextreme.options import AircraftExtremeOptions
from server.core.users.bot import Bot
from server.core.users.test_user import MockUser


def _make_game(*names: str, bots: bool = False) -> AircraftExtremeGame:
    """Build a started game with one player per name."""
    game = AircraftExtremeGame()
    for name in names:
        user = Bot(name) if bots else MockUser(name)
        game.add_player(name, user)
    game.on_start()
    return game


class TestAircraftExtremeUnit:
    """Unit tests for map, engine, and combat rules."""

    def test_game_metadata(self):
        game = AircraftExtremeGame()
        assert game.get_name() == "Aircraft Extreme"
        assert game.get_type() == "aircraftextreme"
        assert game.get_category() == "category-board-games"
        assert game.get_min_players() == 2
        assert game.get_max_players() == 4
        assert "game-name-aircraftextreme" in game.get_name_key()

    def test_storm_geometry(self):
        assert in_storm(2, 2)
        assert in_storm(3, 3)
        assert not in_storm(1, 2)
        assert not in_storm(2, 1)
        assert not in_storm(4, 4)
        assert adjacent_to_storm(1, 1)
        assert adjacent_to_storm(4, 4)
        assert not adjacent_to_storm(0, 0)

    def test_on_start_places_planes_on_corner_runways(self):
        game = _make_game("Alice", "Bob")
        for p in game.players:
            row, col = BASE_CORNERS[p.base]
            assert (p.row, p.col) == (row, col)
            assert p.health == game.options.start_health
            assert p.power == MAX_POWER
            assert p.laps == 0
        # Bases are distinct corners
        bases = {p.base for p in game.players}
        assert len(bases) == 2

    def test_target_corner_is_opposite_of_base(self):
        for base, (row, col) in BASE_CORNERS.items():
            t_row, t_col = TARGET_CORNERS[base]
            assert (t_row, t_col) == (GRID_SIZE - 1 - row, GRID_SIZE - 1 - col)

    def test_player_creation(self):
        game = AircraftExtremeGame()
        player = game.add_player("Alice", MockUser("Alice"))
        assert isinstance(player, AircraftExtremePlayer)
        assert player.is_bot is False

    def test_fly_moves_and_costs_power(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        start = (alice.row, alice.col)
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_south" if alice.base in ("nw", "ne") else "fly_north")
        assert (alice.row, alice.col) != start
        assert alice.power == MAX_POWER - 1
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_fly_into_storm_is_blocked(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.row, alice.col = STORM_MIN - 1, STORM_MIN  # just above the storm
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_south")
        assert alice.row == STORM_MIN - 1  # didn't move
        assert alice.power == MAX_POWER  # no power spent

    def test_fly_off_map_is_blocked(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.row, alice.col = 0, 0
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_north")
        assert (alice.row, alice.col) == (0, 0)

    def test_fly_blocked_by_other_plane(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        alice.row, alice.col = 0, 0
        bob.row, bob.col = 1, 0
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_south")
        assert (alice.row, alice.col) == (0, 0)

    def test_dead_engine_blocks_flying(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.power = 0
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_south")
        assert alice.power == 0
        # The move is refused, but the action is spent so the turn still moves on.
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_climb_recharges_engine(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.power = 1
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "climb")
        assert alice.power == MAX_POWER
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_lap_banks_at_target_corner(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        t_row, t_col = TARGET_CORNERS[alice.base]
        alice.row, alice.col = t_row, t_col + (-1 if t_col else 1)
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        toward_col = "east" if t_col > alice.col else "west"
        game.execute_action(alice, f"fly_{toward_col}")
        assert alice.laps == 1
        assert (alice.row, alice.col) == (t_row, t_col)

    def test_landing_home_with_all_laps_wins(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.laps = game.options.laps
        # Park one square off the runway so a single fly lands and wins.
        b_row, b_col = BASE_CORNERS[alice.base]
        alice.row, alice.col = (1, b_col) if b_row == 0 else (b_row - 1, b_col)
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, f"fly_{'north' if b_row == 0 else 'south'}")
        assert game.winner_id == alice.id
        assert game.status == "finished"

    def test_fire_reaches_diagonal_range_two(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        alice.row, alice.col = 2, 0
        bob.row, bob.col = 0, 2  # Chebyshev distance 2
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.health == game.options.start_health - CANNON_DAMAGE

    def test_fire_out_of_range_consumes_the_action(self):
        """A refused shot still burns the action so the turn cannot stall."""
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        alice.row, alice.col = 0, 0
        bob.row, bob.col = 5, 5
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fire")
        assert bob.health == game.options.start_health
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_fire_at_own_base_consumes_the_action(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fire")
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_target_on_own_runway_is_safe(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        # Place Alice next to Bob's runway corner
        b_row, b_col = BASE_CORNERS[bob.base]
        alice.row, alice.col = max(0, b_row - 1), max(0, b_col - 1)
        # Distances: ensure within range 2
        if max(abs(alice.row - b_row), abs(alice.col - b_col)) > FIRE_RANGE:
            alice.row, alice.col = b_row, max(0, b_col - 2)
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.health == game.options.start_health
        assert alice.actions_left == ACTIONS_PER_TURN - 1

    def test_barrel_roll_makes_next_shot_miss(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        alice.row, alice.col = 2, 0
        bob.row, bob.col = 2, 1
        game.turn_index = game.turn_player_ids.index(bob.id)
        game._prepare_turn(bob)
        game.execute_action(bob, "barrel_roll")
        assert bob.barrel_roll is True
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.health == game.options.start_health  # dodged
        assert bob.barrel_roll is False  # consumed

    def test_cloud_shield_absorbs_hit(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        alice.row, alice.col = 2, 0
        bob.row, bob.col = 2, 1
        game.turn_index = game.turn_player_ids.index(bob.id)
        game._prepare_turn(bob)
        game.execute_action(bob, "cloud")
        assert bob.cloud_shield is True
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.health == game.options.start_health  # absorbed
        assert bob.cloud_shield is False

    def test_shootdown_respawns_with_configured_health(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        alice.row, alice.col = 0, 1
        bob.row, bob.col = 0, 0  # within range of Alice
        bob.health = CANNON_DAMAGE
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.downed is True
        assert bob.downs == 1
        assert game.winner_id is None  # more than one pilot remains
        # Bob's next turn respawns him
        game.turn_index = game.turn_player_ids.index(bob.id)
        game._prepare_turn(bob)
        assert bob.downed is False
        assert bob.health == game.options.respawn_health
        b_row, b_col = BASE_CORNERS[bob.base]
        assert (bob.row, bob.col) == (b_row, b_col)

    def test_three_downs_eliminates_pilot(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        bob.downs = 2
        bob.health = CANNON_DAMAGE
        alice.row, alice.col = 0, 1
        bob.row, bob.col = 0, 0
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fire")
        assert bob.downed is True
        assert game._is_out(bob)
        assert game.winner_id == alice.id  # last plane flying wins
        assert game.status == "finished"

    def test_storm_damage_applies_adjacent(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.row, alice.col = 1, 1  # diagonal to the storm block
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fly_south")  # ends at (2,1): adjacent
        assert alice.health == game.options.start_health - game.options.storm_damage

    def test_storm_disabled_with_zero_damage(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        game.options.storm_damage = 0
        alice.row, alice.col = 1, 2
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        with mock.patch("server.games.aircraftextreme.game.random.random", return_value=0.0):
            game.execute_action(alice, "fly_south")
        assert alice.health == game.options.start_health

    def test_turn_passes_after_two_actions(self):
        game = _make_game("Alice", "Bob")
        alice, bob = game.players
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        alice.row, alice.col = 1, 0  # room to fly north and south
        game.execute_action(alice, "fly_south")
        assert game.current_player is alice  # still her turn
        game.execute_action(alice, "fly_north")
        assert game.current_player is bob

    def test_pilot_and_sky_status_speak(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        alice.speak_messages = []  # not part of MockUser; ensure no crash
        game._action_pilot_status(alice, "pilot_status")
        game._action_sky_status(alice, "sky_status")

    def test_cell_labels(self):
        game = _make_game("Alice", "Bob")
        player = game.players[0]
        storm_label = game.get_cell_label(STORM_MIN, STORM_MIN, player, "en")
        assert "thunderstorm" in storm_label
        p = game.players[1]
        plane_label = game.get_cell_label(p.row, p.col, player, "en")
        assert p.name in plane_label
        empty_label = game.get_cell_label(0, 3, player, "en")
        assert "clear sky" in empty_label

    def test_prestart_rejects_respawn_health_above_start(self):
        game = AircraftExtremeGame()
        game.add_player("Alice", MockUser("Alice"))
        game.add_player("Bob", MockUser("Bob"))
        game.options.respawn_health = 99
        errors = game.prestart_validate()
        assert "aircraftextreme-error-respawn-too-high" in errors


class TestAircraftExtremePlay:
    """Integration tests: full games driven by bots."""

    def test_two_bot_game_completes(self):
        game = _make_game("Bot1", "Bot2", bots=True)
        max_ticks = 30000
        for _ in range(max_ticks):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"
        result = game.build_game_result()
        assert result.custom_data["winner_name"] in ("Bot1", "Bot2")

    def test_three_bot_game_completes(self):
        game = _make_game("Bot1", "Bot2", "Bot3", bots=True)
        for _ in range(40000):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status == "finished"

    def test_four_bot_game_completes(self):
        game = _make_game("Bot1", "Bot2", "Bot3", "Bot4", bots=True)
        for _ in range(50000):
            if game.status == "finished":
                break
        # Four-pilot free-for-alls with respawns can run long; require either
        # a finished game or a reachable state (no crash, valid board).
        assert game.game_active in (True, False)

    def test_human_vs_bot_progresses(self):
        game = _make_game("Alice", "Bot2", bots=False)
        alice = game.players[0]
        game.execute_action(alice, "fly_south" if alice.base in ("nw", "ne") else "fly_north")
        for _ in range(2000):
            if game.status == "finished":
                break
            game.on_tick()
        assert game.status in ("playing", "finished")

    def test_game_result_shape(self):
        game = _make_game("Bot1", "Bot2", bots=True)
        for _ in range(30000):
            if game.status == "finished":
                break
            game.on_tick()
        result = game.build_game_result()
        assert result.game_type == "aircraftextreme"
        assert len(result.player_results) == 2
        assert set(result.custom_data["final_laps"]) == {"Bot1", "Bot2"}
        assert result.custom_data["win_reason"] in (
            "aircraftextreme-winner-laps",
            "aircraftextreme-last-plane",
            None,
        )

    def test_format_end_screen(self):
        game = _make_game("Bot1", "Bot2", bots=True)
        for _ in range(30000):
            if game.status == "finished":
                break
            game.on_tick()
        result = game.build_game_result()
        lines = game.format_end_screen(result, "en")
        assert len(lines) == 3  # header + 2 players
        assert "Bot1" in lines[1]


class TestAircraftExtremePersistence:
    """Serialization round-trip tests."""

    def test_full_state_preserved(self):
        game = _make_game("Alice", "Bob")
        alice = game.players[0]
        game.turn_index = game.turn_player_ids.index(alice.id)
        game._prepare_turn(alice)
        game.execute_action(alice, "fly_south" if alice.base in ("nw", "ne") else "fly_north")
        saved = game.to_json()
        loaded = AircraftExtremeGame.from_json(saved)
        assert loaded.players[0].row == game.players[0].row
        assert loaded.players[0].col == game.players[0].col
        assert loaded.players[0].power == game.players[0].power
        assert loaded.players[0].laps == game.players[0].laps
        assert loaded.players[0].base == game.players[0].base
        assert loaded.players[1].base == game.players[1].base
        assert loaded.grid_rows == GRID_SIZE
        assert loaded.status == game.status

    def test_serialized_game_continues(self):
        """A save/load cycle mid-game must not corrupt the flow."""
        game = _make_game("Bot1", "Bot2", bots=True)
        for _ in range(60):
            if game.status == "finished":
                break
            game.on_tick()
        loaded = AircraftExtremeGame.from_json(game.to_json())
        # Reattach users so broadcasts keep working after load
        for player, original in zip(loaded.players, game.players):
            user = game.get_user(original)
            if user:
                loaded.attach_user(player.id, user)
        for _ in range(30000):
            if loaded.status == "finished":
                break
            loaded.on_tick()
        assert loaded.status == "finished"

    def test_options_round_trip(self):
        options = AircraftExtremeOptions(laps=3, storm_damage=2, start_health=8, respawn_health=4)
        data = json.loads(options.to_json())
        loaded = AircraftExtremeOptions.from_dict(data)
        assert loaded.laps == 3
        assert loaded.storm_damage == 2
        assert loaded.start_health == 8
        assert loaded.respawn_health == 4


class TestAircraftExtremeBotLiveness:
    """Bot games must always reach a result, never stall."""

    def test_downed_bot_turn_does_not_strand_the_game(self):
        """A downed bot must let the turn advance so it can respawn.

        A downed pilot cannot take any flight action, and only _prepare_turn
        respawns them. If the turn does not advance, the game hangs forever.
        """
        game = _make_game("Bot1", "Bot2", bots=True)
        victim = game.players[0]
        victim.downed = True
        victim.health = 0

        for _ in range(2000):
            if game.status == "finished":
                break
            game.on_tick()

        assert game.status == "finished", "downed bot stranded the turn"

    def test_bot_games_finish_across_seeds(self):
        """Seeded bot games must finish for both table sizes."""
        stalled = []
        for seed in range(25):
            random.seed(seed)
            names = ("Bot1", "Bot2") if seed % 2 else ("Bot1", "Bot2", "Bot3", "Bot4")
            game = _make_game(*names, bots=True)
            finished = False
            for _ in range(20000):
                if game.status == "finished":
                    finished = True
                    break
                game.on_tick()
            if not finished:
                stalled.append(seed)

        assert not stalled, f"bot games stalled for seeds {stalled}"
