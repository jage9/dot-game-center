"""Lightweight rendering helpers for DotPad game modules."""

from __future__ import annotations

import dotpad as dp


def draw_dot(builder: dp.DotPadBuilder, row: int, col: int) -> None:
    """Draw a single dot at dot coordinates (row, col)."""
    builder.draw_line(row, col, 1)


def draw_filled_rect(builder: dp.DotPadBuilder, row: int, col: int, h: int, w: int) -> None:
    """Fill a rectangle with dots (h rows, w cols)."""
    for r in range(h):
        builder.draw_line(row + r, col, w)


def draw_grid(
    builder: dp.DotPadBuilder,
    top: int,
    left: int,
    rows: int,
    cols: int,
    cell_h: int,
    cell_w: int,
) -> None:
    """Draw a rows×cols grid starting at (top, left) with given cell size.

    Args:
        builder: DotPadBuilder instance.
        top: Starting dot row (1-based).
        left: Starting dot column (1-based).
        rows: Number of grid rows.
        cols: Number of grid columns.
        cell_h: Cell height in dots.
        cell_w: Cell width in dots.
    """
    total_h = rows * cell_h + 1
    total_w = cols * cell_w + 1
    # Outer border
    builder.draw_rectangle(top, left, top + total_h - 1, left + total_w - 1)
    # Inner vertical lines
    for c in range(1, cols):
        builder.draw_vline(top, left + c * cell_w, total_h)
    # Inner horizontal lines
    for r in range(1, rows):
        builder.draw_line(top + r * cell_h, left, total_w)


def cell_top_left(
    grid_top: int,
    grid_left: int,
    row: int,
    col: int,
    cell_h: int,
    cell_w: int,
) -> tuple[int, int]:
    """Return the top-left dot coordinate of a cell in a grid.

    Args:
        grid_top: Grid top dot row.
        grid_left: Grid left dot col.
        row: Cell row index (0-based).
        col: Cell column index (0-based).
        cell_h: Cell height in dots.
        cell_w: Cell width in dots.

    Returns:
        (dot_row, dot_col) for top-left interior of the cell.
    """
    return grid_top + row * cell_h + 1, grid_left + col * cell_w + 1


def send_diff(pad: dp.DotPad, builder: dp.DotPadBuilder, last_rows: list[bytes] | None) -> list[bytes]:
    """Send only changed lines to the DotPad and return new rows.

    Args:
        pad: DotPad instance.
        builder: Fully populated builder.
        last_rows: Previous rows for diff, or None for full refresh.

    Returns:
        New rows list.
    """
    rows = builder.rows()
    if last_rows is None:
        for i, row_bytes in enumerate(rows, start=1):
            pad.send_display_line(i, row_bytes)
    else:
        for i, row_bytes in enumerate(rows, start=1):
            if row_bytes != last_rows[i - 1]:
                pad.send_display_line(i, row_bytes)
    return rows
