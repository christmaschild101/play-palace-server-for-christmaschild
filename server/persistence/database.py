"""Database persistence layer supporting PostgreSQL and SQLite backends.

Production uses PostgreSQL via Supabase (psycopg).
Testing/development can use SQLite via a file path.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid as uuid_module
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg import rows
try:
    from psycopg.pool import ConnectionPool
except ImportError:
    from psycopg_pool import ConnectionPool

if TYPE_CHECKING:
    from server.core.tables.table import Table
    from server.core.users.base import TrustLevel


def _trust_level_enum():
    from server.core.users.base import TrustLevel
    return TrustLevel


@dataclass
class UserRecord:
    id: int
    username: str
    password_hash: str
    uuid: str
    locale: str = "en"
    preferences_json: str = "{}"
    trust_level: int = 1  # _trust_level_enum().USER.value
    approved: bool = False
    fluent_languages: list[str] = field(default_factory=list)


@dataclass
class SavedTableRecord:
    id: int
    username: str
    save_name: str
    game_type: str
    game_json: str
    members_json: str
    saved_at: str


@dataclass
class RefreshTokenRecord:
    username: str
    token: str
    expires_at: int
    created_at: int
    revoked_at: int | None = None
    replaced_by: str | None = None


def _token_from_row(row: dict) -> RefreshTokenRecord:
    return RefreshTokenRecord(
        username=row["username"],
        token=row["token"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
        revoked_at=row.get("revoked_at"),
        replaced_by=row.get("replaced_by"),
    )


_USER_COLUMNS = (
    "id, username, password_hash, uuid, locale, "
    "preferences_json, trust_level, approved, fluent_languages"
)


# ---------------------------------------------------------------------------
# SQLite backend (testing / dev)
# ---------------------------------------------------------------------------


class _SqliteBackend:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __sql(self, query: str) -> str:
        """Convert %s placeholders to ? for sqlite3."""
        return query.replace("%s", "?")

    def _to_dict(self, row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return dict(row)

    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        assert self._conn
        cur = self._conn.execute(self.__sql(query), params)
        return [dict(r) for r in cur.fetchall()]

    def execute_one(self, query: str, params: tuple = ()) -> dict | None:
        assert self._conn
        cur = self._conn.execute(self.__sql(query), params)
        row = cur.fetchone()
        return dict(row) if row else None

    def execute_insert(self, query: str, params: tuple = ()) -> int | None:
        assert self._conn
        cur = self._conn.execute(self.__sql(query), params)
        cur.fetchall()
        self._conn.commit()
        return cur.lastrowid

    def execute_commit(self, query: str, params: tuple = ()) -> None:
        assert self._conn
        self._conn.execute(self.__sql(query), params)
        self._conn.commit()

    @property
    def unique_violation(self) -> type[Exception]:
        return sqlite3.IntegrityError

    def _create_tables(self) -> None:
        assert self._conn
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                uuid TEXT NOT NULL,
                locale TEXT DEFAULT 'en',
                preferences_json TEXT DEFAULT '{}',
                trust_level INTEGER DEFAULT 1,
                approved INTEGER DEFAULT 0,
                fluent_languages TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS transcriber_assignments (
                user_id INTEGER NOT NULL,
                lang_code TEXT NOT NULL,
                PRIMARY KEY (user_id, lang_code),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tables (
                table_id TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                host TEXT NOT NULL,
                members_json TEXT NOT NULL,
                game_json TEXT,
                status TEXT DEFAULT 'waiting'
            );

            CREATE TABLE IF NOT EXISTS saved_tables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                save_name TEXT NOT NULL,
                game_type TEXT NOT NULL,
                game_json TEXT NOT NULL,
                members_json TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS game_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration_ticks INTEGER,
                custom_data TEXT
            );

            CREATE TABLE IF NOT EXISTS game_result_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER REFERENCES game_results(id) ON DELETE CASCADE,
                player_id TEXT NOT NULL,
                player_name TEXT NOT NULL,
                is_bot INTEGER NOT NULL,
                is_virtual_bot INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_game_results_type ON game_results(game_type);
            CREATE INDEX IF NOT EXISTS idx_game_results_timestamp ON game_results(timestamp);
            CREATE INDEX IF NOT EXISTS idx_result_players_player ON game_result_players(player_id);

            CREATE TABLE IF NOT EXISTS player_ratings (
                player_id TEXT NOT NULL,
                game_type TEXT NOT NULL,
                mu REAL NOT NULL,
                sigma REAL NOT NULL,
                PRIMARY KEY (player_id, game_type)
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER,
                replaced_by TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_username ON refresh_tokens(username);
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);

            CREATE TABLE IF NOT EXISTS virtual_bots (
                name TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                online_ticks INTEGER NOT NULL DEFAULT 0,
                target_online_ticks INTEGER NOT NULL DEFAULT 0,
                table_id TEXT,
                game_join_tick INTEGER NOT NULL DEFAULT 0
            );
        """)
        self._conn.commit()


