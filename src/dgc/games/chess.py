"""Chess display-first prototype.

Renders the initial chess board layout on the DotPad tactile display.
The player can navigate the cursor around the 8 × 8 board to inspect pieces.
No move validation or AI is implemented in this prototype; the focus is on
a correct tactile initial display with standard piece notation.

Board layout on the 60 × 40 dot display
-----------------------------------------
Grid:  top=1, left=1, cell_w=7, cell_h=4  →  occupies cols 1–57, rows 1–33.
Pieces are shown as braille letters centred in each cell:
  Uppercase = white  (K Q R B N P)
  Lowercase = black  (k q r b n p)
A short underline marks the currently selected cell.
Dark squares (where (row + col) % 2 == 1) are marked with a corner dot for
tactile orientation.

Piece key:
  K/k = King    Q/q = Queen   R/r = Rook
  B/b = Bishop  N/n = Knight  P/p = Pawn

Assumptions
-----------
* ``dp.DotPadBuilder.render_text`` places a 3-dot-wide braille character at
  the given dot coordinates.  Centering in a 7-dot wide cell uses +2 offset.
* Row 0 = rank 8 (black's back rank), row 7 = rank 1 (white's back rank).
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

# Standard initial piece layout, row 0 = rank 8 (black), row 7 = rank 1 (white).
_BACK_RANK = ["r", "n", "b", "q", "k", "b", "n", "r"]

_EMPTY = ""


def _initial_board() -> list[list[str]]:
    """Return the standard 8×8 chess starting position.

    Uppercase letters are white pieces; lowercase are black.
    """
    board: list[list[str]] = [[_EMPTY] * _SIZE for _ in range(_SIZE)]
    # Black back rank (row 0) and pawns (row 1).
    for c, piece in enumerate(_BACK_RANK):
        board[0][c] = piece       # Black — lowercase.
        board[1][c] = "p"         # Black pawn.
    # White pawns (row 6) and back rank (row 7).
    for c, piece in enumerate(_BACK_RANK):
        board[6][c] = "P"         # White pawn.
        board[7][c] = piece.upper()  # White — uppercase.
    return board


@dataclass
class Chess:
    """Chess board display prototype with DotPad rendering.

    Attributes:
        board:    8×8 grid of piece strings ('' for empty squares).
        sel_row:  Currently selected row (0-based, 0 = black's back rank).
        sel_col:  Currently selected column (0-based, 0 = a-file).
        winner:   Always ``None`` in this prototype.
    """

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to the standard chess starting position."""
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
        """Render the chess board to the DotPad.

        Draws the 8×8 grid, places piece letters on occupied squares, adds a
        small corner dot on dark squares for tactile board orientation, and
        marks the selected cell with an underline.

        Args:
            pad: Connected ``dp.DotPad`` device instance, or ``None`` (no-op).
        """
        if pad is None:
            return

        builder = pad.builder()

        # Draw the 8×8 grid.
        draw_grid(builder, _TOP, _LEFT, _CELL_W, _CELL_H, _SIZE, _SIZE)

        # Draw pieces and dark-square markers.
        for r in range(_SIZE):
            for c in range(_SIZE):
                cell_top = _TOP + r * _CELL_H
                cell_left = _LEFT + c * _CELL_W

                # Dark squares get a small tactile corner marker.
                if (r + c) % 2 == 1:
                    builder.draw_line(cell_top + 1, cell_left + 1, 1)

                piece = self.board[r][c]
                if piece:
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

        # Status: file/rank label + piece name.
        file_label = chr(ord("a") + self.sel_col)
        rank_label = str(8 - self.sel_row)
        square = f"{file_label}{rank_label}"
        piece = self.board[self.sel_row][self.sel_col]
        cell_desc = piece if piece else "empty"
        send_status(pad, f"{square} {cell_desc} PAN/F1/F4")
