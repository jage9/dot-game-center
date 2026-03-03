"""Checkers (Draughts) display-first prototype.

Renders the initial checkers board layout on the DotPad tactile display.
The player can move the cursor around the 8 × 8 board and select pieces.
No move validation or AI is implemented in this prototype; the focus is
on a correct tactile initial display.

Board layout on the 60 × 40 dot display
-----------------------------------------
Grid:  top=1, left=1, cell_w=7, cell_h=4  →  occupies cols 1–57, rows 1–33.
Pieces are shown as braille letters centred in each dark-square cell:
  'b' = black checker  'B' = black king
  'w' = white checker  'W' = white king
A short underline marks the currently selected cell.

The dark squares are those where (row + col) % 2 == 1 (0-based indices).
Black pieces occupy rows 0–2 on dark squares; white pieces occupy rows 5–7.

Assumptions
-----------
* ``dp.DotPadBuilder.render_text`` places a 3-dot-wide braille character at
  the given dot coordinates, so centering in a 7-dot wide cell uses an offset
  of +2 dots from the cell's left column.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers.render_helpers import draw_grid, flush_rows

# Grid layout constants (dot coordinates).
_TOP = 1
_LEFT = 1
_CELL_W = 7
_CELL_H = 4
_SIZE = 8  # Board side length.

# Piece constants.
_EMPTY = ""
_BLACK = "b"
_WHITE = "w"


def _initial_board() -> list[list[str]]:
    """Return the standard 8×8 checkers starting position."""
    board: list[list[str]] = [[_EMPTY] * _SIZE for _ in range(_SIZE)]
    for r in range(_SIZE):
        for c in range(_SIZE):
            if (r + c) % 2 == 1:  # Dark square only.
                if r < 3:
                    board[r][c] = _BLACK
                elif r > 4:
                    board[r][c] = _WHITE
    return board


@dataclass
class Checkers:
    """Checkers board display prototype with DotPad rendering.

    Attributes:
        board:    8×8 grid of piece strings.
        sel_row:  Currently selected row (0-based).
        sel_col:  Currently selected column (0-based).
        winner:   Always ``None`` in this prototype.
    """

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to the standard checkers starting position."""
        self.board: list[list[str]] = _initial_board()
        self.sel_row: int = 0
        self.sel_col: int = 0
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key name strings from the DotPad driver.
        """
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % _SIZE
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % _SIZE
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % _SIZE
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % _SIZE

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the checkers board to the DotPad.

        Draws the 8×8 grid, places piece letters on occupied squares, fills
        dark squares lightly to convey the checkerboard pattern, and marks
        the selected cell with an underline.

        Args:
            pad: Connected ``dp.DotPad`` device instance, or ``None`` (no-op).
        """
        if pad is None:
            return

        builder = pad.builder()

        # Draw the 8×8 grid.
        draw_grid(builder, _TOP, _LEFT, _CELL_W, _CELL_H, _SIZE, _SIZE)

        # Draw pieces and dark-square fill dots.
        for r in range(_SIZE):
            for c in range(_SIZE):
                cell_top = _TOP + r * _CELL_H
                cell_left = _LEFT + c * _CELL_W

                # Mark dark squares with a small corner dot (tactile texture).
                if (r + c) % 2 == 1:
                    builder.draw_line(cell_top + 1, cell_left + 1, 1)

                piece = self.board[r][c]
                if piece:
                    # Centre the braille letter in the cell.
                    piece_row = cell_top + 1
                    piece_col = cell_left + 2
                    builder.render_text(
                        piece,
                        row=piece_row,
                        col=piece_col,
                        use_number_sign=False,
                    )

        # Selection underline.
        focus_row = _TOP + (self.sel_row + 1) * _CELL_H - 1
        focus_col = _LEFT + self.sel_col * _CELL_W + 2
        builder.draw_line(focus_row, focus_col, 4)

        self._last_rows = flush_rows(pad, builder, self._last_rows)

        sq = f"{chr(ord('A') + self.sel_row)}{self.sel_col + 1}"
        piece = self.board[self.sel_row][self.sel_col]
        cell_desc = piece if piece else "empty"
        send_status(pad, f"{sq} {cell_desc} PAN/F1/F4")
