"""Connect 4 game logic and DotPad rendering."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional

import dotpad as dp
from .utils import send_status


@dataclass
class Connect4:
    """Connect 4 game with a basic AI."""

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
        # win if possible
        for c in range(self.cols):
            if self._can_drop(c):
                self._drop(c, 2)
                if self._find_winner() == 2:
                    self._check_winner()
                    return
                self._undo_drop(c)
        # block player
        for c in range(self.cols):
            if self._can_drop(c):
                self._drop(c, 1)
                if self._find_winner() == 1:
                    self._undo_drop(c)
                    self._drop(c, 2)
                    self._check_winner()
                    return
                self._undo_drop(c)
        # prefer center
        center = self.cols // 2
        if self._can_drop(center):
            self._drop(center, 2)
            self._check_winner()
            return
        # random valid
        valid = [c for c in range(self.cols) if self._can_drop(c)]
        if valid:
            self._drop(random.choice(valid), 2)
            self._check_winner()
        else:
            self.winner = -1

    def _can_drop(self, col: int) -> bool:
        return self.board[0][col] == 0

    def _undo_drop(self, col: int) -> None:
        for r in range(self.rows):
            if self.board[r][col] != 0:
                self.board[r][col] = 0
                return

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
