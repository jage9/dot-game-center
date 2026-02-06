"""Shared helpers for game rendering."""


def row_to_dot(line: int) -> int:
    """Convert a 1-based line index to a dot row.

    Args:
        line: Line index (1..10).

    Returns:
        Dot row (1..40).
    """
    return (line - 1) * 4 + 1


def send_status(pad, message: str) -> None:
    """Send a fixed-width 20-cell status line with Nemeth/no number sign."""
    pad.send_text(message[:20].ljust(20), use_number_sign=False, use_nemeth=True)
