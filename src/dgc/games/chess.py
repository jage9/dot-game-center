"""Chess game board display and DotPad rendering.

The 8x8 board occupies the 60x40 dot display area:
  - left=2, top=1, cell_w=7, cell_h=4
  - Column labels (a-h) at row 35; row labels (1-8) at col 58.

Each piece is rendered as a single braille letter:
  White: K Q R B N P (uppercase via dot-6 capital prefix)
  Black: k q r b n p (lowercase)

Controls:
  panLeft/panRight/f1/f4 – move cursor
  f2                      – select piece / confirm destination
  f3                      – cancel selection
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid

# Piece codes: positive = white, negative = black
EMPTY  = 0
W_PAWN   = 1;  B_PAWN   = -1
W_KNIGHT = 2;  B_KNIGHT = -2
W_BISHOP = 3;  B_BISHOP = -3
W_ROOK   = 4;  B_ROOK   = -4
W_QUEEN  = 5;  B_QUEEN  = -5
W_KING   = 6;  B_KING   = -6

_PIECE_LETTER = {
    W_PAWN: "p", W_KNIGHT: "n", W_BISHOP: "b",
    W_ROOK: "r", W_QUEEN:  "q", W_KING:   "k",
    B_PAWN: "p", B_KNIGHT: "n", B_BISHOP: "b",
    B_ROOK: "r", B_QUEEN:  "q", B_KING:   "k",
}


def _initial_board() -> list[list[int]]:
    """Return the standard 8x8 chess starting position."""
    back = [W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING, W_BISHOP, W_KNIGHT, W_ROOK]
    board = [[EMPTY] * 8 for _ in range(8)]
    # White pieces on rows 6-7 (bottom of board as displayed)
    for c in range(8):
        board[7][c] = back[c]
        board[6][c] = W_PAWN
    # Black pieces on rows 0-1 (top of board as displayed)
    for c in range(8):
        board[0][c] = -back[c]
        board[1][c] = B_PAWN
    return board


@dataclass
class Chess:
    """Chess board with cursor navigation.

    Controls (DotPad keys):
      panLeft / panRight / f1 / f4 – move cursor
      f2                            – select piece / confirm destination
      f3                            – cancel selection
    """

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to the standard starting position."""
        self.board: list[list[int]] = _initial_board()
        self.sel_row: int = 7
        self.sel_col: int = 4  # white king
        self.selected: Optional[tuple[int, int]] = None
        self.valid_moves: list[tuple[int, int]] = []
        self.turn: int = 1        # 1 = white, -1 = black
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
        piece = self.board[r][c]
        if self.selected is None:
            # Select a piece belonging to the active player
            if piece != EMPTY and (piece > 0) == (self.turn == 1):
                self.selected = (r, c)
                self.valid_moves = self._get_moves(r, c)
        else:
            if (r, c) in self.valid_moves:
                self._do_move(self.selected[0], self.selected[1], r, c)
                self.selected = None
                self.valid_moves = []
                self._check_winner()
            elif piece != EMPTY and (piece > 0) == (self.turn == 1):
                # Re-select own piece
                self.selected = (r, c)
                self.valid_moves = self._get_moves(r, c)
            else:
                self.selected = None
                self.valid_moves = []

    def _get_moves(self, r: int, c: int) -> list[tuple[int, int]]:
        """Return pseudo-legal destination squares for piece at (r, c)."""
        piece = self.board[r][c]
        if piece == EMPTY:
            return []
        side = 1 if piece > 0 else -1
        moves: list[tuple[int, int]] = []

        def add(nr: int, nc: int) -> bool:
            """Add square if empty or enemy; return False if blocked."""
            if not (0 <= nr < 8 and 0 <= nc < 8):
                return False
            target = self.board[nr][nc]
            if target == EMPTY:
                moves.append((nr, nc))
                return True
            if (target > 0) != (side > 0):
                moves.append((nr, nc))  # capture
            return False  # blocked by any piece

        abs_piece = abs(piece)
        if abs_piece == abs(W_PAWN):
            fwd = -side  # white moves up (row decreases), black moves down
            if 0 <= r + fwd < 8 and self.board[r + fwd][c] == EMPTY:
                moves.append((r + fwd, c))
                # Double push from starting rank
                start = 6 if side == 1 else 1
                if r == start and self.board[r + 2 * fwd][c] == EMPTY:
                    moves.append((r + 2 * fwd, c))
            # Diagonal captures
            for dc in (-1, 1):
                nr, nc = r + fwd, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target != EMPTY and (target > 0) != (side > 0):
                        moves.append((nr, nc))

        elif abs_piece == abs(W_KNIGHT):
            for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                            (1, -2),  (1, 2),  (2, -1),  (2, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target == EMPTY or (target > 0) != (side > 0):
                        moves.append((nr, nc))

        elif abs_piece == abs(W_BISHOP):
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                nr, nc = r + dr, c + dc
                while add(nr, nc):
                    nr += dr; nc += dc

        elif abs_piece == abs(W_ROOK):
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                while add(nr, nc):
                    nr += dr; nc += dc

        elif abs_piece == abs(W_QUEEN):
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1),
                            (-1, 0),  (1, 0),  (0, -1),  (0, 1)]:
                nr, nc = r + dr, c + dc
                while add(nr, nc):
                    nr += dr; nc += dc

        elif abs_piece == abs(W_KING):
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1),
                            (-1, 0),  (1, 0),  (0, -1),  (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target == EMPTY or (target > 0) != (side > 0):
                        moves.append((nr, nc))

        return moves

    def _do_move(self, fr: int, fc: int, tr: int, tc: int) -> None:
        """Execute a move and switch turns."""
        self.board[tr][tc] = self.board[fr][fc]
        self.board[fr][fc] = EMPTY
        # Pawn promotion to queen
        piece = self.board[tr][tc]
        if piece == W_PAWN and tr == 0:
            self.board[tr][tc] = W_QUEEN
        elif piece == B_PAWN and tr == 7:
            self.board[tr][tc] = B_QUEEN
        self.turn = -self.turn

    def _check_winner(self) -> None:
        """Set winner when a king is captured (simplified end condition)."""
        kings = {
            self.board[r][c]
            for r in range(8)
            for c in range(8)
            if abs(self.board[r][c]) == abs(W_KING)
        }
        if W_KING not in kings:
            self.winner = -1  # black wins
        elif B_KING not in kings:
            self.winner = 1   # white wins

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the chess board to the DotPad.

        The 8x8 board uses cell_w=7, cell_h=4 within the 60x40 dot display.
        White pieces are rendered with a dot-6 capital prefix; black pieces
        are rendered as lowercase letters.

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
                piece = self.board[r][c]
                if piece == EMPTY:
                    continue
                letter = _PIECE_LETTER[piece]
                piece_row = top + r * cell_h + 2   # vertically centred
                piece_col = left + c * cell_w + 2  # horizontally centred
                if piece > 0:
                    # White: dot-6 capital prefix + lowercase letter
                    builder.render_text_dots("6", row=piece_row, col=piece_col)
                    builder.render_text(
                        letter, row=piece_row, col=piece_col + 3,
                        use_number_sign=False,
                    )
                else:
                    # Black: lowercase letter only
                    builder.render_text(
                        letter, row=piece_row, col=piece_col,
                        use_number_sign=False,
                    )

        # Highlight valid move destinations
        for tr, tc in self.valid_moves:
            ind_row = top + tr * cell_h + cell_h - 1
            ind_col = left + tc * cell_w + cell_w // 2
            builder.render_text_dots("4", row=ind_row, col=ind_col)

        # Cursor indicator: short underline
        if self.winner is None:
            cur_row = top + self.sel_row * cell_h + cell_h - 1
            cur_col = left + self.sel_col * cell_w + 2
            builder.draw_line(cur_row, cur_col, 3)

        # Selection indicator: top of cell
        if self.selected is not None:
            sr, sc = self.selected
            sel_row = top + sr * cell_h
            sel_col = left + sc * cell_w + 1
            builder.draw_line(sel_row, sel_col, cell_w - 1)

        # Column labels a-h at the bottom (row 36)
        for c in range(8):
            builder.render_text(
                chr(ord("a") + c),
                row=36,
                col=left + c * cell_w + 3,
                use_number_sign=False,
            )

        # Row labels 8-1 on the right edge (col 58)
        for r in range(8):
            builder.render_text(
                str(8 - r),
                row=top + r * cell_h + 2,
                col=58,
                use_number_sign=False,
                use_nemeth=True,
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

        turn_label = "WHITE" if self.turn == 1 else "BLACK"
        if self.winner == 1:
            send_status(pad, "WHITE WINS F3 MENU")
        elif self.winner == -1:
            send_status(pad, "BLACK WINS F3 MENU")
        else:
            send_status(pad, f"{turn_label} PAN/F2 SEL")
