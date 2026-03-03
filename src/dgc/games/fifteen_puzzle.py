"""15-Puzzle game (display-first prototype).

The 15-puzzle is a sliding tile puzzle on a 4 × 4 grid containing tiles
numbered 1–15 and one blank space.  The player slides a tile adjacent to
the blank into the blank position until the tiles are in ascending order
(left-to-right, top-to-bottom) with the blank in the bottom-right corner.

Board is rendered on the 60 × 40 DotPad dot display.
Grid:  top=2, left=2, cell_w=13, cell_h=8  →  occupies cols 2–54, rows 2–34.
Tile numbers are rendered as braille digits centred in each cell.
A short focus underline marks the currently selected tile.

Assumptions
-----------
* ``dp.DotPadBuilder.render_text`` places a braille string at dot (row, col)
  with each character 3 dots wide × 4 dots tall.
* ``use_number_sign=False, use_nemeth=True`` renders digits in lowered
  Nemeth style without a leading number indicator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers.render_helpers import draw_grid, flush_rows

# Board side length.
_SIDE = 4

# Grid layout constants (dot coordinates).
_TOP = 2
_LEFT = 2
_CELL_W = 13
_CELL_H = 8


@dataclass
class FifteenPuzzle:
    """Sliding 15-puzzle with DotPad rendering.

    Attributes:
        sel_row: Currently selected tile row (0-based).
        sel_col: Currently selected tile column (0-based).
        winner:  ``"player"`` when solved, otherwise ``None``.
    """

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to the solved initial configuration."""
        # Tiles stored flat; index = row * 4 + col.  0 represents the blank.
        self._tiles: list[int] = list(range(1, _SIDE * _SIDE)) + [0]
        self._blank_r: int = _SIDE - 1
        self._blank_c: int = _SIDE - 1
        self.sel_row: int = 0
        self.sel_col: int = 0
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    @property
    def board(self) -> list[list[int]]:
        """Return the current tile layout as a 2-D list."""
        return [self._tiles[r * _SIDE:(r + 1) * _SIDE] for r in range(_SIDE)]

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key name strings from the DotPad driver.
        """
        if self.winner is not None:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % _SIDE
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % _SIDE
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % _SIDE
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % _SIDE
        if "f2" in names:
            self._slide(self.sel_row, self.sel_col)

    # ------------------------------------------------------------------
    # Internal logic
    # ------------------------------------------------------------------

    def _slide(self, r: int, c: int) -> None:
        """Slide the tile at (r, c) into the blank if they are adjacent."""
        br, bc = self._blank_r, self._blank_c
        if abs(r - br) + abs(c - bc) != 1:
            return  # Not adjacent — ignore.
        idx = r * _SIDE + c
        blank_idx = br * _SIDE + bc
        self._tiles[blank_idx], self._tiles[idx] = self._tiles[idx], self._tiles[blank_idx]
        self._blank_r, self._blank_c = r, c
        # Check for win: tiles 1–15 in order, blank at last position.
        if self._tiles == list(range(1, _SIDE * _SIDE)) + [0]:
            self.winner = "player"

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the current puzzle state to the DotPad.

        Draws the 4×4 grid, places tile numbers in each cell, and marks the
        selected cell with a short underline.  Sends only changed lines for
        efficient incremental updates.

        Args:
            pad: Connected ``dp.DotPad`` device instance, or ``None`` (no-op).
        """
        if pad is None:
            return

        builder = pad.builder()

        # Draw the 4×4 grid border and interior lines.
        draw_grid(builder, _TOP, _LEFT, _CELL_W, _CELL_H, _SIDE, _SIDE)

        # Render tile numbers centred in each cell.
        board = self.board
        for r in range(_SIDE):
            for c in range(_SIDE):
                val = board[r][c]
                if val == 0:
                    continue  # Blank cell — leave empty.
                # Two-digit values: render tens digit then units digit.
                piece_row = _TOP + r * _CELL_H + 3
                if val < 10:
                    # Single digit — centre in cell.
                    piece_col = _LEFT + c * _CELL_W + 5
                    builder.render_text(
                        str(val),
                        row=piece_row,
                        col=piece_col,
                        use_number_sign=False,
                        use_nemeth=True,
                    )
                else:
                    # Two digits side-by-side.
                    piece_col = _LEFT + c * _CELL_W + 3
                    builder.render_text(
                        str(val // 10),
                        row=piece_row,
                        col=piece_col,
                        use_number_sign=False,
                        use_nemeth=True,
                    )
                    builder.render_text(
                        str(val % 10),
                        row=piece_row,
                        col=piece_col + 4,
                        use_number_sign=False,
                        use_nemeth=True,
                    )

        # Focus underline on the selected cell (only while game is active).
        if self.winner is None:
            focus_row = _TOP + (self.sel_row + 1) * _CELL_H - 1
            focus_col = _LEFT + self.sel_col * _CELL_W + 4
            builder.draw_line(focus_row, focus_col, 5)

        self._last_rows = flush_rows(pad, builder, self._last_rows)

        if self.winner:
            send_status(pad, "YOU WIN F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 MV F2 SLIDE")
