"""
Tic-Tac-Toe Game Implementation for PlayPalace.

Grid-based 3x3 game. Players alternate placing X and O; first to line up
three in a row, column, or diagonal wins. Bots play a perfect minimax.
"""

from dataclasses import dataclass, field
from datetime import datetime
import random

from ..base import Game, Player, GameOptions
from ..registry import register_game
from ...game_utils.action_guard_mixin import ActionGuardMixin
from ...game_utils.actions import Action, ActionSet
from ...game_utils.bot_helper import BotHelper
from ...game_utils.game_result import GameResult, PlayerResult
from ...game_utils.grid_mixin import GridGameMixin, GridCursor, grid_cell_id
from ...messages.localization import Localization

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),  # diagonals
]


@dataclass
class TicTacToePlayer(Player):
    """Player state for Tic-Tac-Toe (marker derived from turn order)."""


@dataclass
class TicTacToeOptions(GameOptions):
    """Options for Tic-Tac-Toe."""


@dataclass
@register_game
class TicTacToeGame(GridGameMixin, ActionGuardMixin, Game):
    """Tic-Tac-Toe grid game."""

    players: list[TicTacToePlayer] = field(default_factory=list)
    options: TicTacToeOptions = field(default_factory=TicTacToeOptions)
    board: list[str] = field(default_factory=lambda: [""] * 9)
    # Grid mixin serialized state
    grid_rows: int = 3
    grid_cols: int = 3
    grid_cursors: dict[str, GridCursor] = field(default_factory=dict)
    grid_row_labels: list[str] = field(default_factory=lambda: ["1", "2", "3"])
    grid_col_labels: list[str] = field(default_factory=lambda: ["A", "B", "C"])

    @classmethod
    def get_name(cls) -> str:
        return "Tic-Tac-Toe"

    @classmethod
    def get_type(cls) -> str:
        return "tictactoe"

    @classmethod
    def get_category(cls) -> str:
        return "category-board-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 2

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> TicTacToePlayer:
        """Create a new player."""
        return TicTacToePlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game."""
        from ...game_utils.game_status import GameStatus

        self.status = GameStatus.PLAYING
        self.game_active = True
        self.board = [""] * 9
        self.set_turn_players(self.get_active_players())
        self._init_grid()
        self.play_sound("game_squares/start.ogg")
        self._announce_turn()
        self.rebuild_all_menus()

    def on_tick(self) -> None:
        """Run per-tick logic including bot AI."""
        super().on_tick()
        BotHelper.on_tick(self)

    # ==========================================================================
    # Grid callbacks
    # ==========================================================================

    def get_cell_label(self, row: int, col: int, player: Player, locale: str) -> str:
        """Describe a grid cell for speech output."""
        coord = self._grid_cell_coordinate(row, col)
        mark = self.board[row * self.grid_cols + col]
        if mark:
            return Localization.get(locale, "tictactoe-cell-filled", coord=coord, mark=mark)
        return Localization.get(locale, "tictactoe-cell-empty", coord=coord)

    def is_grid_cell_enabled(self, player: Player, row: int, col: int) -> str | None:
        """Only the current player may place in an empty cell."""
        if self.status != "playing":
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if self.current_player != player:
            return "action-not-your-turn"
        if self.board[row * self.grid_cols + col]:
            return "tictactoe-cell-taken"
        return None

    def on_grid_select(self, player: Player, row: int, col: int) -> None:
        """Place a mark and advance the game."""
        if self.status != "playing" or player.is_spectator:
            return
        if self.current_player != player:
            return

        index = row * self.grid_cols + col
        if self.board[index]:
            user = self.get_user(player)
            if user:
                user.speak_l("tictactoe-cell-taken")
            return

        marker = self._marker_for_player(player)
        self.board[index] = marker
        coord = self._grid_cell_coordinate(row, col)
        self.play_sound(random.choice(["game_chess/movepawn1.ogg", "game_chess/movepawn2.ogg"]))  # nosec B311
        self.broadcast_l("tictactoe-move", player=player.name, coord=coord, mark=marker)
        self.update_player_menu(player, selection_id=grid_cell_id(row, col))

        winner = self._winner_of(self.board)
        if winner:
            self.play_sound("game_pig/win.ogg")
            self.broadcast_l("tictactoe-winner", player=player.name, mark=winner)
            self.finish_game()
            return
        if all(self.board):
            self.broadcast_l("tictactoe-draw")
            self.finish_game()
            return

        self.turn_index = (self.turn_index + 1) % len(self.turn_player_ids)
        self._announce_turn()
        self.rebuild_all_menus()

    # ==========================================================================
    # Turn action set and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: TicTacToePlayer) -> ActionSet:
        """Create the turn action set with grid cells and navigation."""
        action_set = ActionSet(name="turn")
        for action in self.build_grid_actions(player):
            action_set.add(action)
        for action in self.build_grid_nav_actions():
            action_set.add(action)
        return action_set

    def setup_keybinds(self) -> None:
        """Define keybinds for the game."""
        super().setup_keybinds()
        self.setup_grid_keybinds()

    # ==========================================================================
    # Game logic helpers
    # ==========================================================================

    def _marker_for_player(self, player: Player) -> str:
        """Return the marker for a player based on turn order."""
        if self.turn_player_ids and player.id == self.turn_player_ids[0]:
            return "X"
        return "O"

    @staticmethod
    def _winner_of(board: list[str]) -> str | None:
        """Return the winning marker, or None."""
        for a, b, c in WIN_LINES:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a]
        return None

    def _announce_turn(self) -> None:
        """Announce the current player's turn with their marker."""
        player = self.current_player
        if not player:
            return
        marker = self._marker_for_player(player)
        self.broadcast_personal_l(
            player,
            "tictactoe-your-turn",
            "tictactoe-turn-start",
            mark=marker,
        )

    # ==========================================================================
    # Bot AI (perfect minimax)
    # ==========================================================================

    @staticmethod
    def _minimax(board: list[str], marker: str, depth: int) -> int:
        """Minimax score for the given board state (X maximizes)."""
        winner = TicTacToeGame._winner_of(board)
        if winner == "X":
            return 10 - depth
        if winner == "O":
            return depth - 10
        if all(board):
            return 0

        best = -1000 if marker == "X" else 1000
        for i, cell in enumerate(board):
            if not cell:
                board[i] = marker
                score = TicTacToeGame._minimax(board, "O" if marker == "X" else "X", depth + 1)
                board[i] = ""
                if marker == "X":
                    best = max(best, score)
                else:
                    best = min(best, score)
        return best

    def bot_think(self, player: TicTacToePlayer) -> str | None:
        """Choose the best legal move via minimax (random among equals)."""
        my_marker = self._marker_for_player(player)
        moves = [i for i, v in enumerate(self.board) if not v]
        if not moves:
            return None

        best_score = -1000 if my_marker == "X" else 1000
        best_moves: list[int] = []
        for i in moves:
            self.board[i] = my_marker
            score = self._minimax(self.board, "O" if my_marker == "X" else "X", 1)
            self.board[i] = ""
            if my_marker == "X":
                if score > best_score:
                    best_score, best_moves = score, [i]
                elif score == best_score:
                    best_moves.append(i)
            else:
                if score < best_score:
                    best_score, best_moves = score, [i]
                elif score == best_score:
                    best_moves.append(i)

        row, col = divmod(random.choice(best_moves), 3)  # nosec B311
        return grid_cell_id(row, col)

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        winner_name = None
        winner_mark = self._winner_of(self.board)
        if winner_mark:
            for player in self.get_active_players():
                if self._marker_for_player(player) == winner_mark:
                    winner_name = player.name
                    break

        return GameResult(
            game_type=self.get_type(),
            timestamp=datetime.now().isoformat(),
            duration_ticks=self.sound_scheduler_tick,
            player_results=[
                PlayerResult(
                    player_id=p.id,
                    player_name=p.name,
                    is_bot=p.is_bot,
                    is_virtual_bot=getattr(p, "is_virtual_bot", False),
                )
                for p in self.get_active_players()
            ],
            custom_data={
                "winner_name": winner_name,
                "board": list(self.board),
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        board = result.custom_data.get("board", [])
        for row in range(3):
            cells = board[row * 3:(row + 1) * 3]
            lines.append(" ".join(cell or "-" for cell in cells))
        return lines


__all__ = ["TicTacToeGame", "TicTacToePlayer", "TicTacToeOptions"]