"""Tests for the host-facing table privacy actions in the shared lobby menu."""

import pytest

from server.game_utils.actions import Visibility
from server.core.tables.table import TABLE_VISIBILITY_PRIVATE, Table

from server.games.tictactoe.game import TicTacToeGame
from server.core.users.test_user import MockUser
from server.core.users.bot import Bot


@pytest.fixture
def game():
    """A real game seated at a real table, as the server would build it."""
    table = Table(table_id="t1", game_type="tictactoe", host="host")
    instance = TicTacToeGame()
    instance._table = table
    instance.initialize_lobby("host", MockUser("host"))
    return instance


def _seat(game, name):
    game.add_player(name, MockUser(name))


def test_the_host_is_offered_both_table_controls(game):
    host_player = game.players[0]

    assert game._is_toggle_table_private_enabled(host_player) is None
    assert game._is_set_table_password_enabled(host_player) is None
    assert game._is_toggle_table_private_hidden(host_player) == Visibility.VISIBLE
    assert game._is_set_table_password_hidden(host_player) == Visibility.VISIBLE


def test_non_hosts_are_neither_shown_nor_enabled(game):
    _seat(game, "guest")
    guest = game.players[1]

    assert game._is_toggle_table_private_enabled(guest) == "action-not-host"
    assert game._is_set_table_password_enabled(guest) == "action-not-host"
    assert game._is_toggle_table_private_hidden(guest) == Visibility.HIDDEN
    assert game._is_set_table_password_hidden(guest) == Visibility.HIDDEN


def test_the_controls_disappear_once_the_game_starts(game):
    host_player = game.players[0]
    game.status = "playing"

    assert game._is_toggle_table_private_enabled(host_player) == "action-game-in-progress"
    assert game._is_set_table_password_enabled(host_player) == "action-game-in-progress"
    assert game._is_toggle_table_private_hidden(host_player) == Visibility.HIDDEN
    assert game._is_set_table_password_hidden(host_player) == Visibility.HIDDEN


def test_the_private_label_says_what_pressing_it_will_do(game):
    host_player = game.players[0]

    assert "private" in game._get_toggle_table_private_label(host_player, "toggle_table_private").lower()

    game._table.set_visibility(True)
    assert "public" in game._get_toggle_table_private_label(host_player, "toggle_table_private").lower()


def test_the_host_toggling_privacy_flips_the_table(game):
    host_player = game.players[0]

    game._action_toggle_table_private(host_player, "toggle_table_private")
    assert game._table.visibility == TABLE_VISIBILITY_PRIVATE

    game._action_toggle_table_private(host_player, "toggle_table_private")
    assert game._table.is_private is False


def test_the_host_can_set_and_clear_a_password(game):
    host_player = game.players[0]

    game._action_set_table_password(host_player, "hunter2", "set_table_password")
    assert game._table.password == "hunter2"
    assert game._table.has_password is True

    # Submitting a blank password is how a host removes the requirement.
    game._action_set_table_password(host_player, "   ", "set_table_password")
    assert game._table.password is None
    assert game._table.has_password is False


def test_a_password_is_stripped_of_surrounding_whitespace(game):
    host_player = game.players[0]
    game._action_set_table_password(host_player, "  hunter2  ", "set_table_password")
    assert game._table.password == "hunter2"


def test_the_host_is_told_what_changed(game):
    host_player = game.players[0]
    user = game.get_user(host_player)

    def spoken():
        return [
            message.data.get("text", "")
            for message in user.messages
            if message.type == "speak"
        ]

    game._action_toggle_table_private(host_player, "toggle_table_private")
    assert any("private" in text.lower() for text in spoken()), spoken()

    before = len(spoken())
    game._action_set_table_password(host_player, "hunter2", "set_table_password")
    assert len(spoken()) > before, "setting a password should say something"
    assert any("password" in text.lower() for text in spoken()), spoken()


def test_a_game_with_no_table_does_not_crash(game):
    host_player = game.players[0]
    game._table = None

    # Should be a no-op rather than raising.
    game._action_toggle_table_private(host_player, "toggle_table_private")
    game._action_set_table_password(host_player, "hunter2", "set_table_password")


def test_both_controls_are_registered_on_every_game_lobby(game):
    action_set = game.create_lobby_action_set(game.players[0])
    ids = [action.id for action in action_set._actions.values()]

    assert "toggle_table_private" in ids
    assert "set_table_password" in ids

    password_action = action_set.get_action("set_table_password")
    assert password_action.input_request is not None, "setting a password must prompt for text"
    assert password_action.input_request.prompt == "enter-table-password"


def test_the_settings_survive_the_menu_being_rebuilt(game):
    host_player = game.players[0]
    game._action_set_table_password(host_player, "hunter2", "set_table_password")
    game._action_toggle_table_private(host_player, "toggle_table_private")

    game.rebuild_all_menus()

    assert game._table.password == "hunter2"
    assert game._table.is_private is True