"""Table management for games."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from mashumaro.mixins.json import DataClassJSONMixin

from server.game_utils.game_status import GameStatus

# Table visibility values. A public table appears in the tables list; a private
# one does not, and can only be joined by members or holders of its password.
TABLE_VISIBILITY_PUBLIC = "public"
TABLE_VISIBILITY_PRIVATE = "private"

if TYPE_CHECKING:
    from server.games.base import Game
    from server.core.users.base import User
    from server.core.tables.manager import TableManager
    from server.core.server import Server
    from server.persistence.database import Database


@dataclass
class TableMember:
    """Member of a table (player or spectator).

    Attributes:
        username: Member username.
        is_spectator: True if spectating.
    """

    username: str
    is_spectator: bool = False


@dataclass
class Table(DataClassJSONMixin):
    """Game table holding members and a game instance.

    Tables track membership and forward events to the game. Role logic
    (player vs spectator) is handled by the game.
    """

    table_id: str
    game_type: str
    host: str
    members: list[TableMember] = field(default_factory=list)
    game_json: str | None = None  # Serialized game state
    status: str = GameStatus.WAITING
    # A "private" table is hidden from the tables list and can only be joined
    # by someone who already holds its password (or is already a member).
    visibility: str = TABLE_VISIBILITY_PUBLIC
    # Join password. Stored as given so it can be handed back to members who
    # have already proved they know it; never sent to a client that has not.
    password: str | None = None

    # Not serialized
    _game: "Game | None" = field(default=None, repr=False)
    _users: dict[str, "User"] = field(default_factory=dict, repr=False)
    _manager: "TableManager | None" = field(default=None, repr=False)
    _server: "Server | None" = field(default=None, repr=False)
    _db: "Database | None" = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize non-serialized runtime references."""
        self._game = None
        self._users = {}
        self._manager = None
        self._server = None
        self._db = None

    @property
    def game(self) -> "Game | None":
        """Return the current game instance."""
        return self._game

    @game.setter
    def game(self, value: "Game | None") -> None:
        """Set the game instance and update serialized state."""
        self._game = value
        if value:
            self.game_json = value.to_json()

    def add_member(self, username: str, user: "User", as_spectator: bool = False) -> None:
        """Add a member to the table.

        Args:
            username: Member username.
            user: User instance.
            as_spectator: True to join as spectator.
        """
        # Check if already a member
        for member in self.members:
            if member.username == username:
                return

        self.members.append(TableMember(username=username, is_spectator=as_spectator))
        self._users[username] = user

    def remove_member(self, username: str) -> None:
        """Remove a member from the table."""
        self.members = [m for m in self.members if m.username != username]
        self._users.pop(username, None)

        # Destroy table if it's empty
        if not self.members:
            self.destroy()

    def get_user(self, username: str) -> "User | None":
        """Get a user by username."""
        return self._users.get(username)

    def attach_user(self, username: str, user: "User") -> None:
        """Attach a user to a member (e.g., after deserialization)."""
        self._users[username] = user

    def get_players(self) -> list[TableMember]:
        """Get all non-spectator members."""
        return [m for m in self.members if not m.is_spectator]

    def get_spectators(self) -> list[TableMember]:
        """Get all spectator members."""
        return [m for m in self.members if m.is_spectator]

    @property
    def player_count(self) -> int:
        """Get the number of players (non-spectators)."""
        return len(self.get_players())

    def broadcast(self, text: str, buffer: str = "misc") -> None:
        """Send a message to all members."""
        for username, user in self._users.items():
            user.speak(text, buffer)

    def broadcast_sound(self, name: str, volume: int = 100) -> None:
        """Play a sound for all members."""
        for user in self._users.values():
            user.play_sound(name, volume)

    def on_tick(self) -> None:
        """Called every tick. Forwards to game when it still has work to do."""
        game = self._game
        if game is not None and self._game_needs_tick(game):
            game.on_tick()

    @staticmethod
    def _game_needs_tick(game) -> bool:
        """
        Whether a game is still worth ticking.

        A finished game keeps sitting at its table until everyone leaves, and
        the tick loop runs twenty times a second, so ticking one forever is
        pure waste. This deliberately only skips games that have *finished*:
        games that are merely waiting for a human move are still ticked, because
        55 of the games override on_tick with turn timers and bot logic.

        Queued sounds are still allowed to drain, so an end-of-game jingle is
        never cut off by the tick being skipped.
        """
        if getattr(game, "status", None) != "finished":
            return True
        if getattr(game, "scheduled_sounds", None):
            return True
        if getattr(game, "_estimate_running", False):
            return True
        return False

    def handle_event(self, username: str, event: dict) -> None:
        """Handle an event from a member."""
        if self._game:
            # Find the player
            for player in self._game.players:
                if player.name == username:
                    self._game.handle_event(player, event)
                    break

    def save_game_state(self) -> None:
        """Save the current game state to game_json."""
        if self._game:
            self.game_json = self._game.to_json()

    def can_start(self, min_players: int) -> bool:
        """Check if the game can start."""
        return self.player_count >= min_players

    @property
    def is_private(self) -> bool:
        """Whether this table is hidden from the tables list."""
        return self.visibility == TABLE_VISIBILITY_PRIVATE

    @property
    def has_password(self) -> bool:
        """Whether joining this table requires a password."""
        return bool(self.password)

    def is_member(self, username: str) -> bool:
        """Whether *username* is already seated at this table."""
        return any(member.username == username for member in self.members)

    def is_visible_to(self, username: str) -> bool:
        """
        Whether this table should be listed for *username*.

        Public tables are listed for everyone. A private or password-protected
        table is listed only for the host and people already seated at it,
        so the list never reveals tables others cannot join.
        """
        if not self.is_private and not self.has_password:
            return True
        return self.host == username or self.is_member(username)

    def can_join(self, username: str, password: str | None = None) -> tuple[bool, str]:
        """
        Check whether *username* may join, and why not.

        Returns ``(allowed, reason)`` where *reason* is one of ``""``,
        ``"private"`` or ``"password"``. The host and existing members are
        always allowed, so a table never locks out the people already in it.
        """
        if self.host == username or self.is_member(username):
            return True, ""
        if self.is_private:
            return False, "private"
        if self.has_password:
            if password is None or not self.password_matches(password):
                return False, "password"
        return True, ""

    def password_matches(self, candidate: str) -> bool:
        """Whether *candidate* is this table's password."""
        import hmac

        if not self.password:
            return False
        return hmac.compare_digest(self.password, candidate)

    def destroy(self) -> None:
        """Destroy this table. Called by Game.destroy()."""
        if self._manager:
            self._manager.on_table_destroy(self)

    def save_and_close(self, username: str) -> None:
        """Save game state and close table. Called by game save action."""
        if self._server:
            self._server.on_table_save(self, username)

    def save_game_result(self, result: Any) -> None:
        """Save a game result to the database. Called by game when it finishes."""
        if self._server:
            self._server.on_game_result(result)
