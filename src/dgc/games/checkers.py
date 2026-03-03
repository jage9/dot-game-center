"""Checkers game logic and DotPad rendering.

The 8x8 board occupies the 60x40 dot display area:
  - left=2, top=1, cell_w=7, cell_h=4
  - Total: 2 + 7*8 + 1 = 59 cols, 1 + 4*8 + 1 = 34 rows

Player 1 (human, X) occupies the bottom three dark-square rows.
Player 2 (AI/opponent, O) occupies the top three dark-square rows.
Regular pieces use a small square/circle glyph; kings use a slightly
larger piece with a centre dot.

Controls:
  panLeft/panRight/f1/f4 – move cursor
  f2                      – select piece or confirm move destination
  f3                      – cancel selected piece
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid, draw_piece_square, draw_piece_circle

# Cell values
EMPTY  = 0
P1     = 1   # player 1 (human)
P2     = 2   # player 2 (opponent / display only)
P1_K   = 3   # player 1 king
P2_K   = 4   # player 2 king


def _initial_board() -> list[list[int]]:
    """Return the standard 8x8 checkers starting position."""
    board = [[EMPTY] * 8 for _ in range(8)]
    for r in range(3):
        for c in range(8):
            if (r + c) % 2 == 1:
                board[r][c] = P2
    for r in range(5, 8):
        for c in range(8):
            if (r + c) % 2 == 1:
                board[r][c] = P1
    return board


@dataclass
class Checkers:
    """Checkers game (human vs. display-mode opponent).

    Controls (DotPad keys):
      panLeft / panRight / f1 / f4 – move cursor
      f2                            – select piece / confirm move
      f3                            – cancel selection
    """

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to the standard starting position."""
        self.board: list[list[int]] = _initial_board()
        self.sel_row: int = 5
        self.sel_col: int = 0
        self.selected: Optional[tuple[int, int]] = None  # selected piece
        self.valid_moves: list[tuple[int, int]] = []
        self.winner: Optional[int] = None
        self._last_rows: list[bytes] | None = None

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names.
        """
        if self.winner is not None:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % 8
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % 8
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % 8
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % 8
        if "f2" in names:
            self._handle_confirm()
        if "f3" in names:
            self.selected = None
            self.valid_moves = []

    def _handle_confirm(self) -> None:
        r, c = self.sel_row, self.sel_col
        if self.selected is None:
            # Select own piece
            if self.board[r][c] in (P1, P1_K):
                self.selected = (r, c)
                self.valid_moves = self._get_moves(r, c)
        else:
            # Attempt to move to destination
            if (r, c) in self.valid_moves:
                self._do_move(self.selected[0], self.selected[1], r, c)
                self.selected = None
                self.valid_moves = []
                self._check_winner()
            else:
                # Re-select if another own piece clicked
                if self.board[r][c] in (P1, P1_K):
                    self.selected = (r, c)
                    self.valid_moves = self._get_moves(r, c)
                else:
                    self.selected = None
                    self.valid_moves = []

    def _get_moves(self, r: int, c: int) -> list[tuple[int, int]]:
        """Return valid destination squares for the piece at (r, c)."""
        piece = self.board[r][c]
        moves: list[tuple[int, int]] = []
        if piece == P1:
            dirs = [(-1, -1), (-1, 1)]  # move upward
        elif piece == P1_K:
            dirs = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            return []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if self.board[nr][nc] == EMPTY:
                    moves.append((nr, nc))
                elif self.board[nr][nc] in (P2, P2_K):
                    # Capture jump
                    jr, jc = nr + dr, nc + dc
                    if 0 <= jr < 8 and 0 <= jc < 8 and self.board[jr][jc] == EMPTY:
                        moves.append((jr, jc))
        return moves

    def _do_move(self, fr: int, fc: int, tr: int, tc: int) -> None:
        """Execute a move, capturing opponent pieces on jumps."""
        piece = self.board[fr][fc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = EMPTY
        # Capture mid-square on a 2-step jump
        dr = tr - fr
        dc = tc - fc
        if abs(dr) == 2:
            self.board[fr + dr // 2][fc + dc // 2] = EMPTY
        # Promotion
        if tr == 0 and piece == P1:
            self.board[tr][tc] = P1_K

    def _check_winner(self) -> None:
        """Set winner if one player has no pieces remaining."""
        has_p1 = any(self.board[r][c] in (P1, P1_K) for r in range(8) for c in range(8))
        has_p2 = any(self.board[r][c] in (P2, P2_K) for r in range(8) for c in range(8))
        if not has_p2:
            self.winner = 1
        elif not has_p1:
            self.winner = 2

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _draw_piece(
        self,
        builder: dp.DotPadBuilder,
        r: int,
        c: int,
        top: int,
        left: int,
        cell_w: int,
        cell_h: int,
    ) -> None:
        """Draw the piece at board (r, c) inside its cell."""
        piece = self.board[r][c]
        if piece == EMPTY:
            return
        base_row = top + r * cell_h + 1
        base_col = left + c * cell_w + 1
        if piece in (P1, P1_K):
            draw_piece_square(builder, base_row, base_col)
        else:
            draw_piece_circle(builder, base_row, base_col)
        # King indicator: centre dot (dot pattern "14" = top-right corner of cell)
        if piece in (P1_K, P2_K):
            builder.render_text_dots("14", row=base_row + 1, col=base_col + 2)

    # ------------------------------------------------------------------
    # Main render
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the checkers board to the DotPad.

        The 8x8 board uses cell_w=7, cell_h=4 within the 60x40 dot display.

        Args:
            pad: Active DotPad instance.
        """
        builder = pad.builder()

        top = 1
        left = 2
        cell_w = 7
        cell_h = 4

        # Board grid
        draw_grid(builder, top, left, 8, 8, cell_h, cell_w)

        # Pieces
        for r in range(8):
            for c in range(8):
                self._draw_piece(builder, r, c, top, left, cell_w, cell_h)

        # Highlight valid move destinations
        for tr, tc in self.valid_moves:
            indicator_row = top + tr * cell_h + cell_h - 1
            indicator_col = left + tc * cell_w + cell_w // 2
            builder.render_text_dots("4", row=indicator_row, col=indicator_col)

        # Cursor: short line below current cell
        if self.winner is None:
            cur_row = top + self.sel_row * cell_h + cell_h - 1
            cur_col = left + self.sel_col * cell_w + 2
            builder.draw_line(cur_row, cur_col, 3)

        # Selection indicator: top line above selected cell
        if self.selected is not None:
            sr, sc = self.selected
            sel_row = top + sr * cell_h
            sel_col = left + sc * cell_w + 1
            builder.draw_line(sel_row, sel_col, cell_w - 1)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        if self.winner == 1:
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == 2:
            send_status(pad, "YOU LOSE F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 MV F2 SEL")
