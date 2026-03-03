"""Chess game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status

# Piece constants: positive = white, negative = black
# 1=P 2=N 3=B 4=R 5=Q 6=K
_PIECE_CHAR: dict[int, str] = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q", 6: "K"}

_INITIAL_BOARD: list[list[int]] = [
    [-4, -2, -3, -5, -6, -3, -2, -4],
    [-1, -1, -1, -1, -1, -1, -1, -1],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0],
    [1, 1, 1, 1, 1, 1, 1, 1],
    [4, 2, 3, 5, 6, 3, 2, 4],
]

# Board rendering constants
_BOARD_TOP = 1
_BOARD_LEFT = 2
_CELL_H = 5
_CELL_W = 7


@dataclass
class Chess:
    """Chess with full rules: castling, en passant, promotion, check, stalemate."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to the standard starting position."""
        self.board: list[list[int]] = [row[:] for row in _INITIAL_BOARD]
        # Castling eligibility flags
        self.white_king_moved: bool = False
        self.black_king_moved: bool = False
        self.white_rook_a_moved: bool = False   # a-file rook (col 0)
        self.white_rook_h_moved: bool = False   # h-file rook (col 7)
        self.black_rook_a_moved: bool = False
        self.black_rook_h_moved: bool = False
        # En passant target: square a pawn can capture by moving there
        self.en_passant_target: Optional[tuple[int, int]] = None
        # Whose turn: 1=white, -1=black
        self.turn: int = 1
        # Selection state
        self.cursor_row: int = 6
        self.cursor_col: int = 4
        self.selected: Optional[tuple[int, int]] = None
        self.legal_dests: set[tuple[int, int]] = set()
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    # ------------------------------------------------------------------
    # Attack / check detection
    # ------------------------------------------------------------------

    def _is_attacked(self, r: int, c: int, by_color: int) -> bool:
        """Return True if square (r, c) is attacked by any piece of by_color."""
        # Knights
        for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                       (1, -2), (1, 2), (2, -1), (2, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if self.board[nr][nc] == 2 * by_color:
                    return True
        # Pawns (attack toward the opposite direction the pawn moves)
        pawn_dr = -by_color   # attacker's pawn attacks toward +by_color row
        for dc in (-1, 1):
            pr, pc = r + pawn_dr, c + dc
            if 0 <= pr < 8 and 0 <= pc < 8:
                if self.board[pr][pc] == by_color:
                    return True
        # King
        for dr, dc in [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                       (0, 1), (1, -1), (1, 0), (1, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                if self.board[nr][nc] == 6 * by_color:
                    return True
        # Rooks / queens (orthogonal)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                p = self.board[nr][nc]
                if p != 0:
                    if p == 4 * by_color or p == 5 * by_color:
                        return True
                    break
                nr += dr
                nc += dc
        # Bishops / queens (diagonal)
        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                p = self.board[nr][nc]
                if p != 0:
                    if p == 3 * by_color or p == 5 * by_color:
                        return True
                    break
                nr += dr
                nc += dc
        return False

    def _king_pos(self, color: int) -> tuple[int, int]:
        target = 6 * color
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == target:
                    return r, c
        raise RuntimeError(f"King not found for color {color}")

    def _in_check(self, color: int) -> bool:
        kr, kc = self._king_pos(color)
        return self._is_attacked(kr, kc, -color)

    # ------------------------------------------------------------------
    # Move application (temporary, for legal-move filtering)
    # ------------------------------------------------------------------

    def _apply_temp(self, fr: int, fc: int, tr: int, tc: int) -> dict:
        """Apply a move temporarily; return undo info."""
        piece = self.board[fr][fc]
        undo = {
            "board": [row[:] for row in self.board],
            "ep": self.en_passant_target,
        }
        self.board[tr][tc] = piece
        self.board[fr][fc] = 0
        # En passant capture
        if abs(piece) == 1 and (tr, tc) == self.en_passant_target:
            self.board[fr][tc] = 0
        # Promotion (temporary queen for check detection)
        if piece == 1 and tr == 0:
            self.board[tr][tc] = 5
        elif piece == -1 and tr == 7:
            self.board[tr][tc] = -5
        # Castling: move rook
        if abs(piece) == 6 and abs(tc - fc) == 2:
            if tc > fc:   # kingside
                self.board[fr][tc - 1] = self.board[fr][7]
                self.board[fr][7] = 0
            else:          # queenside
                self.board[fr][tc + 1] = self.board[fr][0]
                self.board[fr][0] = 0
        return undo

    def _undo_temp(self, undo: dict) -> None:
        self.board = undo["board"]
        self.en_passant_target = undo["ep"]

    # ------------------------------------------------------------------
    # Pseudo-legal move generation
    # ------------------------------------------------------------------

    def _pseudo_moves(self, r: int, c: int) -> list[tuple[int, int, int, int]]:
        """Generate pseudo-legal moves for the piece at (r, c)."""
        piece = self.board[r][c]
        if piece == 0:
            return []
        color = 1 if piece > 0 else -1
        abs_p = abs(piece)
        moves: list[tuple[int, int, int, int]] = []

        if abs_p == 1:   # Pawn
            direction = -color   # white moves up (-1), black moves down (+1)
            start_row = 6 if color == 1 else 1
            nr = r + direction
            if 0 <= nr < 8 and self.board[nr][c] == 0:
                moves.append((r, c, nr, c))
                nr2 = r + 2 * direction
                if r == start_row and self.board[nr2][c] == 0:
                    moves.append((r, c, nr2, c))
            for dc in (-1, 1):
                nc = c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target * color < 0:
                        moves.append((r, c, nr, nc))
                    elif self.en_passant_target == (nr, nc):
                        moves.append((r, c, nr, nc))

        elif abs_p == 2:   # Knight
            for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                           (1, -2), (1, 2), (2, -1), (2, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and self.board[nr][nc] * color <= 0:
                    moves.append((r, c, nr, nc))

        elif abs_p in (3, 4, 5):   # Bishop / Rook / Queen
            slide_dirs: list[tuple[int, int]] = []
            if abs_p in (3, 5):
                slide_dirs += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
            if abs_p in (4, 5):
                slide_dirs += [(-1, 0), (1, 0), (0, -1), (0, 1)]
            for dr, dc in slide_dirs:
                nr, nc = r + dr, c + dc
                while 0 <= nr < 8 and 0 <= nc < 8:
                    if self.board[nr][nc] * color > 0:
                        break
                    moves.append((r, c, nr, nc))
                    if self.board[nr][nc] * color < 0:
                        break
                    nr += dr
                    nc += dc

        elif abs_p == 6:   # King
            for dr, dc in [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                           (0, 1), (1, -1), (1, 0), (1, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and self.board[nr][nc] * color <= 0:
                    moves.append((r, c, nr, nc))
            # Castling
            king_row = 7 if color == 1 else 0
            if r == king_row and c == 4:
                # Kingside
                k_moved = self.white_king_moved if color == 1 else self.black_king_moved
                rh_moved = self.white_rook_h_moved if color == 1 else self.black_rook_h_moved
                if (not k_moved and not rh_moved
                        and self.board[king_row][5] == 0
                        and self.board[king_row][6] == 0):
                    moves.append((r, c, king_row, 6))
                # Queenside
                ra_moved = self.white_rook_a_moved if color == 1 else self.black_rook_a_moved
                if (not k_moved and not ra_moved
                        and self.board[king_row][1] == 0
                        and self.board[king_row][2] == 0
                        and self.board[king_row][3] == 0):
                    moves.append((r, c, king_row, 2))

        return moves

    # ------------------------------------------------------------------
    # Legal move generation (filters pseudo-legal by check)
    # ------------------------------------------------------------------

    def _legal_moves(self, r: int, c: int) -> list[tuple[int, int, int, int]]:
        """Return only moves that do not leave the player's king in check."""
        piece = self.board[r][c]
        if piece == 0:
            return []
        color = 1 if piece > 0 else -1
        result: list[tuple[int, int, int, int]] = []

        for move in self._pseudo_moves(r, c):
            fr, fc, tr, tc = move
            # For castling, the king may not start in check or pass through check
            if abs(piece) == 6 and abs(tc - fc) == 2:
                if self._in_check(color):
                    continue
                mid_c = (fc + tc) // 2
                undo_mid = self._apply_temp(fr, fc, fr, mid_c)
                through_check = self._in_check(color)
                self._undo_temp(undo_mid)
                if through_check:
                    continue

            undo = self._apply_temp(fr, fc, tr, tc)
            in_check = self._in_check(color)
            self._undo_temp(undo)
            if not in_check:
                result.append(move)

        return result

    def _all_legal_moves(self, color: int) -> list[tuple[int, int, int, int]]:
        """Return all legal moves for the given color."""
        moves: list[tuple[int, int, int, int]] = []
        for r in range(8):
            for c in range(8):
                if self.board[r][c] != 0 and (self.board[r][c] > 0) == (color > 0):
                    moves.extend(self._legal_moves(r, c))
        return moves

    # ------------------------------------------------------------------
    # Execute a move (permanent)
    # ------------------------------------------------------------------

    def _make_move(self, fr: int, fc: int, tr: int, tc: int) -> None:
        """Permanently apply a move, updating all state."""
        piece = self.board[fr][fc]
        color = 1 if piece > 0 else -1

        self.board[tr][tc] = piece
        self.board[fr][fc] = 0

        # En passant capture
        if abs(piece) == 1 and (tr, tc) == self.en_passant_target:
            self.board[fr][tc] = 0

        # Update en passant target
        if abs(piece) == 1 and abs(tr - fr) == 2:
            self.en_passant_target = ((fr + tr) // 2, fc)
        else:
            self.en_passant_target = None

        # Promotion (auto-queen)
        if piece == 1 and tr == 0:
            self.board[tr][tc] = 5
        elif piece == -1 and tr == 7:
            self.board[tr][tc] = -5

        # Castling: move rook and update flags
        if abs(piece) == 6 and abs(tc - fc) == 2:
            if tc > fc:   # kingside
                self.board[fr][tc - 1] = self.board[fr][7]
                self.board[fr][7] = 0
            else:          # queenside
                self.board[fr][tc + 1] = self.board[fr][0]
                self.board[fr][0] = 0

        # Update moved flags
        if piece == 6:
            self.white_king_moved = True
        elif piece == -6:
            self.black_king_moved = True
        if fr == 7 and fc == 0:
            self.white_rook_a_moved = True
        elif fr == 7 and fc == 7:
            self.white_rook_h_moved = True
        elif fr == 0 and fc == 0:
            self.black_rook_a_moved = True
        elif fr == 0 and fc == 7:
            self.black_rook_h_moved = True

        self.turn = -self.turn

    def _check_game_over(self) -> None:
        """Set self.winner if the game has ended."""
        moves = self._all_legal_moves(self.turn)
        if not moves:
            if self._in_check(self.turn):
                # Checkmate: the other side wins
                self.winner = "ai" if self.turn == 1 else "player"
            else:
                self.winner = "draw"

    # ------------------------------------------------------------------
    # Game API
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names pressed.
        """
        if self.winner:
            return
        if self.turn != 1:
            return   # not player's turn

        if "panLeft" in names:
            self.cursor_col = max(0, self.cursor_col - 1)
        if "panRight" in names:
            self.cursor_col = min(7, self.cursor_col + 1)
        if "f1" in names:
            self.cursor_row = max(0, self.cursor_row - 1)
        if "f4" in names:
            self.cursor_row = min(7, self.cursor_row + 1)
        if "f3" in names:
            # Deselect
            self.selected = None
            self.legal_dests = set()
        if "f2" in names:
            if self.selected is None:
                self._try_select()
            else:
                self._try_execute()

    def _try_select(self) -> None:
        r, c = self.cursor_row, self.cursor_col
        if self.board[r][c] <= 0:
            return
        moves = self._legal_moves(r, c)
        if not moves:
            return
        self.selected = (r, c)
        self.legal_dests = {(m[2], m[3]) for m in moves}

    def _try_execute(self) -> None:
        dest = (self.cursor_row, self.cursor_col)
        if dest not in self.legal_dests:
            # Clicking elsewhere: deselect or re-select
            self.selected = None
            self.legal_dests = set()
            self._try_select()
            return
        assert self.selected is not None
        sr, sc = self.selected
        self._make_move(sr, sc, dest[0], dest[1])
        self.selected = None
        self.legal_dests = set()
        self._check_game_over()

    def run_ai_turn(self) -> bool:
        """Run one AI turn (random legal black move).

        Returns:
            True if a move was made.
        """
        if self.winner is not None or self.turn != -1:
            return False
        moves = self._all_legal_moves(-1)
        if not moves:
            self._check_game_over()
            return False
        fr, fc, tr, tc = random.choice(moves)
        self._make_move(fr, fc, tr, tc)
        self._check_game_over()
        return True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the current board state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        top = _BOARD_TOP
        left = _BOARD_LEFT
        cell_h = _CELL_H
        cell_w = _CELL_W

        # Grid
        for i in range(9):
            builder.draw_line(top + i * cell_h, left, 8 * cell_w + 1)
        for j in range(9):
            builder.draw_vline(top, left + j * cell_w, 8 * cell_h + 1)

        # Pieces: one-char label centered in each cell
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == 0:
                    continue
                ch = _PIECE_CHAR.get(abs(piece), "?")
                if piece < 0:
                    ch = ch.lower()
                pr = top + r * cell_h + 1
                pc = left + c * cell_w + 2
                builder.render_text(ch, pr, pc, use_number_sign=False)

        # Selected piece: corner marks
        if self.selected is not None:
            sr, sc = self.selected
            ct = top + sr * cell_h + 1
            cl = left + sc * cell_w + 1
            builder.draw_line(ct, cl, 3)
            builder.draw_vline(ct, cl, 3)

        # Legal destinations: short line in cell center
        for dr, dc in self.legal_dests:
            mr = top + dr * cell_h + 2
            mc = left + dc * cell_w + 3
            builder.draw_line(mr, mc, 2)

        # Cursor indicator: small mark at bottom-right of cell
        if self.winner is None and self.turn == 1:
            ct = top + self.cursor_row * cell_h + cell_h - 2
            cl = left + self.cursor_col * cell_w + cell_w - 3
            builder.draw_line(ct, cl, 2)

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
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == "ai":
            send_status(pad, "YOU LOSE F3 MENU")
        elif self.winner == "draw":
            send_status(pad, "DRAW F3 MENU")
        elif self.turn == 1 and self._in_check(1):
            send_status(pad, "CHECK F2 MOVE")
        else:
            send_status(pad, "PAN F2 SEL/MOVE F3 DEL")
