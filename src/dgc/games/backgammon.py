"""Backgammon display-first prototype.

This module renders the initial backgammon board layout on the DotPad tactile
display.  Gameplay is navigation-only: the player can move the cursor between
the 24 points using the DotPad keys.  No move validation or AI is implemented
in this prototype.

Board layout on the 60 × 40 dot display
----------------------------------------
The board is divided into four quadrants of 6 points each, separated by a
centre bar.  Points are shown as vertical columns of stacked dots representing
the checkers on each point.

  Top half (points 13–24, pieces point downward from row 3):
      Left quad:  points 13–18  cols  2,  6, 10, 14, 18, 22
      Bar:                       cols 26–29
      Right quad: points 19–24  cols 30, 34, 38, 42, 46, 50

  Bottom half (points 1–12, pieces point upward toward row 36):
      Left quad:  points 12–7   cols  2,  6, 10, 14, 18, 22
      Bar:                       cols 26–29
      Right quad: points  6–1   cols 30, 34, 38, 42, 46, 50

Each checker is represented by a 2-dot-wide × 1-dot-tall filled segment.
Point numbers are shown as braille digits near the outer edge.

Assumptions
-----------
* Standard backgammon starting position is used.
* ``dp.DotPadBuilder.render_text`` places braille at the given dot coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers.render_helpers import flush_rows

# --- Layout constants (dot coordinates) ---
_TOP = 3          # Top dot row for pieces pointing downward.
_BOT = 36         # Bottom dot row for pieces pointing upward.
_POINT_W = 4      # Width of one point column in dots.
_BAR_LEFT = 26    # First dot column of the centre bar.
_BAR_W = 4        # Width of the bar in dots.
_RIGHT_START = _BAR_LEFT + _BAR_W  # First dot col of the right quadrants.

# Maximum stack height shown per point (dots).
_MAX_STACK = 10

# Standard backgammon starting position.
# Indexed by point number 1–24.  Positive = white checkers, negative = black.
# White home board: points 1–6.  Black home board: points 19–24.
_START_POSITION: dict[int, int] = {
    1: 2,    # 2 white
    6: -5,   # 5 black
    8: -3,   # 3 black
    12: 5,   # 5 white
    13: -5,  # 5 black
    17: 3,   # 3 white
    19: 5,   # 5 white
    24: -2,  # 2 black
}


def _point_col(point: int) -> int:
    """Return the leftmost dot column for the given point (1–24)."""
    # Points 1–6: right quadrant bottom half (reversed order).
    # Points 7–12: left quadrant bottom half (reversed order).
    # Points 13–18: left quadrant top half.
    # Points 19–24: right quadrant top half.
    if 1 <= point <= 6:
        # Bottom-right: point 1 is at the rightmost column, point 6 at left of right quad.
        offset = 5 - (point - 1)
        return _RIGHT_START + offset * _POINT_W
    if 7 <= point <= 12:
        # Bottom-left: point 12 at leftmost col, point 7 near bar.
        offset = point - 7
        return 2 + offset * _POINT_W
    if 13 <= point <= 18:
        # Top-left: point 13 at leftmost col.
        offset = point - 13
        return 2 + offset * _POINT_W
    # 19–24: Top-right: point 19 nearest bar.
    offset = point - 19
    return _RIGHT_START + offset * _POINT_W


@dataclass
class Backgammon:
    """Backgammon board display prototype with DotPad rendering.

    Attributes:
        points:  List of 25 elements (index 1–24 used); positive values are
                 white checkers, negative are black.
        sel_point: Currently selected point number (1–24).
        winner:  Always ``None`` in this prototype.
    """

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset to the standard backgammon starting position."""
        self.points: list[int] = [0] * 25  # 1-indexed; index 0 unused.
        for pt, count in _START_POSITION.items():
            self.points[pt] = count
        self.sel_point: int = 1
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    @property
    def board(self) -> list[list[str]]:
        """Return a 2-row summary grid for the on-screen game grid widget."""
        top_row = [str(abs(self.points[p])) if self.points[p] != 0 else "." for p in range(13, 25)]
        bot_row = [str(abs(self.points[p])) if self.points[p] != 0 else "." for p in range(1, 13)]
        return [top_row, bot_row]

    @property
    def sel_row(self) -> int:
        """Row index for the selected point (0 = top half, 1 = bottom half)."""
        return 0 if self.sel_point >= 13 else 1

    @property
    def sel_col(self) -> int:
        """Column index (0–11) for the selected point within its half."""
        if self.sel_point >= 13:
            return self.sel_point - 13
        return 12 - self.sel_point  # Points 12→0, 1→11

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key name strings from the DotPad driver.
        """
        if "panLeft" in names:
            self.sel_point = max(1, self.sel_point - 1)
        if "panRight" in names:
            self.sel_point = min(24, self.sel_point + 1)
        if "f1" in names:
            # Mirror the selected point to the opposite half of the board.
            self.sel_point = 25 - self.sel_point
        if "f4" in names:
            self.sel_point = 25 - self.sel_point

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the backgammon board to the DotPad.

        Draws the border, bar, point labels, and stacked checker columns.
        The selected point is highlighted with a short underline (bottom half)
        or overline (top half).

        Args:
            pad: Connected ``dp.DotPad`` device instance, or ``None`` (no-op).
        """
        if pad is None:
            return

        builder = pad.builder()

        # Outer board border.
        board_right = _RIGHT_START + 6 * _POINT_W  # rightmost column + 1
        builder.draw_rectangle(1, 1, 39, board_right)

        # Centre bar (vertical line).
        builder.draw_vline(1, _BAR_LEFT, 39)
        builder.draw_vline(1, _BAR_LEFT + _BAR_W - 1, 39)

        # Mid-board horizontal divider.
        mid_row = 20
        builder.draw_line(mid_row, 1, board_right)

        # Draw each point's checker stack and point number label.
        for pt in range(1, 25):
            col = _point_col(pt)
            count = self.points[pt]
            n = abs(count)
            is_top = pt >= 13  # Pieces point downward from _TOP.

            # Render point number label near the outer edge.
            label_row = _TOP - 1 if is_top else _BOT + 1
            if pt < 10:
                label_col = col + 1
            else:
                label_col = col
            builder.render_text(
                str(pt),
                row=label_row,
                col=label_col,
                use_number_sign=False,
                use_nemeth=True,
            )

            if n == 0:
                continue

            # Stacked checker dots (each checker = 2-dot wide segment).
            stack_height = min(n, _MAX_STACK)
            for i in range(stack_height):
                if is_top:
                    dot_row = _TOP + i
                else:
                    dot_row = _BOT - i
                # Fill the 2-dot wide checker segment.
                builder.draw_line(dot_row, col, 2)

        # Selection indicator.
        sel_col = _point_col(self.sel_point)
        if self.sel_point >= 13:
            # Top half: overline just below the label.
            ind_row = _TOP + min(abs(self.points[self.sel_point]), _MAX_STACK)
            builder.draw_line(ind_row, sel_col, _POINT_W - 1)
        else:
            # Bottom half: underline just above the label.
            ind_row = _BOT - min(abs(self.points[self.sel_point]), _MAX_STACK)
            builder.draw_line(ind_row, sel_col, _POINT_W - 1)

        self._last_rows = flush_rows(pad, builder, self._last_rows)
        send_status(pad, f"PT{self.sel_point} PAN/F1/F4 MOVE")
