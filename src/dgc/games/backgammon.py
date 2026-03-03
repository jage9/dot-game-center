"""Backgammon board display and DotPad rendering.

The board occupies the 60x40 dot display area:
  - 12 points per half, each 4 dots wide, with a 2-dot bar in the centre.
  - Top half (points 13-24): piece columns grow downward from row 2.
  - Bottom half (points 1-12): piece columns grow upward from row 38.
  - Up to 5 pieces per point are shown; overflow is indicated by a small
    numeral above/below the stack.

White pieces use dot pattern "1234"; black pieces use dot pattern "3456".
Controls: panLeft/panRight move the cursor between points; f1/f4 move between
top and bottom halves.  This implementation is display-only (no move rules).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import dotpad as dp
from .utils import send_status


# ---------------------------------------------------------------------------
# Initial position: list[int] indexed 1-24 where positive = white, negative = black
# White moves 24→1; black moves 1→24.
# ---------------------------------------------------------------------------
def _initial_counts() -> list[int]:
    """Return 25-element list (1-indexed) of signed piece counts."""
    counts = [0] * 25
    counts[1]  =  2   # white
    counts[12] =  5   # white
    counts[17] =  3   # white
    counts[19] =  5   # white
    counts[24] = -2   # black
    counts[13] = -5   # black
    counts[8]  = -3   # black
    counts[6]  = -5   # black
    return counts


# ---------------------------------------------------------------------------
# Layout constants (all in dot coordinates)
# ---------------------------------------------------------------------------
_BOARD_TOP  = 1    # top border row
_BOARD_BOT  = 38   # bottom border row
_BOARD_LEFT = 4    # left border col
_BOARD_RIGHT = 53  # right border col
_BAR_LEFT  = 28    # bar left col
_BAR_RIGHT = 29    # bar right col
_POINT_W   = 4     # dots wide per point
_PIECE_H   = 3     # dots tall per piece glyph
_TOP_PIECE_START = 2   # first row for top-half pieces
_BOT_PIECE_START = 38  # first row (bottom) for bottom-half pieces


def _point_col(point: int) -> int:
    """Return the left dot column of point 1-24."""
    # Bottom half: points 1-6 are on the right, 7-12 on the left.
    # Top half:    points 13-18 on the left, 19-24 on the right.
    if 1 <= point <= 6:
        # right of bar; point 1 rightmost
        idx = point - 1          # 0-5 (1→0, 6→5)
        return _BAR_RIGHT + 1 + (5 - idx) * _POINT_W
    if 7 <= point <= 12:
        # left of bar; point 12 leftmost
        idx = point - 7          # 0-5 (7→0, 12→5)
        return _BOARD_LEFT + (5 - idx) * _POINT_W
    if 13 <= point <= 18:
        # left of bar; point 13 leftmost
        idx = point - 13         # 0-5
        return _BOARD_LEFT + idx * _POINT_W
    # 19-24: right of bar; point 24 rightmost
    idx = point - 19             # 0-5
    return _BAR_RIGHT + 1 + idx * _POINT_W


@dataclass
class Backgammon:
    """Backgammon board with cursor navigation (display prototype).

    Controls:
      panLeft / panRight – move cursor among the 24 points
      f1 / f4            – jump between top and bottom halves
    """

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to the standard starting position."""
        # counts[i]: positive = white pieces, negative = black pieces (1-indexed)
        self.counts: list[int] = _initial_counts()
        self.cursor: int = 1          # currently selected point (1-24)
        self.winner: Optional[int] = None
        self._last_rows: list[bytes] | None = None

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Move cursor between board points.

        Args:
            names: List of key names from DotPad event.
        """
        if "panLeft" in names:
            self.cursor = max(1, self.cursor - 1)
        if "panRight" in names:
            self.cursor = min(24, self.cursor + 1)
        if "f1" in names:
            # Jump to the mirror point in the opposite half
            self.cursor = 25 - self.cursor
        if "f4" in names:
            self.cursor = 25 - self.cursor

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _draw_board_outline(self, builder: dp.DotPadBuilder) -> None:
        """Draw the outer board rectangle and centre bar."""
        builder.draw_rectangle(_BOARD_TOP, _BOARD_LEFT, _BOARD_BOT, _BOARD_RIGHT)
        builder.draw_vline(_BOARD_TOP, _BAR_LEFT,  _BOARD_BOT - _BOARD_TOP + 1)
        builder.draw_vline(_BOARD_TOP, _BAR_RIGHT, _BOARD_BOT - _BOARD_TOP + 1)

    def _draw_point_marker(self, builder: dp.DotPadBuilder, point: int) -> None:
        """Draw a small triangle/arrow indicating the point direction."""
        col = _point_col(point)
        if point > 12:
            # Top-half point: downward-pointing triangle
            builder.draw_line(_BOARD_TOP + 1, col, _POINT_W - 1)
            builder.draw_diag_line(_BOARD_TOP + 2, col, 2, "ltr")
            builder.draw_diag_line(_BOARD_TOP + 2, col + _POINT_W - 2, 2, "rtl")
        else:
            # Bottom-half point: upward-pointing triangle
            builder.draw_line(_BOARD_BOT - 1, col, _POINT_W - 1)
            builder.draw_diag_line(_BOARD_BOT - 3, col, 2, "ltr")
            builder.draw_diag_line(_BOARD_BOT - 3, col + _POINT_W - 2, 2, "rtl")

    def _draw_pieces(self, builder: dp.DotPadBuilder, point: int) -> None:
        """Draw stacked piece glyphs for the given point."""
        count = self.counts[point]
        if count == 0:
            return
        is_white = count > 0
        n = abs(count)
        col = _point_col(point) + 1  # 1-dot indent inside point width
        # Use dot pattern "1234" for white, "3456" for black (2x2 dot clusters)
        pattern = "1234" if is_white else "3456"
        show = min(n, 5)
        for i in range(show):
            if point > 12:
                # Top half: grow downward from _TOP_PIECE_START + 2 (below marker)
                row = _TOP_PIECE_START + 2 + i * _PIECE_H
            else:
                # Bottom half: grow upward from _BOT_PIECE_START - 2 (above marker)
                row = _BOT_PIECE_START - 2 - i * _PIECE_H
            builder.render_text_dots(pattern, row=row, col=col)
        # Show numeric overflow when more than 5 pieces
        if n > 5:
            if point > 12:
                label_row = _TOP_PIECE_START + 2 + 5 * _PIECE_H
            else:
                label_row = _BOT_PIECE_START - 2 - 5 * _PIECE_H
            builder.render_text(
                str(n), row=label_row, col=col,
                use_number_sign=False, use_nemeth=True,
            )

    def _draw_cursor(self, builder: dp.DotPadBuilder) -> None:
        """Draw a small underline/overline at the cursor point."""
        col = _point_col(self.cursor)
        if self.cursor > 12:
            builder.draw_line(_BOARD_TOP, col, _POINT_W - 1)
        else:
            builder.draw_line(_BOARD_BOT, col, _POINT_W - 1)

    # ------------------------------------------------------------------
    # Main render
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the backgammon board to the DotPad.

        The board layout within the 60x40 dot display:
          - Outer border: rows 1-38, cols 4-53
          - Centre bar:   cols 28-29
          - Top points (13-24): pieces grow downward from row 2
          - Bottom points (1-12): pieces grow upward from row 38

        Args:
            pad: Active DotPad instance.
        """
        builder = pad.builder()

        self._draw_board_outline(builder)

        for pt in range(1, 25):
            self._draw_point_marker(builder, pt)
            self._draw_pieces(builder, pt)

        self._draw_cursor(builder)

        # Point number labels along the bottom border gap
        for pt in range(1, 13):
            col = _point_col(pt)
            builder.render_text(
                str(pt), row=39, col=col,
                use_number_sign=False, use_nemeth=True,
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

        send_status(pad, f"PT {self.cursor} PAN/F1/F4 NAV")
