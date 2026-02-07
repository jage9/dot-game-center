"""Tic Tac Toe game logic and DotPad rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status

@dataclass
class TicTacToe:
    """Tic Tac Toe game with simple AI."""

    player_mark: str = "X"
    ai_mark: str = "O"

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the game state."""
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.sel_row = 0
        self.sel_col = 0
        self.turn = "player"
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names.
        """
        if self.winner:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % 3
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % 3
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % 3
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % 3
        if "f2" in names:
            self._place_player()

    def _place_player(self) -> None:
        if self.board[self.sel_row][self.sel_col] != "":
            return
        self.board[self.sel_row][self.sel_col] = self.player_mark
        self._update_winner()

    def run_ai_turn(self) -> bool:
        """Run one AI turn if game is still active."""
        if self.winner is not None:
            return False
        self._ai_move()
        return True

    def _ai_move(self) -> None:
        move = self._best_move()
        if move is None:
            return
        r, c = move
        self.board[r][c] = self.ai_mark
        self._update_winner()

    def _update_winner(self) -> None:
        winner = self._check_winner()
        if winner:
            self.winner = winner
        elif all(self.board[r][c] != "" for r in range(3) for c in range(3)):
            self.winner = "draw"

    def _check_winner(self) -> Optional[str]:
        lines = []
        lines.extend(self.board)
        lines.extend([[self.board[r][c] for r in range(3)] for c in range(3)])
        lines.append([self.board[i][i] for i in range(3)])
        lines.append([self.board[i][2 - i] for i in range(3)])
        for line in lines:
            if line[0] and all(cell == line[0] for cell in line):
                return line[0]
        return None

    def _best_move(self) -> Optional[tuple[int, int]]:
        best_score = -2
        best = None
        for r in range(3):
            for c in range(3):
                if self.board[r][c] == "":
                    self.board[r][c] = self.ai_mark
                    score = self._minimax(False)
                    self.board[r][c] = ""
                    if score > best_score:
                        best_score = score
                        best = (r, c)
        return best

    def _minimax(self, maximizing: bool) -> int:
        winner = self._check_winner()
        if winner == self.ai_mark:
            return 1
        if winner == self.player_mark:
            return -1
        if all(self.board[r][c] != "" for r in range(3) for c in range(3)):
            return 0

        if maximizing:
            best = -2
            for r in range(3):
                for c in range(3):
                    if self.board[r][c] == "":
                        self.board[r][c] = self.ai_mark
                        best = max(best, self._minimax(False))
                        self.board[r][c] = ""
            return best
        best = 2
        for r in range(3):
            for c in range(3):
                if self.board[r][c] == "":
                    self.board[r][c] = self.player_mark
                    best = min(best, self._minimax(True))
                    self.board[r][c] = ""
        return best

    def _draw_x(self, builder: dp.DotPadBuilder, row: int, col: int, size: int) -> None:
        """Draw a graphical X in a square region."""
        builder.draw_diag_line(row, col, size, "ltr")
        builder.draw_diag_line(row, col + size - 1, size, "rtl")

    def _draw_o(self, builder: dp.DotPadBuilder, row: int, col: int, size: int) -> None:
        """Draw a rounded O in a square region."""
        # Flat sides.
        builder.draw_line(row, col + 2, size - 4)
        builder.draw_line(row + size - 1, col + 2, size - 4)
        builder.draw_vline(row + 2, col, size - 4)
        builder.draw_vline(row + 2, col + size - 1, size - 4)
        # Rounded corners (2-dot diagonals each).
        builder.draw_diag_line(row + 1, col + 1, 2, "rtl")
        builder.draw_diag_line(row + 1, col + size - 2, 2, "ltr")
        builder.draw_diag_line(row + size - 2, col + 1, 2, "ltr")
        builder.draw_diag_line(row + size - 2, col + size - 2, 2, "rtl")

    def render(self, pad: dp.DotPad) -> None:
        """Render the current game state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        top = 1
        left = 1
        cell_w = 18
        cell_h = 12
        total_h = cell_h * 3 + 1

        # Grid lines
        for i in range(1, 3):
            col = left + i * cell_w
            builder.draw_vline(top, col, total_h)
        for i in range(1, 3):
            row = top + i * cell_h
            builder.draw_line(row, left, cell_w * 3)

        # Pieces (graphical X/O, not braille letters)
        for r in range(3):
            for c in range(3):
                mark = self.board[r][c]
                if not mark:
                    continue
                mark_row = top + r * cell_h + 2
                mark_col = left + c * cell_w + 5
                mark_size = 8
                if mark == "X":
                    self._draw_x(builder, mark_row, mark_col, mark_size)
                else:
                    self._draw_o(builder, mark_row, mark_col, mark_size)

        # Focus indicator (short line below selected cell) while game is active.
        if self.winner is None:
            focus_row = top + (self.sel_row + 1) * cell_h - 1
            focus_col = left + self.sel_col * cell_w + 6
            builder.draw_line(focus_row, focus_col, 6)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        if self.winner == "draw":
            send_status(pad, "DRAW F3 MENU")
        elif self.winner == self.player_mark:
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == self.ai_mark:
            send_status(pad, "YOU LOSE F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 MOVE F2 PLACE")
