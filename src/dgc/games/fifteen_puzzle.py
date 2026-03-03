"""15-Puzzle sliding puzzle game for Dot Game Center."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid, cell_top_left, send_diff

# Solved state: 1-15 with 0 (empty) at bottom-right
SOLVED = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 0]]

# Grid layout on 60×40 dot display
_TOP = 3
_LEFT = 5
_CELL_H = 9
_CELL_W = 13


@dataclass
class FifteenPuzzle:
    """Sliding 15-puzzle with solvable shuffle and undo."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset and shuffle the board."""
        self.board: list[list[int]] = [row[:] for row in SOLVED]
        self.sel_row: int = 0
        self.sel_col: int = 0
        self.winner: Optional[str] = None
        self._undo_stack: list[tuple[list[list[int]], int, int, int, int]] = []
        self._last_rows: Optional[list[bytes]] = None
        self._shuffle()
        # Position cursor on empty tile initially
        er, ec = self._find_empty()
        self.sel_row, self.sel_col = er, ec

    # ------------------------------------------------------------------
    # Puzzle logic
    # ------------------------------------------------------------------

    def _find_empty(self) -> tuple[int, int]:
        for r in range(4):
            for c in range(4):
                if self.board[r][c] == 0:
                    return r, c
        return 3, 3

    def _is_solvable(self) -> bool:
        flat = [self.board[r][c] for r in range(4) for c in range(4) if self.board[r][c] != 0]
        inversions = sum(
            1
            for i in range(len(flat))
            for j in range(i + 1, len(flat))
            if flat[i] > flat[j]
        )
        er, _ = self._find_empty()
        # For 4×4: solvable when (inversions + empty_row_from_bottom) is even
        empty_row_from_bottom = 4 - er
        return (inversions + empty_row_from_bottom) % 2 == 0

    def _shuffle(self) -> None:
        tiles = list(range(16))
        while True:
            random.shuffle(tiles)
            self.board = [tiles[r * 4 : r * 4 + 4] for r in range(4)]
            if self._is_solvable() and self.board != SOLVED:
                break

    def _can_move_to_empty(self, tr: int, tc: int) -> bool:
        """Return True if tile at (tr,tc) is adjacent to the empty cell."""
        er, ec = self._find_empty()
        return (abs(tr - er) + abs(tc - ec)) == 1

    def _slide_tile(self, tr: int, tc: int) -> bool:
        """Slide the tile at (tr,tc) into the empty space. Return True on success."""
        if not self._can_move_to_empty(tr, tc):
            return False
        er, ec = self._find_empty()
        # Save undo state
        snap = [row[:] for row in self.board]
        self._undo_stack.append((snap, self.sel_row, self.sel_col, er, ec))
        self.board[er][ec] = self.board[tr][tc]
        self.board[tr][tc] = 0
        # Move cursor to where the empty is now (previous tile position)
        self.sel_row, self.sel_col = er, ec
        return True

    def _check_win(self) -> None:
        if self.board == SOLVED:
            self.winner = "win"

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Navigation moves the cursor. F2 slides the tile under the cursor
        toward the empty space (if adjacent). F3 undoes the last move.

        Args:
            names: List of key names received from DotPad/keyboard.
        """
        if self.winner:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % 4
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % 4
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % 4
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % 4
        if "f2" in names:
            moved = self._slide_tile(self.sel_row, self.sel_col)
            if moved:
                self._check_win()
        if "f3" in names:
            self._undo()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        snap, sr, sc, er, ec = self._undo_stack.pop()
        self.board = snap
        self.sel_row, self.sel_col = sr, sc
        self.winner = None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the puzzle board to the DotPad.

        Args:
            pad: Active DotPad device instance.
        """
        builder = pad.builder()
        draw_grid(builder, _TOP, _LEFT, 4, 4, _CELL_H, _CELL_W)

        er, ec = self._find_empty()

        for r in range(4):
            for c in range(4):
                tile = self.board[r][c]
                if tile == 0:
                    continue
                crow, ccol = cell_top_left(_TOP, _LEFT, r, c, _CELL_H, _CELL_W)
                # Center the number text within the cell (2 dots from top, 3 from left)
                text = str(tile)
                builder.render_text(text, row=crow + 2, col=ccol + 2, use_number_sign=False)

        # Cursor: highlight the selected cell with a short underline if not empty
        if self.winner is None:
            if not (self.sel_row == er and self.sel_col == ec):
                cr, cc = cell_top_left(_TOP, _LEFT, self.sel_row, self.sel_col, _CELL_H, _CELL_W)
                # Draw a 3-dot indicator line near bottom of selected cell
                builder.draw_line(cr + _CELL_H - 2, cc + 3, 5)
            # Highlight empty cell with a small rectangle
            er_top, ec_left = cell_top_left(_TOP, _LEFT, er, ec, _CELL_H, _CELL_W)
            builder.draw_line(er_top + 3, ec_left + 4, 3)

        self._last_rows = send_diff(pad, builder, self._last_rows)

        if self.winner == "win":
            send_status(pad, "YOU WIN F3 MENU")
        else:
            move_count = len(self._undo_stack)
            send_status(pad, f"MOVES:{move_count} F2 SLIDE F3 UNDO"[:20])
