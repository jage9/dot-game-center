"""Connect 4 game logic and DotPad rendering."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import dotpad as dp
from .utils import send_status


@dataclass
class Connect4:
    """Connect 4 game with alpha-beta minimax AI."""

    cols: int = 7
    rows: int = 6

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the game state."""
        self.board = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.sel_col = 3
        self.winner: Optional[int] = None
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names.
        """
        if self.winner:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % self.cols
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % self.cols
        if "f2" in names:
            if self._drop(self.sel_col, 1):
                self._check_winner()
                if not self.winner:
                    self._ai_move()

    def _drop(self, col: int, player: int) -> bool:
        for r in reversed(range(self.rows)):
            if self.board[r][col] == 0:
                self.board[r][col] = player
                return True
        return False

    def _check_winner(self) -> None:
        win = self._find_winner()
        if win:
            self.winner = win
        elif all(self.board[0][c] != 0 for c in range(self.cols)):
            self.winner = -1

    def _find_winner(self) -> Optional[int]:
        for r in range(self.rows):
            for c in range(self.cols):
                player = self.board[r][c]
                if player == 0:
                    continue
                if self._check_dir(r, c, 1, 0, player):
                    return player
                if self._check_dir(r, c, 0, 1, player):
                    return player
                if self._check_dir(r, c, 1, 1, player):
                    return player
                if self._check_dir(r, c, 1, -1, player):
                    return player
        return None

    def _check_dir(self, r: int, c: int, dr: int, dc: int, player: int) -> bool:
        for i in range(4):
            rr = r + dr * i
            cc = c + dc * i
            if rr < 0 or rr >= self.rows or cc < 0 or cc >= self.cols:
                return False
            if self.board[rr][cc] != player:
                return False
        return True

    def _ai_move(self) -> None:
        valid = self._valid_moves()
        if not valid:
            self.winner = -1
            return

        # Deeper search late-game when branching is smaller.
        empties = sum(1 for r in range(self.rows) for c in range(self.cols) if self.board[r][c] == 0)
        depth = 6 if empties <= 20 else 5

        best_col = valid[0]
        best_score = -math.inf
        alpha = -math.inf
        beta = math.inf
        for col in valid:
            self._drop(col, 2)
            score = self._minimax(depth - 1, maximizing=False, alpha=alpha, beta=beta)
            self._undo_drop(col)
            if score > best_score:
                best_score = score
                best_col = col
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break

        self._drop(best_col, 2)
        self._check_winner()

    def _can_drop(self, col: int) -> bool:
        return self.board[0][col] == 0

    def _undo_drop(self, col: int) -> None:
        for r in range(self.rows):
            if self.board[r][col] != 0:
                self.board[r][col] = 0
                return

    def _valid_moves(self) -> list[int]:
        """Return drop columns ordered from center out."""
        center = self.cols // 2
        order = [center]
        for i in range(1, self.cols):
            if center - i >= 0:
                order.append(center - i)
            if center + i < self.cols:
                order.append(center + i)
        return [c for c in order if self._can_drop(c)]

    def _minimax(self, depth: int, maximizing: bool, alpha: float, beta: float) -> float:
        winner = self._find_winner()
        if winner == 2:
            return 1_000_000 + depth
        if winner == 1:
            return -1_000_000 - depth
        if all(self.board[0][c] != 0 for c in range(self.cols)):
            return 0
        if depth <= 0:
            return self._evaluate_position()

        valid = self._valid_moves()
        if maximizing:
            value = -math.inf
            for col in valid:
                self._drop(col, 2)
                value = max(value, self._minimax(depth - 1, False, alpha, beta))
                self._undo_drop(col)
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = math.inf
        for col in valid:
            self._drop(col, 1)
            value = min(value, self._minimax(depth - 1, True, alpha, beta))
            self._undo_drop(col)
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def _evaluate_position(self) -> int:
        """Heuristic evaluation from AI perspective (player 2)."""
        score = 0

        # Center control is typically strongest in Connect 4.
        center_col = self.cols // 2
        center_count = sum(1 for r in range(self.rows) if self.board[r][center_col] == 2)
        score += center_count * 6

        # Horizontal windows
        for r in range(self.rows):
            for c in range(self.cols - 3):
                score += self._score_window([self.board[r][c + i] for i in range(4)])
        # Vertical windows
        for c in range(self.cols):
            for r in range(self.rows - 3):
                score += self._score_window([self.board[r + i][c] for i in range(4)])
        # Diagonal down-right windows
        for r in range(self.rows - 3):
            for c in range(self.cols - 3):
                score += self._score_window([self.board[r + i][c + i] for i in range(4)])
        # Diagonal up-right windows
        for r in range(3, self.rows):
            for c in range(self.cols - 3):
                score += self._score_window([self.board[r - i][c + i] for i in range(4)])

        return score

    @staticmethod
    def _score_window(window: list[int]) -> int:
        ai = window.count(2)
        human = window.count(1)
        empty = window.count(0)

        if ai == 4:
            return 100_000
        if ai == 3 and empty == 1:
            return 120
        if ai == 2 and empty == 2:
            return 15
        if human == 4:
            return -100_000
        if human == 3 and empty == 1:
            return -140
        if human == 2 and empty == 2:
            return -10
        return 0

    def _draw_square(self, builder: dp.DotPadBuilder, row: int, col: int) -> None:
        """Draw a 5x5 square token."""
        builder.draw_rectangle(row, col, row + 4, col + 4)

    def _draw_circle(self, builder: dp.DotPadBuilder, row: int, col: int) -> None:
        """Draw a rounded 5x5 circle-like token using diagonals."""
        builder.draw_diag_line(row, col + 2, 3, "rtl")
        builder.draw_diag_line(row, col + 2, 3, "ltr")
        builder.draw_diag_line(row + 2, col, 3, "ltr")
        builder.draw_diag_line(row + 2, col + 4, 3, "rtl")

    def render(self, pad: dp.DotPad) -> None:
        """Render the current game state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        top = 1
        left = 1
        cell_w = 8
        cell_h = 6

        # Draw pieces
        for r in range(self.rows):
            for c in range(self.cols):
                val = self.board[r][c]
                if val == 0:
                    continue
                base_row = top + r * cell_h + 1
                base_col = left + c * cell_w + 2
                if val == 1:
                    self._draw_square(builder, base_row, base_col)
                else:
                    self._draw_circle(builder, base_row, base_col)

        # Caret indicator at bottom.
        cursor_row = top + self.rows * cell_h + 2
        cursor_col = left + self.sel_col * cell_w + 2
        builder.draw_line(cursor_row, cursor_col, 5)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        if self.winner == -1:
            send_status(pad, "DRAW F3 MENU")
        elif self.winner == 1:
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == 2:
            send_status(pad, "YOU LOSE F3 MENU")
        else:
            send_status(pad, "PAN MOVE F2 DROP")
