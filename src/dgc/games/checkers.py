"""American Checkers game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status

# Board layout constants for rendering
_BOARD_TOP = 1
_BOARD_LEFT = 2
_CELL_H = 5
_CELL_W = 7


@dataclass
class Checkers:
    """American Checkers: player=black (bottom, moves up), AI=red (top, moves down)."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to standard starting position."""
        self.board: list[list[int]] = [[0] * 8 for _ in range(8)]
        self._setup_board()
        self.cursor_row: int = 5
        self.cursor_col: int = 0
        self.selected: Optional[tuple[int, int]] = None
        self.legal_moves: list[list[tuple[int, int]]] = []
        self.legal_dests: set[tuple[int, int]] = set()
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    def _setup_board(self) -> None:
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = -1   # red (AI)
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = 1    # black (player)

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------

    def _find_regular_moves(
        self, r: int, c: int, color: int
    ) -> list[list[tuple[int, int]]]:
        piece = self.board[r][c]
        is_king = abs(piece) == 2
        dirs: list[tuple[int, int]] = []
        if color == 1:
            dirs = [(-1, -1), (-1, 1)]
            if is_king:
                dirs += [(1, -1), (1, 1)]
        else:
            dirs = [(1, -1), (1, 1)]
            if is_king:
                dirs += [(-1, -1), (-1, 1)]
        moves: list[list[tuple[int, int]]] = []
        for dr, dc in dirs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and self.board[nr][nc] == 0:
                moves.append([(r, c), (nr, nc)])
        return moves

    def _find_jumps(
        self,
        r: int,
        c: int,
        color: int,
        captured: set[tuple[int, int]],
    ) -> list[list[tuple[int, int]]]:
        """Recursively find all jump sequences from (r, c).

        Each returned path is a list of positions starting with (r, c).
        """
        piece = self.board[r][c]
        is_king = abs(piece) == 2
        result: list[list[tuple[int, int]]] = []

        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            # Forward-only restriction for non-kings
            if not is_king:
                if color == 1 and dr > 0:
                    continue
                if color == -1 and dr < 0:
                    continue

            mr, mc = r + dr, c + dc       # middle (opponent to capture)
            lr, lc = r + 2 * dr, c + 2 * dc   # landing square

            if not (0 <= mr < 8 and 0 <= mc < 8 and 0 <= lr < 8 and 0 <= lc < 8):
                continue
            if (mr, mc) in captured:
                continue
            mid = self.board[mr][mc]
            if mid == 0 or (mid > 0) == (color > 0):
                continue   # must jump opponent
            if self.board[lr][lc] != 0:
                continue   # landing must be empty

            new_captured = captured | {(mr, mc)}

            # Temporarily apply the jump to search for chained jumps
            saved_piece = self.board[r][c]
            saved_mid = self.board[mr][mc]
            self.board[r][c] = 0
            self.board[mr][mc] = 0
            # Handle temporary king promotion for continued-jump direction checks
            temp_piece = saved_piece
            if saved_piece == 1 and lr == 0:
                temp_piece = 2
            elif saved_piece == -1 and lr == 7:
                temp_piece = -2
            self.board[lr][lc] = temp_piece

            further = self._find_jumps(lr, lc, color, new_captured)

            self.board[r][c] = saved_piece
            self.board[mr][mc] = saved_mid
            self.board[lr][lc] = 0

            if further:
                for seq in further:
                    result.append([(r, c)] + seq)
            else:
                result.append([(r, c), (lr, lc)])

        return result

    def _get_all_moves(self, color: int) -> list[list[tuple[int, int]]]:
        """Return all legal moves for color; jump sequences if any exist."""
        jumps: list[list[tuple[int, int]]] = []
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 0:
                    continue
                p = self.board[r][c]
                if p == 0 or (p > 0) != (color > 0):
                    continue
                jumps.extend(self._find_jumps(r, c, color, set()))
        if jumps:
            return jumps

        moves: list[list[tuple[int, int]]] = []
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 0:
                    continue
                p = self.board[r][c]
                if p == 0 or (p > 0) != (color > 0):
                    continue
                moves.extend(self._find_regular_moves(r, c, color))
        return moves

    # ------------------------------------------------------------------
    # Execute move
    # ------------------------------------------------------------------

    def _execute_move(self, path: list[tuple[int, int]]) -> None:
        """Execute a move path, removing captured pieces and kinging."""
        fr, fc = path[0]
        piece = self.board[fr][fc]

        for i in range(len(path) - 1):
            r1, c1 = path[i]
            r2, c2 = path[i + 1]
            if abs(r2 - r1) == 2:
                mr, mc = (r1 + r2) // 2, (c1 + c2) // 2
                self.board[mr][mc] = 0

        tr, tc = path[-1]
        self.board[fr][fc] = 0
        self.board[tr][tc] = piece

        # King promotion
        if piece == 1 and tr == 0:
            self.board[tr][tc] = 2
        elif piece == -1 and tr == 7:
            self.board[tr][tc] = -2

    # ------------------------------------------------------------------
    # Win / selection helpers
    # ------------------------------------------------------------------

    def _check_winner(self) -> None:
        has_black = any(
            self.board[r][c] > 0 for r in range(8) for c in range(8)
        )
        has_red = any(
            self.board[r][c] < 0 for r in range(8) for c in range(8)
        )
        if not has_red:
            self.winner = "player"
        elif not has_black:
            self.winner = "ai"
        elif not self._get_all_moves(1) and not self._get_all_moves(-1):
            self.winner = "draw"

    def _try_select(self) -> None:
        r, c = self.cursor_row, self.cursor_col
        if self.board[r][c] <= 0:
            return
        all_moves = self._get_all_moves(1)
        piece_moves = [m for m in all_moves if m[0] == (r, c)]
        if not piece_moves:
            return
        self.selected = (r, c)
        self.legal_moves = piece_moves
        self.legal_dests = {m[-1] for m in piece_moves}

    def _try_move(self) -> None:
        dest = (self.cursor_row, self.cursor_col)
        if dest not in self.legal_dests:
            self.selected = None
            self.legal_moves = []
            self.legal_dests = set()
            return
        move = next(m for m in self.legal_moves if m[-1] == dest)
        self._execute_move(move)
        self.selected = None
        self.legal_moves = []
        self.legal_dests = set()
        self._check_winner()

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
        if "panLeft" in names:
            self.cursor_col = max(0, self.cursor_col - 1)
        if "panRight" in names:
            self.cursor_col = min(7, self.cursor_col + 1)
        if "f1" in names:
            self.cursor_row = max(0, self.cursor_row - 1)
        if "f4" in names:
            self.cursor_row = min(7, self.cursor_row + 1)
        if "f2" in names:
            if self.selected is None:
                self._try_select()
            else:
                self._try_move()

    def run_ai_turn(self) -> bool:
        """Run one AI turn with a random legal move (preferring captures).

        Returns:
            True if a move was made.
        """
        if self.winner is not None:
            return False
        moves = self._get_all_moves(-1)
        if not moves:
            self._check_winner()
            return False
        # Prefer longer jump sequences (captures)
        max_len = max(len(m) for m in moves)
        best = [m for m in moves if len(m) == max_len]
        self._execute_move(random.choice(best))
        self._check_winner()
        return True

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the current game state to the DotPad.

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

        # Pieces
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == 0:
                    continue
                pr = top + r * cell_h + 1
                pc = left + c * cell_w + 1
                if piece > 0:
                    # Player (black): filled square
                    builder.draw_rectangle(pr, pc, pr + 2, pc + 4)
                    builder.draw_line(pr + 1, pc + 1, 3)
                else:
                    # AI (red): circle
                    builder.draw_diag_line(pr, pc + 2, 2, "rtl")
                    builder.draw_diag_line(pr, pc + 2, 2, "ltr")
                    builder.draw_diag_line(pr + 2, pc, 2, "ltr")
                    builder.draw_diag_line(pr + 2, pc + 4, 2, "rtl")
                # King indicator: extra dot at top
                if abs(piece) == 2:
                    builder.draw_line(pr, pc + 2, 1)

        # Selected piece corner marks
        if self.selected is not None:
            sr, sc = self.selected
            ct = top + sr * cell_h + 1
            cl = left + sc * cell_w + 1
            builder.draw_line(ct, cl, 3)
            builder.draw_vline(ct, cl, 3)

        # Legal destination indicators
        for dr, dc in self.legal_dests:
            mr = top + dr * cell_h + 2
            mc = left + dc * cell_w + 3
            builder.draw_line(mr, mc, 2)

        # Cursor mark (bottom-right corner of cell)
        if self.winner is None:
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
        elif self.selected:
            send_status(pad, "PAN MOVE F2 DEST")
        else:
            send_status(pad, "PAN MOVE F2 SELECT")
