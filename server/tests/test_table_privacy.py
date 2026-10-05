"""Tests for private and password-protected tables."""

import pytest

from server.core.tables.manager import TableManager
from server.core.tables.table import (
    TABLE_VISIBILITY_PRIVATE,
    TABLE_VISIBILITY_PUBLIC,
    Table,
)
from server.persistence.database import Database


def make_table(table_id="t1", host="host", visibility=TABLE_VISIBILITY_PUBLIC, password=None):
    table = Table(
        table_id=table_id,
        game_type="poker",
        host=host,
        visibility=visibility,
        password=password,
    )
    return table


# -- Visibility ------------------------------------------------------------


def test_a_public_table_with_no_password_is_visible_to_everyone():
    table = make_table()
    assert table.is_visible_to("anyone") is True
    assert table.is_visible_to("host") is True


def test_a_private_table_is_hidden_from_other_players():
    table = make_table(visibility=TABLE_VISIBILITY_PRIVATE)

    assert table.is_visible_to("stranger") is False
    assert table.is_visible_to("host") is True


def test_a_private_table_is_visible_to_members_already_seated():
    table = make_table(host="host", visibility=TABLE_VISIBILITY_PRIVATE)
    table.add_member("friend", object())

    assert table.is_visible_to("friend") is True
    assert table.is_visible_to("stranger") is False


def test_a_password_table_is_hidden_from_other_players():
    table = make_table(password="hunter2")

    assert table.is_visible_to("stranger") is False
    assert table.is_visible_to("host") is True


# -- Join enforcement ------------------------------------------------------


def test_anyone_may_join_a_plain_table():
    assert make_table().can_join("stranger") == (True, "")


def test_a_private_table_refuses_strangers():
    allowed, reason = make_table(visibility=TABLE_VISIBILITY_PRIVATE).can_join("stranger")
    assert allowed is False
    assert reason == "private"


def test_a_private_table_still_admits_its_host():
    assert make_table(host="host", visibility=TABLE_VISIBILITY_PRIVATE).can_join("host")[0] is True


def test_a_password_table_refuses_a_stranger_with_no_password():
    allowed, reason = make_table(password="hunter2").can_join("stranger")
    assert allowed is False
    assert reason == "password"


def test_a_password_table_refuses_the_wrong_password():
    allowed, reason = make_table(password="hunter2").can_join("stranger", "wrong")
    assert allowed is False
    assert reason == "password"


def test_a_password_table_admits_the_right_password():
    assert make_table(password="hunter2").can_join("stranger", "hunter2") == (True, "")


def test_a_private_table_refuses_even_the_correct_password():
    """Private hides the table outright; a password is not a key to it."""
    table = make_table(visibility=TABLE_VISIBILITY_PRIVATE, password="hunter2")
    assert table.can_join("stranger", "hunter2") == (False, "private")


def test_a_password_never_locks_out_the_host():
    table = make_table(host="host", password="hunter2")
    assert table.can_join("host") == (True, "")


def test_a_password_never_locks_out_a_seated_member():
    table = make_table(host="host", password="hunter2")
    table.add_member("friend", object())
    assert table.can_join("friend") == (True, "")


def test_password_matching_is_exact():
    table = make_table(password="Hunter2")
    assert table.password_matches("Hunter2") is True
    assert table.password_matches("hunter2") is False
    assert table.password_matches("hunter2 ") is False
    assert table.password_matches("") is False


def test_a_table_with_no_password_matches_nothing():
    assert make_table().password_matches("anything") is False


# -- Listing ---------------------------------------------------------------


def _waiting_manager():
    manager = TableManager()
    public = make_table("pub", host="host")
    private = make_table("priv", host="host", visibility=TABLE_VISIBILITY_PRIVATE)
    locked = make_table("lock", host="host", password="pw")
    for table in (public, private, locked):
        manager.add_table(table)
    return manager


def test_listing_hides_tables_a_player_cannot_join():
    manager = _waiting_manager()
    listed = {t.table_id for t in manager.get_waiting_tables(username="stranger")}
    assert listed == {"pub"}


def test_listing_shows_the_host_their_own_protected_tables():
    manager = _waiting_manager()
    listed = {t.table_id for t in manager.get_waiting_tables(username="host")}
    assert listed == {"pub", "priv", "lock"}


def test_listing_without_a_username_keeps_every_table():
    """The virtual bots and CLI still see everything."""
    manager = _waiting_manager()
    assert len(manager.get_waiting_tables()) == 3


def test_listing_still_filters_by_game_type():
    manager = TableManager()
    manager.add_table(make_table("chess-one", host="h", password="pw"))
    other = make_table("go-one", host="h")
    other.game_type = "go"
    manager.add_table(other)

    listed = {t.table_id for t in manager.get_waiting_tables("go", username="stranger")}
    assert listed == {"go-one"}


# -- Persistence round trip ------------------------------------------------
#
# Table's own mashumaro to_json/from_json cannot resolve the TYPE_CHECKING-only
# "Game" reference, so persistence is exercised through the database, which is
# how tables are actually stored between restarts.


@pytest.fixture
def db(tmp_path):
    database = Database(db_path=tmp_path / "privacy.db")
    database.connect()
    try:
        yield database
    finally:
        database.close()


def test_visibility_and_password_survive_a_restart(db):
    table = make_table(visibility=TABLE_VISIBILITY_PRIVATE, password="hunter2")
    db.save_table(table)

    restored = db.load_table("t1")

    assert restored is not None
    assert restored.visibility == TABLE_VISIBILITY_PRIVATE
    assert restored.password == "hunter2"
    assert restored.is_private is True
    assert restored.has_password is True


def test_a_plain_table_stays_public_and_open_across_a_restart(db):
    db.save_table(make_table())

    restored = db.load_table("t1")

    assert restored.visibility == TABLE_VISIBILITY_PUBLIC
    assert restored.password is None


def test_load_all_tables_keeps_protection(db):
    db.save_table(make_table("a", visibility=TABLE_VISIBILITY_PRIVATE))
    db.save_table(make_table("b", password="pw"))

    restored = {t.table_id: t for t in db.load_all_tables()}

    assert restored["a"].is_private is True
    assert restored["b"].password == "pw"


def test_an_existing_database_gains_the_new_columns(tmp_path):
    """A database created before this feature must migrate cleanly."""
    import sqlite3

    path = tmp_path / "old.db"
    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE tables (
            table_id TEXT PRIMARY KEY,
            game_type TEXT NOT NULL,
            host TEXT NOT NULL,
            members_json TEXT NOT NULL,
            game_json TEXT,
            status TEXT DEFAULT 'waiting'
        )
        """
    )
    connection.execute(
        "INSERT INTO tables (table_id, game_type, host, members_json) VALUES (?, ?, ?, ?)",
        ("legacy", "poker", "host", "[]"),
    )
    connection.commit()
    connection.close()

    database = Database(db_path=path)
    database.connect()
    try:
        restored = database.load_table("legacy")
        assert restored is not None
        assert restored.visibility == TABLE_VISIBILITY_PUBLIC, "existing tables stay public"
        assert restored.password is None
    finally:
        database.close()