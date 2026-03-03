"""Lightweight rendering helpers for Dot Game Center games.

These helpers wrap DotPadBuilder primitives to reduce boilerplate in game
renderers.  All coordinates use the DotPad dot convention: rows and columns
are 1-based, with row 1 at the top and col 1 at the left.  The standard
60 × 40 dot display is assumed (30 braille cells wide × 10 cell rows tall,
each braille cell being 3 dots wide × 4 dots tall in 8-dot format).
"""

from __future__ import annotations


def draw_grid(
    builder,
    top: int,
    left: int,
    cell_w: int,
    cell_h: int,
    nrows: int,
    ncols: int,
) -> None:
    """Draw a rectangular grid of *nrows* × *ncols* cells.

    Draws (*nrows* + 1) horizontal lines and (*ncols* + 1) vertical lines
    so the grid has a full outer border plus interior dividers.

    Args:
        builder: ``dp.DotPadBuilder`` instance to draw into.
        top:    Dot row of the topmost grid line (1-based).
        left:   Dot column of the leftmost grid line (1-based).
        cell_w: Width of each cell in dots.
        cell_h: Height of each cell in dots.
        nrows:  Number of cell rows.
        ncols:  Number of cell columns.
    """
    total_w = ncols * cell_w + 1  # width including right border dot
    total_h = nrows * cell_h + 1  # height including bottom border dot
    for r in range(nrows + 1):
        builder.draw_line(top + r * cell_h, left, total_w)
    for c in range(ncols + 1):
        builder.draw_vline(top, left + c * cell_w, total_h)


def flush_rows(
    pad,
    builder,
    last_rows: list[bytes] | None,
) -> list[bytes]:
    """Send only changed graphics rows to the DotPad.

    Compares the newly built frame against *last_rows* and sends only the
    lines that differ (or all lines when *last_rows* is ``None``).

    Args:
        pad:       ``dp.DotPad`` device instance.
        builder:   ``dp.DotPadBuilder`` holding the new frame.
        last_rows: Previously sent row bytes (``None`` for a full redraw).

    Returns:
        The new row bytes list (suitable for passing as *last_rows* next call).
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
