"""
Migration script: transfer data from an existing SQLite database to Supabase PostgreSQL.

Usage:
    uv run python tools/migrate_sqlite_to_postgres.py \\
        --sqlite-path var/server/playpalace.db \\
        --pg-url "postgresql://user:password@host:5432/db"
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg import rows


def _sqlite_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _pg_conn(pg_url: str):
    return psycopg.connect(pg_url, autocommit=True)


def _table_exists(cur, name: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (name,)
    )
    return cur.fetchone() is not None


def create_pg_tables(cur) -> None:
    """Create PostgreSQL tables matching the new schema."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            uuid TEXT NOT NULL,
            locale TEXT DEFAULT 'en',
            preferences_json TEXT DEFAULT '{}',
            trust_level INTEGER DEFAULT 1,
            approved INTEGER DEFAULT 0,
            fluent_languages TEXT DEFAULT '[]'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transcriber_assignments (
            user_id INTEGER NOT NULL,
            lang_code TEXT NOT NULL,
            PRIMARY KEY (user_id, lang_code),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            table_id TEXT PRIMARY KEY,
            game_type TEXT NOT NULL,
            host TEXT NOT NULL,
            members_json TEXT NOT NULL,
            game_json TEXT,
            status TEXT DEFAULT 'waiting'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_tables (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            save_name TEXT NOT NULL,
            game_type TEXT NOT NULL,
            game_json TEXT NOT NULL,
            members_json TEXT NOT NULL,
            saved_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_results (
            id SERIAL PRIMARY KEY,
            game_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            duration_ticks INTEGER,
            custom_data TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS game_result_players (
            id SERIAL PRIMARY KEY,
            result_id INTEGER REFERENCES game_results(id) ON DELETE CASCADE,
            player_id TEXT NOT NULL,
            player_name TEXT NOT NULL,
            is_bot INTEGER NOT NULL,
            is_virtual_bot INTEGER NOT NULL DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_ratings (
            player_id TEXT NOT NULL,
            game_type TEXT NOT NULL,
            mu REAL NOT NULL,
            sigma REAL NOT NULL,
            PRIMARY KEY (player_id, game_type)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            revoked_at INTEGER,
            replaced_by TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS virtual_bots (
            name TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            online_ticks INTEGER NOT NULL DEFAULT 0,
            target_online_ticks INTEGER NOT NULL DEFAULT 0,
            table_id TEXT,
            game_join_tick INTEGER NOT NULL DEFAULT 0
        )
    """)

    # Indexes
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_game_results_type ON game_results(game_type)",
        "CREATE INDEX IF NOT EXISTS idx_game_results_timestamp ON game_results(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_result_players_player ON game_result_players(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_username ON refresh_tokens(username)",
        "CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at)",
    ]:
        cur.execute(idx_sql)


def migrate_table(
    sqlite: sqlite3.Connection,
    pg_conn,
    table: str,
    columns: list[str],
    insert_sql: str | None = None,
    transform: callable | None = None,
) -> int:
    """Migrate rows from SQLite to PostgreSQL.

    Args:
        sqlite: Source SQLite connection.
        pg_conn: Destination PostgreSQL connection.
        table: Table name.
        columns: Column names to select/insert.
        insert_sql: Optional custom INSERT SQL. If None, auto-generates.
        transform: Optional function to transform each row dict before insert.

    Returns:
        Number of rows migrated.
    """
    sqlite_cur = sqlite.cursor()
    placeholders = ", ".join(f"%s" for _ in columns)
    col_list = ", ".join(columns)

    if insert_sql is None:
        insert_sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        )

    sqlite_cur.execute(f"SELECT {col_list} FROM {table}")
    rows_data = sqlite_cur.fetchall()

    if not rows_data:
        return 0

    with pg_conn.cursor() as pg_cur:
        for row in rows_data:
            row_dict = dict(row)
            if transform:
                row_dict = transform(row_dict, row_dict)
            values = [row_dict[c] for c in columns]
            try:
                pg_cur.execute(insert_sql, values)
            except Exception as exc:
                print(f"  Error migrating {table} row: {exc}", file=sys.stderr)
                print(f"  Row: {row_dict}", file=sys.stderr)
                raise

    return len(rows_data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate from SQLite to Supabase PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        default="var/server/playpalace.db",
        help="Path to existing SQLite database",
    )
    parser.add_argument(
        "--pg-url",
        required=True,
        help="Supabase PostgreSQL connection string",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found at {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to SQLite: {sqlite_path}")
    sqlite = _sqlite_conn(str(sqlite_path))

    print(f"Connecting to PostgreSQL...")
    pg = _pg_conn(args.pg_url)

    try:
        # Create tables in PostgreSQL
        with pg.cursor() as cur:
            create_pg_tables(cur)
        pg.commit()
        print("PostgreSQL tables ready.")

        # Migrate each table
        migrations = [
            ("users", ["username", "password_hash", "uuid", "locale", "preferences_json", "trust_level", "approved", "fluent_languages"]),
            ("transcriber_assignments", ["user_id", "lang_code"]),
            ("tables", ["table_id", "game_type", "host", "members_json", "game_json", "status"]),
            ("saved_tables", ["username", "save_name", "game_type", "game_json", "members_json", "saved_at"]),
            ("game_results", ["game_type", "timestamp", "duration_ticks", "custom_data"]),
            ("game_result_players", ["result_id", "player_id", "player_name", "is_bot", "is_virtual_bot"]),
            ("player_ratings", ["player_id", "game_type", "mu", "sigma"]),
            ("refresh_tokens", ["username", "token", "expires_at", "created_at", "revoked_at", "replaced_by"]),
            ("virtual_bots", ["name", "state", "online_ticks", "target_online_ticks", "table_id", "game_join_tick"]),
        ]

        total = 0
        for table, columns in migrations:
            count = migrate_table(sqlite, pg, table, columns)
            if count:
                print(f"  {table}: {count} rows migrated")
            else:
                print(f"  {table}: (empty or does not exist)")
            total += count

        pg.commit()
        print(f"\nMigration complete. {total} total rows migrated.")

    except Exception as exc:
        print(f"ERROR during migration: {exc}", file=sys.stderr)
        pg.rollback()
        sys.exit(1)
    finally:
        sqlite.close()
        pg.close()


if __name__ == "__main__":
    main()