# ---------------------------------------------------------------------------
# PostgreSQL backend (production via Supabase)
# ---------------------------------------------------------------------------


class _PostgresBackend:
    def __init__(self, db_url: str, pool_min: int = 2, pool_max: int = 10):
        self._db_url = db_url
        self._pool_min = pool_min
        self._pool_max = pool_max
        self._pool: ConnectionPool | None = None

    def connect(self) -> None:
        try:
            self._pool = ConnectionPool(
                self._db_url,
                min_size=self._pool_min,
                max_size=self._pool_max,
                open=True,
            )
        except psycopg.Error as exc:
            print(f"ERROR: Failed to connect to database: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        self._create_tables()

    def close(self) -> None:
        if self._pool:
            self._pool.close()
            self._pool = None

    def _get_pool(self) -> ConnectionPool:
        if self._pool is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    def execute(self, query: str, params: tuple = ()) -> list[dict]:
        with self._get_pool().connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(query, params)
                if cur.description is not None and cur.rowcount > -1:
                    return cur.fetchall()
                return []

    def execute_one(self, query: str, params: tuple = ()) -> dict | None:
        with self._get_pool().connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(query, params)
                if cur.description is not None:
                    return cur.fetchone()
                return None

    def execute_insert(self, query: str, params: tuple = ()) -> int | None:
        with self._get_pool().connection() as conn:
            with conn.cursor(row_factory=rows.dict_row) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                conn.commit()
                return row["id"] if row else None

    def execute_commit(self, query: str, params: tuple = ()) -> None:
        with self._get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                conn.commit()

    @property
    def unique_violation(self) -> type[Exception]:
        return psycopg.errors.UniqueViolation

    def _create_tables(self) -> None:
        with self._get_pool().connection() as conn:
            with conn.cursor() as cur:
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
                    CREATE INDEX IF NOT EXISTS idx_game_results_type
                    ON game_results(game_type)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_game_results_timestamp
                    ON game_results(timestamp)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_result_players_player
                    ON game_result_players(player_id)
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
                    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_username
                    ON refresh_tokens(username)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires
                    ON refresh_tokens(expires_at)
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
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_lower
                    ON users(lower(username))
                """)
                conn.commit()


# ---------------------------------------------------------------------------
# Public Database class
# ---------------------------------------------------------------------------


class Database:
    """Database persistence for PlayPalace.

    Auto-detects backend based on the connection string:
    - ``postgresql://...`` → PostgreSQL via psycopg (production)
    - file path → SQLite via sqlite3 (testing / local dev)
    """

    def __init__(
        self,
        db_url: str | None = None,
        *,
        pool_min: int = 2,
        pool_max: int = 10,
        db_path: str | None = None,
    ):
        resolved = str(db_url or db_path)
        if not resolved:
            raise ValueError("Either db_url or db_path must be provided.")
        if resolved.startswith("postgresql://"):
            self._backend: _PostgresBackend | _SqliteBackend = _PostgresBackend(
                resolved, pool_min=pool_min, pool_max=pool_max
            )
        else:
            self._backend = _SqliteBackend(resolved)

    def connect(self) -> None:
        self._backend.connect()

    def close(self) -> None:
        self._backend.close()

    @property
    def _conn(self):
        """Backward-compatible access to the underlying connection (SQLite)."""
        if isinstance(self._backend, _SqliteBackend):
            return self._backend._conn
        raise RuntimeError("_conn is only available in SQLite mode")

    # -- Internal query helpers (delegated to backend) -----------------------

    def _execute(self, query: str, params: tuple = ()) -> list[dict]:
        return self._backend.execute(query, params)

    def _execute_one(self, query: str, params: tuple = ()) -> dict | None:
        return self._backend.execute_one(query, params)

    def _execute_insert(self, query: str, params: tuple = ()) -> int | None:
        return self._backend.execute_insert(query, params)

    def _execute_commit(self, query: str, params: tuple = ()) -> None:
        self._backend.execute_commit(query, params)

    # ------------------------------------------------------------------
    # User operations
    # ------------------------------------------------------------------

    @staticmethod
    def _user_from_row(row: dict) -> UserRecord:
        trust_level_int = row["trust_level"] if row["trust_level"] is not None else 1
        return UserRecord(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            uuid=row["uuid"],
            locale=row["locale"] or "en",
            preferences_json=row["preferences_json"] or "{}",
            trust_level=_trust_level_enum()(trust_level_int),
            approved=bool(row["approved"]) if row["approved"] is not None else False,
            fluent_languages=json.loads(row["fluent_languages"] or "[]"),
        )

    def get_user(self, username: str) -> UserRecord | None:
        row = self._execute_one(
            f"SELECT {_USER_COLUMNS} FROM users WHERE lower(username) = lower(%s)",
            (username,),
        )
        return self._user_from_row(row) if row else None

    def create_user(
        self,
        username: str,
        password_hash: str,
        locale: str = "en",
        trust_level: _trust_level_enum() = _trust_level_enum().USER,
        approved: bool = False,
    ) -> UserRecord:
        user_uuid = str(uuid_module.uuid4())
        user_id = self._execute_insert(
            "INSERT INTO users (username, password_hash, uuid, locale, trust_level, approved) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (username, password_hash, user_uuid, locale, trust_level.value, 1 if approved else 0),
        )
        return UserRecord(
            id=user_id,
            username=username,
            password_hash=password_hash,
            uuid=user_uuid,
            locale=locale,
            trust_level=trust_level,
            approved=approved,
        )

    def user_exists(self, username: str) -> bool:
        row = self._execute_one(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s)", (username,)
        )
        return row is not None

    def update_user_locale(self, username: str, locale: str) -> None:
        self._execute_commit(
            "UPDATE users SET locale = %s WHERE lower(username) = lower(%s)", (locale, username)
        )

    def update_user_preferences(self, username: str, preferences_json: str) -> None:
        self._execute_commit(
            "UPDATE users SET preferences_json = %s WHERE lower(username) = lower(%s)",
            (preferences_json, username),
        )

    def update_user_password(self, username: str, password_hash: str) -> None:
        self._execute_commit(
            "UPDATE users SET password_hash = %s WHERE lower(username) = lower(%s)",
            (password_hash, username),
        )

    def get_user_count(self) -> int:
        row = self._execute_one("SELECT COUNT(*) AS count FROM users")
        return row["count"] if row else 0

    def initialize_trust_levels(self) -> str | None:
        rows_without = self._execute(
            "SELECT id, username FROM users WHERE trust_level IS NULL"
        )
        promoted_user = None

        if len(rows_without) == 1:
            total = self.get_user_count()
            if total == 1:
                username = rows_without[0]["username"]
                self._execute_commit(
                    "UPDATE users SET trust_level = %s WHERE id = %s",
                    (_trust_level_enum().SERVER_OWNER.value, rows_without[0]["id"]),
                )
                promoted_user = username

        self._execute_commit(
            "UPDATE users SET trust_level = %s WHERE trust_level IS NULL",
            (_trust_level_enum().USER.value,),
        )
        return promoted_user

    def update_user_trust_level(self, username: str, trust_level: _trust_level_enum()) -> None:
        self._execute_commit(
            "UPDATE users SET trust_level = %s WHERE lower(username) = lower(%s)",
            (trust_level.value, username),
        )

    def get_pending_users(self, exclude_banned: bool = True) -> list[UserRecord]:
        if exclude_banned:
            rows = self._execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE approved = 0 AND trust_level > %s",
                (_trust_level_enum().BANNED.value,),
            )
        else:
            rows = self._execute(f"SELECT {_USER_COLUMNS} FROM users WHERE approved = 0")
        return [self._user_from_row(row) for row in rows]

    def get_banned_users(self) -> list[UserRecord]:
        rows = self._execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE trust_level = %s",
            (_trust_level_enum().BANNED.value,),
        )
        return [self._user_from_row(row) for row in rows]

    def approve_user(self, username: str) -> bool:
        self._execute_commit(
            "UPDATE users SET approved = 1 WHERE lower(username) = lower(%s)", (username,)
        )
        row = self._execute_one(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s) AND approved = 1",
            (username,),
        )
        return row is not None

    def delete_user(self, username: str) -> bool:
        row = self._execute_one(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s)", (username,)
        )
        if not row:
            return False
        self._execute_commit(
            "DELETE FROM users WHERE lower(username) = lower(%s)", (username,)
        )
        return True

    def get_non_admin_users(self, exclude_banned: bool = True) -> list[UserRecord]:
        if exclude_banned:
            rows = self._execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE approved = 1 "
                "AND trust_level > %s AND trust_level < %s ORDER BY username",
                (_trust_level_enum().BANNED.value, _trust_level_enum().ADMIN.value),
            )
        else:
            rows = self._execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE approved = 1 "
                "AND trust_level < %s ORDER BY username",
                (_trust_level_enum().ADMIN.value,),
            )
        return [self._user_from_row(row) for row in rows]

    def get_server_owner(self) -> UserRecord | None:
        row = self._execute_one(
            f"SELECT {_USER_COLUMNS} FROM users WHERE trust_level = %s",
            (_trust_level_enum().SERVER_OWNER.value,),
        )
        return self._user_from_row(row) if row else None

    def get_admin_users(self, include_server_owner: bool = True) -> list[UserRecord]:
        if include_server_owner:
            rows = self._execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE trust_level >= %s ORDER BY username",
                (_trust_level_enum().ADMIN.value,),
            )
        else:
            rows = self._execute(
                f"SELECT {_USER_COLUMNS} FROM users WHERE trust_level = %s ORDER BY username",
                (_trust_level_enum().ADMIN.value,),
            )
        return [self._user_from_row(row) for row in rows]

    # ------------------------------------------------------------------
    # Fluent languages operations
    # ------------------------------------------------------------------

    def get_user_fluent_languages(self, username: str) -> list[str]:
        row = self._execute_one(
            "SELECT fluent_languages FROM users WHERE lower(username) = lower(%s)",
            (username,),
        )
        if row:
            return json.loads(row["fluent_languages"] or "[]")
        return []

    def set_user_fluent_languages(self, username: str, languages: list[str]) -> None:
        self._execute_commit(
            "UPDATE users SET fluent_languages = %s WHERE lower(username) = lower(%s)",
            (json.dumps(languages), username),
        )

    # ------------------------------------------------------------------
    # Transcriber assignment operations
    # ------------------------------------------------------------------

    def get_transcriber_languages(self, username: str) -> list[str]:
        rows = self._execute(
            "SELECT ta.lang_code FROM transcriber_assignments ta "
            "JOIN users u ON ta.user_id = u.id "
            "WHERE lower(u.username) = lower(%s) ORDER BY ta.lang_code",
            (username,),
        )
        return [row["lang_code"] for row in rows]

    def add_transcriber_assignment(self, username: str, lang_code: str) -> bool:
        user_row = self._execute_one(
            "SELECT id FROM users WHERE lower(username) = lower(%s)", (username,)
        )
        if not user_row:
            return False
        user_id = user_row["id"]
        try:
            self._execute_commit(
                "INSERT INTO transcriber_assignments (user_id, lang_code) VALUES (%s, %s)",
                (user_id, lang_code),
            )
            return True
        except self._backend.unique_violation:
            return False

    def remove_transcriber_assignment(self, username: str, lang_code: str) -> bool:
        user_row = self._execute_one(
            "SELECT id FROM users WHERE lower(username) = lower(%s)", (username,)
        )
        if not user_row:
            return False
        user_id = user_row["id"]
        exists = self._execute_one(
            "SELECT 1 FROM transcriber_assignments WHERE user_id = %s AND lang_code = %s",
            (user_id, lang_code),
        )
        if not exists:
            return False
        self._execute_commit(
            "DELETE FROM transcriber_assignments WHERE user_id = %s AND lang_code = %s",
            (user_id, lang_code),
        )
        return True

    def get_transcribers_for_language(self, lang_code: str) -> list[str]:
        rows = self._execute(
            "SELECT u.username FROM transcriber_assignments ta "
            "JOIN users u ON ta.user_id = u.id "
            "WHERE ta.lang_code = %s ORDER BY u.username",
            (lang_code,),
        )
        return [row["username"] for row in rows]

    def get_all_transcribers(self) -> dict[str, list[str]]:
        rows = self._execute(
            "SELECT u.username, ta.lang_code FROM transcriber_assignments ta "
            "JOIN users u ON ta.user_id = u.id "
            "ORDER BY u.username, ta.lang_code"
        )
        result: dict[str, list[str]] = {}
        for row in rows:
            result.setdefault(row["username"], []).append(row["lang_code"])
        return result

    # ------------------------------------------------------------------
    # Table operations
    # ------------------------------------------------------------------

    def save_table(self, table: Table) -> None:
        members_json = json.dumps(
            [{"username": m.username, "is_spectator": m.is_spectator} for m in table.members]
        )
        self._execute_commit(
            "INSERT INTO tables (table_id, game_type, host, members_json, game_json, status) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (table_id) DO UPDATE SET "
            "game_type = EXCLUDED.game_type, host = EXCLUDED.host, "
            "members_json = EXCLUDED.members_json, game_json = EXCLUDED.game_json, "
            "status = EXCLUDED.status",
            (table.table_id, table.game_type, table.host, members_json, table.game_json, table.status),
        )

    def load_table(self, table_id: str) -> Table | None:
        row = self._execute_one("SELECT * FROM tables WHERE table_id = %s", (table_id,))
        if not row:
            return None

        members_data = json.loads(row["members_json"])
        from server.core.tables.table import Table, TableMember

        members = [
            TableMember(username=m["username"], is_spectator=m["is_spectator"])
            for m in members_data
        ]

        return Table(
            table_id=row["table_id"],
            game_type=row["game_type"],
            host=row["host"],
            members=members,
            game_json=row["game_json"],
            status=row["status"],
        )

    def load_all_tables(self) -> list[Table]:
        rows = self._execute("SELECT table_id FROM tables")
        tables = []
        for r in rows:
            table = self.load_table(r["table_id"])
            if table:
                tables.append(table)
        return tables

    def delete_table(self, table_id: str) -> None:
        self._execute_commit("DELETE FROM tables WHERE table_id = %s", (table_id,))

    def delete_all_tables(self) -> None:
        self._execute_commit("DELETE FROM tables")

    def save_all_tables(self, tables: list[Table]) -> None:
        for table in tables:
            self.save_table(table)

    # ------------------------------------------------------------------
    # Saved table operations (user-saved game states)
    # ------------------------------------------------------------------

    def save_user_table(
        self,
        username: str,
        save_name: str,
        game_type: str,
        game_json: str,
        members_json: str,
    ) -> SavedTableRecord:
        saved_at = datetime.now().isoformat()
        save_id = self._execute_insert(
            "INSERT INTO saved_tables (username, save_name, game_type, game_json, members_json, saved_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (username, save_name, game_type, game_json, members_json, saved_at),
        )
        return SavedTableRecord(
            id=save_id,
            username=username,
            save_name=save_name,
            game_type=game_type,
            game_json=game_json,
            members_json=members_json,
            saved_at=saved_at,
        )

    def get_user_saved_tables(self, username: str) -> list[SavedTableRecord]:
        rows = self._execute(
            "SELECT * FROM saved_tables WHERE lower(username) = lower(%s) ORDER BY saved_at DESC",
            (username,),
        )
        records = []
        for row in rows:
            records.append(
                SavedTableRecord(
                    id=row["id"],
                    username=row["username"],
                    save_name=row["save_name"],
                    game_type=row["game_type"],
                    game_json=row["game_json"],
                    members_json=row["members_json"],
                    saved_at=row["saved_at"],
                )
            )
        return records

    def get_saved_table(self, save_id: int) -> SavedTableRecord | None:
        row = self._execute_one("SELECT * FROM saved_tables WHERE id = %s", (save_id,))
        if not row:
            return None
        return SavedTableRecord(
            id=row["id"],
            username=row["username"],
            save_name=row["save_name"],
            game_type=row["game_type"],
            game_json=row["game_json"],
            members_json=row["members_json"],
            saved_at=row["saved_at"],
        )

    def delete_saved_table(self, save_id: int) -> None:
        self._execute_commit("DELETE FROM saved_tables WHERE id = %s", (save_id,))

    # ------------------------------------------------------------------
    # Game result operations (statistics)
    # ------------------------------------------------------------------

    def save_game_result(
        self,
        game_type: str,
        timestamp: str,
        duration_ticks: int,
        players: list[tuple[str, str, bool, bool]],
        custom_data: dict | None = None,
    ) -> int:
        result_id = self._execute_insert(
            "INSERT INTO game_results (game_type, timestamp, duration_ticks, custom_data) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                game_type,
                timestamp,
                duration_ticks,
                json.dumps(custom_data) if custom_data else None,
            ),
        )

        for player_id, player_name, is_bot, is_virtual_bot in players:
            self._execute_commit(
                "INSERT INTO game_result_players (result_id, player_id, player_name, is_bot, is_virtual_bot) "
                "VALUES (%s, %s, %s, %s, %s)",
                (result_id, player_id, player_name, 1 if is_bot else 0, 1 if is_virtual_bot else 0),
            )

        return result_id

    def get_player_game_history(
        self,
        player_id: str,
        game_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        if game_type:
            rows = self._execute(
                "SELECT gr.id, gr.game_type, gr.timestamp, gr.duration_ticks, gr.custom_data "
                "FROM game_results gr "
                "INNER JOIN game_result_players grp ON gr.id = grp.result_id "
                "WHERE grp.player_id = %s AND gr.game_type = %s "
                "ORDER BY gr.timestamp DESC LIMIT %s",
                (player_id, game_type, limit),
            )
        else:
            rows = self._execute(
                "SELECT gr.id, gr.game_type, gr.timestamp, gr.duration_ticks, gr.custom_data "
                "FROM game_results gr "
                "INNER JOIN game_result_players grp ON gr.id = grp.result_id "
                "WHERE grp.player_id = %s "
                "ORDER BY gr.timestamp DESC LIMIT %s",
                (player_id, limit),
            )
        return [
            {
                "id": row["id"],
                "game_type": row["game_type"],
                "timestamp": row["timestamp"],
                "duration_ticks": row["duration_ticks"],
                "custom_data": json.loads(row["custom_data"]) if row["custom_data"] else {},
            }
            for row in rows
        ]

    def get_game_result_players(self, result_id: int) -> list[dict]:
        rows = self._execute(
            "SELECT player_id, player_name, is_bot, is_virtual_bot "
            "FROM game_result_players WHERE result_id = %s",
            (result_id,),
        )
        return [
            {
                "player_id": p["player_id"],
                "player_name": p["player_name"],
                "is_bot": bool(p["is_bot"]),
                "is_virtual_bot": bool(p["is_virtual_bot"]) if p["is_virtual_bot"] is not None else False,
            }
            for p in rows
        ]

    def get_game_stats(self, game_type: str, limit: int | None = None) -> list[tuple]:
        if limit:
            rows = self._execute(
                "SELECT id, game_type, timestamp, duration_ticks, custom_data "
                "FROM game_results WHERE game_type = %s "
                "ORDER BY timestamp DESC LIMIT %s",
                (game_type, limit),
            )
        else:
            rows = self._execute(
                "SELECT id, game_type, timestamp, duration_ticks, custom_data "
                "FROM game_results WHERE game_type = %s "
                "ORDER BY timestamp DESC",
                (game_type,),
            )
        return [
            (
                row["id"],
                row["game_type"],
                row["timestamp"],
                row["duration_ticks"],
                row["custom_data"],
            )
            for row in rows
        ]

    def get_game_stats_aggregate(self, game_type: str) -> dict:
        row = self._execute_one(
            "SELECT "
            "COUNT(*) AS total_games, "
            "COALESCE(SUM(duration_ticks), 0) AS total_duration, "
            "COALESCE(AVG(duration_ticks), 0) AS avg_duration "
            "FROM game_results WHERE game_type = %s",
            (game_type,),
        )
        return {
            "total_games": row["total_games"] or 0 if row else 0,
            "total_duration_ticks": row["total_duration"] or 0 if row else 0,
            "avg_duration_ticks": row["avg_duration"] or 0 if row else 0,
        }

    def get_player_stats(self, player_id: str, game_type: str | None = None) -> dict:
        if game_type:
            row = self._execute_one(
                "SELECT COUNT(*) AS games_played "
                "FROM game_result_players grp "
                "INNER JOIN game_results gr ON grp.result_id = gr.id "
                "WHERE grp.player_id = %s AND gr.game_type = %s",
                (player_id, game_type),
            )
        else:
            row = self._execute_one(
                "SELECT COUNT(*) AS games_played "
                "FROM game_result_players "
                "WHERE player_id = %s",
                (player_id,),
            )
        return {"games_played": row["games_played"] or 0 if row else 0}

    # ------------------------------------------------------------------
    # Player rating operations
    # ------------------------------------------------------------------

    def get_player_rating(self, player_id: str, game_type: str) -> tuple[float, float] | None:
        row = self._execute_one(
            "SELECT mu, sigma FROM player_ratings "
            "WHERE player_id = %s AND game_type = %s",
            (player_id, game_type),
        )
        if row:
            return (row["mu"], row["sigma"])
        return None

    def set_player_rating(self, player_id: str, game_type: str, mu: float, sigma: float) -> None:
        self._execute_commit(
            "INSERT INTO player_ratings (player_id, game_type, mu, sigma) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (player_id, game_type) DO UPDATE SET mu = EXCLUDED.mu, sigma = EXCLUDED.sigma",
            (player_id, game_type, mu, sigma),
        )

    def get_rating_leaderboard(
        self, game_type: str, limit: int = 10
    ) -> list[tuple[str, float, float]]:
        rows = self._execute(
            "SELECT player_id, mu, sigma FROM player_ratings "
            "WHERE game_type = %s ORDER BY mu DESC LIMIT %s",
            (game_type, limit),
        )
        return [(row["player_id"], row["mu"], row["sigma"]) for row in rows]

    # ------------------------------------------------------------------
    # Refresh token operations
    # ------------------------------------------------------------------

    def store_refresh_token(
        self, username: str, token: str, expires_at: int, created_at: int
    ) -> None:
        self._execute_commit(
            "INSERT INTO refresh_tokens (username, token, expires_at, created_at) "
            "VALUES (%s, %s, %s, %s)",
            (username, token, expires_at, created_at),
        )

    def get_refresh_token(self, token: str) -> RefreshTokenRecord | None:
        row = self._execute_one(
            "SELECT username, token, expires_at, created_at, revoked_at, replaced_by "
            "FROM refresh_tokens WHERE token = %s",
            (token,),
        )
        return _token_from_row(row) if row else None

    def revoke_refresh_token(
        self, token: str, revoked_at: int, replaced_by: str | None = None
    ) -> None:
        self._execute_commit(
            "UPDATE refresh_tokens SET revoked_at = %s, replaced_by = %s WHERE token = %s",
            (revoked_at, replaced_by, token),
        )

    def revoke_user_refresh_tokens(self, username: str, revoked_at: int) -> None:
        self._execute_commit(
            "UPDATE refresh_tokens SET revoked_at = %s "
            "WHERE lower(username) = lower(%s) AND revoked_at IS NULL",
            (revoked_at, username),
        )

    # ------------------------------------------------------------------
    # Virtual Bot Persistence
    # ------------------------------------------------------------------

    def save_virtual_bot(
        self,
        name: str,
        state: str,
        online_ticks: int,
        target_online_ticks: int,
        table_id: str | None,
        game_join_tick: int,
    ) -> None:
        self._execute_commit(
            "INSERT INTO virtual_bots (name, state, online_ticks, target_online_ticks, table_id, game_join_tick) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (name) DO UPDATE SET "
            "state = EXCLUDED.state, online_ticks = EXCLUDED.online_ticks, "
            "target_online_ticks = EXCLUDED.target_online_ticks, "
            "table_id = EXCLUDED.table_id, game_join_tick = EXCLUDED.game_join_tick",
            (name, state, online_ticks, target_online_ticks, table_id, game_join_tick),
        )

    def load_all_virtual_bots(self) -> list[dict]:
        rows = self._execute(
            "SELECT name, state, online_ticks, target_online_ticks, table_id, game_join_tick "
            "FROM virtual_bots"
        )
        return [
            {
                "name": row["name"],
                "state": row["state"],
                "online_ticks": row["online_ticks"],
                "target_online_ticks": row["target_online_ticks"],
                "table_id": row["table_id"],
                "game_join_tick": row["game_join_tick"],
            }
            for row in rows
        ]

    def delete_virtual_bot(self, name: str) -> None:
        self._execute_commit("DELETE FROM virtual_bots WHERE name = %s", (name,))

    def delete_all_virtual_bots(self) -> None:
        self._execute_commit("DELETE FROM virtual_bots")
