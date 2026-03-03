"""Shared rendering helpers for grid-based games on the 60x40 dot display.

The DotPad X graphics area is 60 dot columns wide and 40 dot rows tall.
Braille cells are 3 dots wide x 4 dots tall; the display holds 20 cells per
row and 10 rows of cells.
"""

from __future__ import annotations

import dotpad as dp


def draw_grid(
    builder: dp.DotPadBuilder,
    top: int,
    left: int,
    rows: int,
    cols: int,
    cell_h: int,
    cell_w: int,
) -> None:
    """Draw a rectangular grid using horizontal and vertical dot lines.

    Args:
        builder: Active DotPadBuilder instance.
        top: Top-left dot row (1-based, within 1-40).
        left: Top-left dot column (1-based, within 1-60).
        rows: Number of grid rows.
        cols: Number of grid columns.
        cell_h: Height of each cell in dots.
        cell_w: Width of each cell in dots.
    """
    total_w = cols * cell_w + 1
    total_h = rows * cell_h + 1
    for r in range(rows + 1):
        builder.draw_line(top + r * cell_h, left, total_w)
    for c in range(cols + 1):
        builder.draw_vline(top, left + c * cell_w, total_h)


def draw_piece_square(builder: dp.DotPadBuilder, row: int, col: int) -> None:
    """Draw a 5x4 filled-rectangle piece (used for player-1 tokens).

    Matches the style used by Connect 4 player-1 pieces.

    Args:
        builder: Active DotPadBuilder instance.
        row: Top dot row of the piece (1-based).
        col: Left dot column of the piece (1-based).
    """
    builder.draw_rectangle(row, col, row + 3, col + 4)


def draw_piece_circle(builder: dp.DotPadBuilder, row: int, col: int) -> None:
    """Draw a 5x4 rounded-circle piece (used for player-2 tokens).

    Matches the style used by Connect 4 player-2 pieces.

    Args:
        builder: Active DotPadBuilder instance.
        row: Top dot row of the piece (1-based).
        col: Left dot column of the piece (1-based).
    """
    # Diamond / rounded shape built from diagonal lines.
    builder.draw_diag_line(row, col + 2, 3, "rtl")
    builder.draw_diag_line(row, col + 2, 3, "ltr")
    builder.draw_diag_line(row + 2, col, 3, "ltr")
    builder.draw_diag_line(row + 2, col + 4, 3, "rtl")
