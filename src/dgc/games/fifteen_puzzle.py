"""15-Puzzle (sliding tile) game logic and DotPad rendering.

The 4x4 grid occupies the full 60x40 dot display area:
  - 4 columns x 14 dots wide  = 56 dots (plus border at col 57)
  - 4 rows    x  9 dots tall  = 36 dots (plus border at row 37)
Tile numbers are rendered as Nemeth braille digits centred in each cell.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid


@dataclass
class FifteenPuzzle:
    """Sliding 15-puzzle game.

    Controls (DotPad keys):
      panLeft / panRight / f1 / f4 – slide the tile adjacent to the blank
      into the blank square.
    """

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to a solvable, randomly shuffled starting position."""
        tiles = list(range(1, 16)) + [0]
        # Shuffle until a solvable configuration is found.
        while True:
            random.shuffle(tiles)
            if self._is_solvable(tiles):
                break
        self.board: list[list[int]] = [
            tiles[i * 4 : (i + 1) * 4] for i in range(4)
        ]
        for r in range(4):
            for c in range(4):
                if self.board[r][c] == 0:
                    self.blank_row: int = r
                    self.blank_col: int = c
        self.winner: Optional[bool] = None
        self._last_rows: list[bytes] | None = None

    # ------------------------------------------------------------------
    # Solvability check
    # ------------------------------------------------------------------

    @staticmethod
    def _is_solvable(tiles: list[int]) -> bool:
        """Return True if the flat tile list represents a solvable puzzle.

        For a 4x4 grid the puzzle is solvable when:
          (inversions + blank_row_from_bottom) is even.
        """
        flat = [t for t in tiles if t != 0]
        inversions = sum(
            1
            for i in range(len(flat))
            for j in range(i + 1, len(flat))
            if flat[i] > flat[j]
        )
        blank_row_from_bottom = 3 - tiles.index(0) // 4
        return (inversions + blank_row_from_bottom) % 2 == 0

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Slide the tile adjacent to the blank in the pressed direction.

        Args:
            names: List of key names from the DotPad event.
        """
        if self.winner is not None:
            return
        br, bc = self.blank_row, self.blank_col
        moved = False
        # panLeft means user wants to slide the tile to the right of blank leftward.
        if "panLeft" in names and bc < 3:
            self.board[br][bc] = self.board[br][bc + 1]
            self.board[br][bc + 1] = 0
            self.blank_col = bc + 1
            moved = True
        elif "panRight" in names and bc > 0:
            self.board[br][bc] = self.board[br][bc - 1]
            self.board[br][bc - 1] = 0
            self.blank_col = bc - 1
            moved = True
        elif "f1" in names and br < 3:
            self.board[br][bc] = self.board[br + 1][bc]
            self.board[br + 1][bc] = 0
            self.blank_row = br + 1
            moved = True
        elif "f4" in names and br > 0:
            self.board[br][bc] = self.board[br - 1][bc]
            self.board[br - 1][bc] = 0
            self.blank_row = br - 1
            moved = True
        if moved:
            self._check_winner()

    def _check_winner(self) -> None:
        """Set winner=True when tiles are in solved order 1–15, blank last."""
        flat = [self.board[r][c] for r in range(4) for c in range(4)]
        if flat == list(range(1, 16)) + [0]:
            self.winner = True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the puzzle board to the DotPad.

        The 4x4 grid uses cell_w=14, cell_h=9 fitting within the 60x40
        dot display area.  Tile numbers are drawn as Nemeth braille digits.

        Args:
            pad: Active DotPad instance.
        """
        builder = pad.builder()

        top = 1
        left = 1
        cell_w = 14  # 4 cols * 14 = 56 dots wide + border at 57
        cell_h = 9   # 4 rows *  9 = 36 dots tall + border at 37

        # Grid lines
        draw_grid(builder, top, left, 4, 4, cell_h, cell_w)

        # Tile numbers
        for r in range(4):
            for c in range(4):
                tile = self.board[r][c]
                if tile == 0:
                    continue  # blank cell – leave empty
                text = str(tile)
                # Horizontally centre the number inside the cell.
                # Single digit (3 dot-cols) → offset 6; two digits (6 dot-cols) → offset 4
                text_col = left + c * cell_w + (6 if len(text) == 1 else 4)
                text_row = top + r * cell_h + 4  # vertically centred
                builder.render_text(
                    text,
                    row=text_row,
                    col=text_col,
                    use_number_sign=False,
                    use_nemeth=True,
                )

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        if self.winner:
            send_status(pad, "SOLVED F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 SLIDE TILE")
