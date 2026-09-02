"""
Reversi (Othello) Game Implementation for PlayPalace.

8x8 grid game. Black moves first; a legal move outflanks and flips one or
more lines of opponent discs. A player with no legal moves passes. The game
ends when neither player can move; the player with the most discs wins.
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
from ...game_utils.game_status import GameStatus
from ...game_utils.grid_mixin import GridGameMixin, GridCursor, grid_cell_id
from ...messages.localization import Localization

SIZE = 8
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _idx(row: int, col: int) -> int:
    return row * SIZE + col


@dataclass
class ReversiPlayer(Player):
    """Player state for Reversi (marker derived from turn order)."""


@dataclass
class ReversiOptions(GameOptions):
    """Options for Reversi."""


@dataclass
@register_game
class ReversiGame(GridGameMixin, ActionGuardMixin, Game):
    """Reversi (Othello) grid game."""

    players: list[ReversiPlayer] = field(default_factory=list)
    options: ReversiOptions = field(default_factory=ReversiOptions)
    board: list[str] = field(default_factory=lambda: [""] * (SIZE * SIZE))
    # Grid mixin serialized state
    grid_rows: int = SIZE
    grid_cols: int = SIZE
    grid_cursors: dict[str, GridCursor] = field(default_factory=dict)
    grid_row_labels: list[str] = field(default_factory=lambda: [str(i + 1) for i in range(SIZE)])
    grid_col_labels: list[str] = field(default_factory=lambda: [chr(ord("A") + i) for i in range(SIZE)])

    @classmethod
    def get_name(cls) -> str:
        return "Reversi"

    @classmethod
    def get_type(cls) -> str:
        return "reversi"

    @classmethod
    def get_category(cls) -> str:
        return "category-board-games"

    @classmethod
    def get_min_players(cls) -> int:
        return 2

    @classmethod
    def get_max_players(cls) -> int:
        return 2

    def create_player(self, player_id: str, name: str, is_bot: bool = False) -> ReversiPlayer:
        """Create a new player."""
        return ReversiPlayer(id=player_id, name=name, is_bot=is_bot)

    def on_start(self) -> None:
        """Start the game with the classic center setup."""
        self.status = GameStatus.PLAYING
        self.game_active = True
        self.board = [""] * (SIZE * SIZE)
        self.board[_idx(3, 3)] = "W"
        self.board[_idx(3, 4)] = "B"
        self.board[_idx(4, 3)] = "B"
        self.board[_idx(4, 4)] = "W"
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
    # Board logic
    # ==========================================================================

    def _marker_for_player(self, player: Player) -> str:
        """Black moves first (player order 0 = B, 1 = W)."""
        if self.turn_player_ids and player.id == self.turn_player_ids[0]:
            return "B"
        return "W"

    def _opponent(self, marker: str) -> str:
        return "W" if marker == "B" else "B"

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < SIZE and 0 <= col < SIZE

    def _legal_moves(self, marker: str) -> set[int]:
        """All flat indices where the marker can legally play."""
        opponent = self._opponent(marker)
        legal: set[int] = set()
        for r in range(SIZE):
            for c in range(SIZE):
                if self.board[_idx(r, c)]:
                    continue
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if not self._in_bounds(nr, nc) or self.board[_idx(nr, nc)] != opponent:
                        continue
                    while self._in_bounds(nr, nc) and self.board[_idx(nr, nc)] == opponent:
                        nr += dr
                        nc += dc
                    if self._in_bounds(nr, nc) and self.board[_idx(nr, nc)] == marker:
                        legal.add(_idx(r, c))
                        break
        return legal

    def _apply_move(self, index: int, marker: str) -> int:
        """Place a disc and flip outflanked lines. Returns flips."""
        row, col = divmod(index, SIZE)
        opponent = self._opponent(marker)
        flipped = 0
        for dr, dc in DIRECTIONS:
            line: list[tuple[int, int]] = []
            nr, nc = row + dr, col + dc
            while self._in_bounds(nr, nc) and self.board[_idx(nr, nc)] == opponent:
                line.append((nr, nc))
                nr += dr
                nc += dc
            if line and self._in_bounds(nr, nc) and self.board[_idx(nr, nc)] == marker:
                for lr, lc in line:
                    self.board[_idx(lr, lc)] = marker
                    flipped += 1
        self.board[index] = marker
        return flipped

    def _count_discs(self, marker: str) -> int:
        return sum(1 for cell in self.board if cell == marker)

    # ==========================================================================
    # Grid callbacks
    # ==========================================================================

    def get_cell_label(self, row: int, col: int, player: Player, locale: str) -> str:
        """Describe a grid cell for speech output."""
        coord = self._grid_cell_coordinate(row, col)
        mark = self.board[_idx(row, col)]
        if mark:
            return Localization.get(locale, "reversi-cell-filled", coord=coord, mark=mark)
        if self.status == "playing" and self.current_player == player:
            if _idx(row, col) in self._legal_moves(self._marker_for_player(player)):
                return Localization.get(locale, "reversi-cell-playable", coord=coord)
        return Localization.get(locale, "reversi-cell-empty", coord=coord)

    def is_grid_cell_enabled(self, player: Player, row: int, col: int) -> str | None:
        """Cells are playable only by the current player on legal empty cells."""
        if self.status != "playing":
            return "action-not-playing"
        if player.is_spectator:
            return "action-spectator"
        if self.current_player != player:
            return "action-not-your-turn"
        index = _idx(row, col)
        if self.board[index]:
            return "reversi-cell-taken"
        if index not in self._legal_moves(self._marker_for_player(player)):
            return "reversi-not-legal"
        return None

    def on_grid_select(self, player: Player, row: int, col: int) -> None:
        """Place a disc and advance the game."""
        if self.status != "playing" or player.is_spectator:
            return
        if self.current_player != player:
            return

        index = _idx(row, col)
        marker = self._marker_for_player(player)
        if self.board[index] or index not in self._legal_moves(marker):
            user = self.get_user(player)
            if user:
                user.speak_l("reversi-not-legal")
            return

        flips = self._apply_move(index, marker)
        coord = self._grid_cell_coordinate(row, col)
        self.play_sound("game_chess/movepawn1.ogg")
        self.broadcast_l("reversi-move", player=player.name, coord=coord, mark=marker)
        if flips:
            self.schedule_sound("game_chess/capture1.ogg", delay_ticks=4)
            self.broadcast_l("reversi-flips", player=player.name, count=flips)
        self.update_player_menu(player, selection_id=grid_cell_id(row, col))

        # Check game end: no legal moves for either player
        other_marker = self._opponent(marker)
        if not self._legal_moves(other_marker) and not self._legal_moves(marker):
            self._finish_game()
            return

        self.turn_index = (self.turn_index + 1) % len(self.turn_player_ids)
        # Skip players with no legal moves
        while self.turn_index != 0 and not self._legal_moves(self._marker_for_player(self.current_player or player)):
            skipped = self.current_player
            if skipped:
                self.broadcast_l("reversi-pass", player=skipped.name)
            self.turn_index = (self.turn_index + 1) % len(self.turn_player_ids)
        self.play_sound("game_chess/pickup.ogg")
        self._announce_turn()
        self.rebuild_all_menus()

    def _finish_game(self) -> None:
        """Count discs and finish."""
        black = self._count_discs("B")
        white = self._count_discs("W")
        self.play_sound("game_pig/win.ogg")
        if black > white:
            winner = self.get_player_by_id(self.turn_player_ids[0])
            self.broadcast_l("reversi-winner", player=winner.name if winner else "?", score=black)
        elif white > black:
            winner = self.get_player_by_id(self.turn_player_ids[1])
            self.broadcast_l("reversi-winner", player=winner.name if winner else "?", score=white)
        else:
            self.broadcast_l("reversi-tie", score=black)
        self.finish_game()

    # ==========================================================================
    # Turn action set and keybinds
    # ==========================================================================

    def create_turn_action_set(self, player: ReversiPlayer) -> ActionSet:
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

    def _announce_turn(self) -> None:
        """Announce the current player's turn with their marker."""
        player = self.current_player
        if not player:
            return
        marker = self._marker_for_player(player)
        self.broadcast_personal_l(
            player,
            "reversi-your-turn",
            "reversi-turn-start",
            mark=marker,
        )

    # ==========================================================================
    # Bot AI
    # ==========================================================================

    def _bot_evaluate_move(self, move: int, marker: str) -> float:
        """Heuristic value of a move: corners > edges > flips, minus opponent mobility."""
        board = list(self.board)
        self.board[move] = marker
        flips = self._apply_move(move, marker)
        value = float(flips)

        row, col = divmod(move, SIZE)
        if (row in (0, SIZE - 1)) and (col in (0, SIZE - 1)):
            value += 25
        elif row in (0, SIZE - 1) or col in (0, SIZE - 1):
            value += 5

        opp_mobility = len(self._legal_moves(self._opponent(marker)))
        value -= opp_mobility * 1.5

        self.board = board
        return value

    def bot_think(self, player: ReversiPlayer) -> str | None:
        """Bot AI: pick the best greedy move."""
        marker = self._marker_for_player(player)
        moves = sorted(self._legal_moves(marker))
        if not moves:
            return None
        best = max(moves, key=lambda m: self._bot_evaluate_move(m, marker))
        return grid_cell_id(best // SIZE, best % SIZE)

    # ==========================================================================
    # Results
    # ==========================================================================

    def build_game_result(self) -> GameResult:
        """Build the game result."""
        black = self._count_discs("B")
        white = self._count_discs("W")
        winner_name = None
        if black > white and self.turn_player_ids:
            winner = self.get_player_by_id(self.turn_player_ids[0])
            winner_name = winner.name if winner else None
        elif white > black and len(self.turn_player_ids) > 1:
            winner = self.get_player_by_id(self.turn_player_ids[1])
            winner_name = winner.name if winner else None

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
                "black": black,
                "white": white,
                "board": list(self.board),
            },
        )

    def format_end_screen(self, result: GameResult, locale: str) -> list[str]:
        """Format the end screen."""
        lines = [Localization.get(locale, "game-over")]
        lines.append(Localization.get(locale, "reversi-final", black=result.custom_data.get("black", 0), white=result.custom_data.get("white", 0)))
        return lines


__all__ = ["ReversiGame", "ReversiPlayer", "ReversiOptions"]