"""Fifteen puzzle (sliding tile puzzle) game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status


@dataclass
class FifteenPuzzle:
    """4×4 sliding-tile puzzle (1–15 tiles plus one blank)."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to a freshly shuffled solvable puzzle."""
        # tiles[r][c] holds 1-15 or 0 for the blank
        self.tiles: list[list[int]] = [
            [r * 4 + c + 1 for c in range(4)] for r in range(4)
        ]
        self.tiles[3][3] = 0
        self._shuffle()
        self.cursor_row: int = 0
        self.cursor_col: int = 0
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _blank_pos(self) -> tuple[int, int]:
        for r in range(4):
            for c in range(4):
                if self.tiles[r][c] == 0:
                    return r, c
        raise RuntimeError("No blank tile found")

    def _shuffle(self) -> None:
        """Shuffle by making 200 valid adjacent swaps (guarantees solvability)."""
        br, bc = 3, 3
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        prev: Optional[tuple[int, int]] = None
        for _ in range(200):
            random.shuffle(dirs)
            for dr, dc in dirs:
                nr, nc = br + dr, bc + dc
                # Avoid immediately reversing the last move
                if prev and (dr, dc) == (-prev[0], -prev[1]):
                    continue
                if 0 <= nr < 4 and 0 <= nc < 4:
                    self.tiles[br][bc], self.tiles[nr][nc] = (
                        self.tiles[nr][nc],
                        self.tiles[br][bc],
                    )
                    prev = (dr, dc)
                    br, bc = nr, nc
                    break

    def _check_win(self) -> None:
        expected = list(range(1, 16)) + [0]
        actual = [self.tiles[r][c] for r in range(4) for c in range(4)]
        if actual == expected:
            self.winner = "win"

    # ------------------------------------------------------------------
    # Game API
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names pressed.
        """
        if self.winner:
            return
        if "panLeft" in names:
            self.cursor_col = (self.cursor_col - 1) % 4
        if "panRight" in names:
            self.cursor_col = (self.cursor_col + 1) % 4
        if "f1" in names:
            self.cursor_row = (self.cursor_row - 1) % 4
        if "f4" in names:
            self.cursor_row = (self.cursor_row + 1) % 4
        if "f2" in names:
            self._slide_toward_blank()

    def _slide_toward_blank(self) -> None:
        """Slide the tile at the cursor one step toward the blank if adjacent."""
        br, bc = self._blank_pos()
        cr, cc = self.cursor_row, self.cursor_col
        if cr == br and abs(cc - bc) == 1:
            self.tiles[br][bc], self.tiles[cr][cc] = self.tiles[cr][cc], 0
            self._check_win()
        elif cc == bc and abs(cr - br) == 1:
            self.tiles[br][bc], self.tiles[cr][cc] = self.tiles[cr][cc], 0
            self._check_win()

    def run_ai_turn(self) -> bool:
        """No AI for this puzzle; always returns False."""
        return False

    def render(self, pad: dp.DotPad) -> None:
        """Render the current puzzle state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        top = 2
        left = 3
        cell_h = 9
        cell_w = 13

        # Grid lines (borders + internal separators)
        total_w = 4 * cell_w + 1
        total_h = 4 * cell_h + 1
        for i in range(5):
            builder.draw_line(top + i * cell_h, left, total_w)
        for j in range(5):
            builder.draw_vline(top, left + j * cell_w, total_h)

        # Tile numbers as braille text centered in each cell
        for r in range(4):
            for c in range(4):
                val = self.tiles[r][c]
                if val == 0:
                    continue
                text_row = top + r * cell_h + 3
                text_col = left + c * cell_w + 4
                builder.render_text(str(val), text_row, text_col, use_number_sign=False)

        # Cursor: small corner mark at top-left of selected cell
        if self.winner is None:
            ct = top + self.cursor_row * cell_h + 1
            cl = left + self.cursor_col * cell_w + 1
            builder.draw_line(ct, cl, 3)
            builder.draw_vline(ct, cl, 3)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        if self.winner == "win":
            send_status(pad, "YOU WIN F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 F2 SLIDE")
