"""15-Puzzle (sliding tile) game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status


@dataclass
class Puzzle15:
    """15-puzzle sliding tile game (single-player, no AI)."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset and shuffle the board into a solvable state."""
        self.sel_row = 0
        self.sel_col = 0
        self.winner: Optional[str] = None
        self.moves: int = 0
        self._last_rows: list[bytes] | None = None
        self.board = self._make_solvable_board()

    # ------------------------------------------------------------------
    # Board setup
    # ------------------------------------------------------------------

    def _make_solvable_board(self) -> list[list[int]]:
        """Return a randomly shuffled, solvable 4×4 board."""
        tiles = list(range(16))  # 0 = blank, 1-15 = tiles
        while True:
            random.shuffle(tiles)
            if self._is_solvable(tiles):
                return [tiles[i * 4:(i + 1) * 4] for i in range(4)]

    @staticmethod
    def _is_solvable(tiles: list[int]) -> bool:
        """Return True if the flat tile list represents a solvable 15-puzzle.

        For a 4×4 grid the position is solvable when:
        (number of inversions) + (row of blank counted from bottom, 1-indexed) is even.
        """
        inversions = 0
        flat = [t for t in tiles if t != 0]
        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                if flat[i] > flat[j]:
                    inversions += 1
        blank_index = tiles.index(0)
        blank_row_from_bottom = 4 - (blank_index // 4)  # 1-indexed from bottom
        return (inversions + blank_row_from_bottom) % 2 == 0

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names.
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
            self._slide_tile()

    def _slide_tile(self) -> None:
        """Slide the selected tile into the adjacent blank, if possible."""
        r, c = self.sel_row, self.sel_col
        blank = self._blank_pos()
        if blank is None:
            return
        br, bc = blank
        # Only slide if blank is directly adjacent (no diagonals).
        if abs(br - r) + abs(bc - c) != 1:
            return
        # Swap tile and blank.
        self.board[br][bc] = self.board[r][c]
        self.board[r][c] = 0
        self.moves += 1
        if self._is_solved():
            self.winner = "player"

    def _blank_pos(self) -> Optional[tuple[int, int]]:
        for r in range(4):
            for c in range(4):
                if self.board[r][c] == 0:
                    return r, c
        return None

    def _is_solved(self) -> bool:
        for r in range(4):
            for c in range(4):
                expected = r * 4 + c + 1
                if r == 3 and c == 3:
                    expected = 0
                if self.board[r][c] != expected:
                    return False
        return True

    # ------------------------------------------------------------------
    # AI stub (no CPU opponent)
    # ------------------------------------------------------------------

    def run_ai_turn(self) -> bool:
        """No-op: 15-puzzle has no AI opponent."""
        return False

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    # Layout constants (dot coordinates, 1-indexed)
    _TOP = 3
    _LEFT = 2
    _CELL_W = 14
    _CELL_H = 9

    def render(self, pad: dp.DotPad) -> None:
        """Render the current game state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()
        top = self._TOP
        left = self._LEFT
        cw = self._CELL_W
        ch = self._CELL_H

        # Outer border.
        total_w = cw * 4 + 1
        total_h = ch * 4 + 1
        builder.draw_rectangle(top, left, top + total_h - 1, left + total_w - 1)

        # Inner vertical dividers (3 lines).
        for i in range(1, 4):
            col = left + i * cw
            builder.draw_vline(top, col, total_h)

        # Inner horizontal dividers (3 lines).
        for i in range(1, 4):
            row = top + i * ch
            builder.draw_line(row, left, total_w)

        # Tile numbers as Nemeth braille.
        for r in range(4):
            for c in range(4):
                val = self.board[r][c]
                if val == 0:
                    continue
                # Center text in cell; two-digit numbers shifted one dot left.
                text_row = top + r * ch + 2
                if val >= 10:
                    text_col = left + c * cw + 5
                else:
                    text_col = left + c * cw + 7
                builder.render_text(str(val), text_row, text_col,
                                    use_number_sign=False, use_nemeth=True)

        # Focus indicator: short underline below selected cell while active.
        if self.winner is None:
            focus_row = top + (self.sel_row + 1) * ch - 2
            focus_col = left + self.sel_col * cw + 4
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

        if self.winner == "player":
            send_status(pad, "SOLVED F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 MOVE F2 SLIDE")
