"""Shared rendering helpers for board games."""

from __future__ import annotations

import dotpad as dp


def board_to_dot(
    row: int, col: int, top: int, left: int, cell_h: int, cell_w: int
) -> tuple[int, int]:
    """Convert board coordinates to dot coordinates (top-left corner of cell).

    Args:
        row: Board row index (0-based).
        col: Board column index (0-based).
        top: Top dot coordinate of the board.
        left: Left dot coordinate of the board.
        cell_h: Height of each cell in dots.
        cell_w: Width of each cell in dots.

    Returns:
        Tuple of (dot_row, dot_col).
    """
    return top + row * cell_h, left + col * cell_w


def draw_grid(
    builder: dp.DotPadBuilder,
    top: int,
    left: int,
    rows: int,
    cols: int,
    cell_h: int,
    cell_w: int,
) -> None:
    """Draw a complete grid including outer border and all internal separators.

    Args:
        builder: DotPadBuilder instance.
        top: Top dot coordinate of the grid.
        left: Left dot coordinate of the grid.
        rows: Number of rows in the grid.
        cols: Number of columns in the grid.
        cell_h: Height of each cell in dots.
        cell_w: Width of each cell in dots.
    """
    total_w = cols * cell_w + 1
    total_h = rows * cell_h + 1
    for i in range(rows + 1):
        builder.draw_line(top + i * cell_h, left, total_w)
    for j in range(cols + 1):
        builder.draw_vline(top, left + j * cell_w, total_h)


def fill_cell(
    builder: dp.DotPadBuilder,
    top: int,
    left: int,
    row: int,
    col: int,
    cell_h: int,
    cell_w: int,
) -> None:
    """Fill a cell interior with horizontal lines forming a solid dot block.

    Args:
        builder: DotPadBuilder instance.
        top: Top dot coordinate of the board.
        left: Left dot coordinate of the board.
        row: Board row index (0-based).
        col: Board column index (0-based).
        cell_h: Height of each cell in dots.
        cell_w: Width of each cell in dots.
    """
    dr, dc = board_to_dot(row, col, top, left, cell_h, cell_w)
    for i in range(1, cell_h):
        builder.draw_line(dr + i, dc + 1, cell_w - 1)


def draw_piece_square(
    builder: dp.DotPadBuilder, r: int, c: int, size: int
) -> None:
    """Draw a rectangle outline piece at dot position (r, c).

    Args:
        builder: DotPadBuilder instance.
        r: Top dot row.
        c: Left dot column.
        size: Side length of the square in dots.
    """
    builder.draw_rectangle(r, c, r + size - 1, c + size - 1)


def draw_piece_circle(
    builder: dp.DotPadBuilder, r: int, c: int, size: int
) -> None:
    """Draw an approximate circle piece at dot position (r, c).

    Uses four 3-step diagonal arcs at each quadrant to approximate a circle.

    Args:
        builder: DotPadBuilder instance.
        r: Top dot row.
        c: Left dot column.
        size: Bounding box size in dots (should be ≥ 5).
    """
    half = size // 2
    builder.draw_diag_line(r, c + half, 3, "rtl")
    builder.draw_diag_line(r, c + half, 3, "ltr")
    builder.draw_diag_line(r + half, c, 3, "ltr")
    builder.draw_diag_line(r + half, c + size - 1, 3, "rtl")


def draw_piece_x(
    builder: dp.DotPadBuilder, r: int, c: int, size: int
) -> None:
    """Draw an X using two crossing diagonal lines at dot position (r, c).

    Args:
        builder: DotPadBuilder instance.
        r: Top dot row.
        c: Left dot column.
        size: Size of the X in dots.
    """
    builder.draw_diag_line(r, c, size, "ltr")
    builder.draw_diag_line(r, c + size - 1, size, "rtl")
