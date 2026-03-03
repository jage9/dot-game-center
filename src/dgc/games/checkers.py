"""American (English) Checkers for Dot Game Center.

Rules:
- 8×8 board, dark squares only (standard American/English rules).
- Player is red (moves up the board, from row 7 toward row 0).
- AI is black (moves down the board, from row 0 toward row 7).
- Forced captures (longest capture not enforced, but any capture must be taken).
- Multiple jumps in a single turn.
- Kinging at back rank.
- Win: opponent has no pieces or no legal moves.
- Draw: 40 consecutive non-capture, non-kinging moves (half-move clock).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid, cell_top_left, send_diff

# Piece constants
EMPTY = 0
PLAYER = 1   # red
AI = 2       # black
PLAYER_K = 3  # red king
AI_K = 4     # black king

# Grid layout: 8×8 on 60×40 dots → cell_w=7, cell_h=5
_TOP = 1
_LEFT = 3
_CELL_H = 5
_CELL_W = 7


def _is_player(v: int) -> bool:
    return v in (PLAYER, PLAYER_K)


def _is_ai(v: int) -> bool:
    return v in (AI, AI_K)


def _is_king(v: int) -> bool:
    return v in (PLAYER_K, AI_K)


def _owner(v: int) -> int:
    """Return 1 (player), 2 (ai), or 0 (empty)."""
    if v in (PLAYER, PLAYER_K):
        return 1
    if v in (AI, AI_K):
        return 2
    return 0


@dataclass
class Checkers:
    """American checkers with forced captures and simple AI."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the board to starting position."""
        self.board: list[list[int]] = [[EMPTY] * 8 for _ in range(8)]
        # Black pieces (AI) on rows 0-2 on dark squares
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = AI
        # Red pieces (player) on rows 5-7 on dark squares
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = PLAYER
        self.sel_row: int = 5
        self.sel_col: int = 1
        self.selected: Optional[tuple[int, int]] = None
        self.turn: int = 1  # 1=player, 2=ai
        self.winner: Optional[str] = None
        self._half_moves: int = 0  # for draw detection
        self._last_rows: Optional[list[bytes]] = None
        self._status_msg: str = "F2 SELECT PIECE"
        # Multi-jump tracking
        self._jumping_piece: Optional[tuple[int, int]] = None
        # Normalize cursor to a valid dark square
        self._snap_cursor_to_valid()

    # ------------------------------------------------------------------
    # Move generation
    # ------------------------------------------------------------------

    def _dark(self, r: int, c: int) -> bool:
        return (r + c) % 2 == 1

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < 8 and 0 <= c < 8

    def _get_moves(self, side: int) -> list[tuple]:
        """Return all legal moves for *side* (1=player, 2=ai).

        Returns list of (fr, fc, tr, tc) for simple moves
        or (fr, fc, tr, tc, mr, mc) for captures (midpoint row/col).
        """
        simple: list[tuple] = []
        captures: list[tuple] = []
        for r in range(8):
            for c in range(8):
                if _owner(self.board[r][c]) == side:
                    captures.extend(self._piece_captures(r, c))
                    simple.extend(self._piece_simple(r, c))
        return captures if captures else simple

    def _piece_dir(self, piece: int) -> list[int]:
        """Movement directions (row delta) for a piece."""
        if piece == PLAYER:
            return [-1]
        if piece == AI:
            return [1]
        return [-1, 1]  # kings

    def _piece_simple(self, r: int, c: int) -> list[tuple]:
        piece = self.board[r][c]
        moves = []
        for dr in self._piece_dir(piece):
            for dc in (-1, 1):
                nr, nc = r + dr, c + dc
                if self._in_bounds(nr, nc) and self.board[nr][nc] == EMPTY:
                    moves.append((r, c, nr, nc))
        return moves

    def _piece_captures(self, r: int, c: int) -> list[tuple]:
        piece = self.board[r][c]
        owner = _owner(piece)
        captures = []
        for dr in self._piece_dir(piece):
            for dc in (-1, 1):
                mr, mc = r + dr, c + dc
                nr, nc = r + 2 * dr, c + 2 * dc
                if not self._in_bounds(nr, nc):
                    continue
                mid = self.board[mr][mc]
                if _owner(mid) != 0 and _owner(mid) != owner and self.board[nr][nc] == EMPTY:
                    captures.append((r, c, nr, nc, mr, mc))
        return captures

    def _has_captures(self, r: int, c: int) -> bool:
        return bool(self._piece_captures(r, c))

    def _any_capture(self, side: int) -> bool:
        for r in range(8):
            for c in range(8):
                if _owner(self.board[r][c]) == side and self._piece_captures(r, c):
                    return True
        return False

    # ------------------------------------------------------------------
    # Move application
    # ------------------------------------------------------------------

    def _apply_move(self, move: tuple) -> bool:
        """Apply a simple or capture move. Return True if it was a capture."""
        fr, fc, tr, tc = move[0], move[1], move[2], move[3]
        piece = self.board[fr][fc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = EMPTY
        captured = False
        if len(move) == 6:
            mr, mc = move[4], move[5]
            self.board[mr][mc] = EMPTY
            captured = True
        # Kinging
        if piece == PLAYER and tr == 0:
            self.board[tr][tc] = PLAYER_K
        elif piece == AI and tr == 7:
            self.board[tr][tc] = AI_K
        return captured

    def _check_win_draw(self) -> None:
        """Set winner if game over condition is met."""
        if self._half_moves >= 80:
            self.winner = "draw"
            return
        player_moves = self._get_moves(1)
        ai_moves = self._get_moves(2)
        if not player_moves:
            self.winner = "cpu"
        elif not ai_moves:
            self.winner = "player"

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Navigation moves cursor on dark squares. F2 selects/moves a piece.
        F3 cancels current selection.

        Args:
            names: List of key names.
        """
        if self.winner or self.turn != 1:
            return

        if "panLeft" in names:
            self._move_cursor(0, -1)
        if "panRight" in names:
            self._move_cursor(0, 1)
        if "f1" in names:
            self._move_cursor(-1, 0)
        if "f4" in names:
            self._move_cursor(1, 0)
        if "f3" in names:
            self.selected = None
            self._jumping_piece = None
        if "f2" in names:
            self._on_action()

    def _move_cursor(self, dr: int, dc: int) -> None:
        nr = max(0, min(7, self.sel_row + dr))
        nc = max(0, min(7, self.sel_col + dc))
        # Keep cursor on dark squares
        if self._dark(nr, nc):
            self.sel_row, self.sel_col = nr, nc
        else:
            # Shift one more column in the same direction to land on a dark square
            nc2 = nc + (1 if dc >= 0 else -1)
            if 0 <= nc2 < 8 and self._dark(nr, nc2):
                self.sel_row, self.sel_col = nr, nc2
            elif 0 <= nc - (1 if dc >= 0 else -1) < 8 and self._dark(nr, nc - (1 if dc >= 0 else -1)):
                self.sel_row, self.sel_col = nr, nc - (1 if dc >= 0 else -1)

    def _snap_cursor_to_valid(self) -> None:
        """Move cursor to the first player piece that has legal moves."""
        moves = self._get_moves(1)
        if moves:
            self.sel_row, self.sel_col = moves[0][0], moves[0][1]
            return
        # Fallback: any player piece
        for r in range(7, -1, -1):
            for c in range(8):
                if self.board[r][c] in (PLAYER, PLAYER_K):
                    self.sel_row, self.sel_col = r, c
                    return

    def _on_action(self) -> None:
        """Handle F2 press: select piece or move to destination."""
        r, c = self.sel_row, self.sel_col

        if self._jumping_piece is not None:
            # Must continue jumping with the jumping piece
            jr, jc = self._jumping_piece
            captures = self._piece_captures(jr, jc)
            for mv in captures:
                if mv[2] == r and mv[3] == c:
                    self._apply_move(mv)
                    self._half_moves = 0
                    # Check if can continue jumping
                    new_captures = self._piece_captures(r, c)
                    # Stop multi-jump if piece was just kinged
                    just_kinged = self.board[r][c] == PLAYER_K and r == 0
                    if new_captures and not just_kinged:
                        self._jumping_piece = (r, c)
                        self.sel_row, self.sel_col = r, c
                    else:
                        self._jumping_piece = None
                        self.turn = 2
                        self._check_win_draw()
                    return
            return

        if self.selected is None:
            # Select a player piece
            if _is_player(self.board[r][c]):
                # If there are any captures available, only allow selecting a piece with captures
                if self._any_capture(1):
                    if self._piece_captures(r, c):
                        self.selected = (r, c)
                else:
                    if self._piece_simple(r, c):
                        self.selected = (r, c)
        else:
            sr, sc = self.selected
            # Try to move selected piece to cursor
            all_moves = self._get_moves(1)
            for mv in all_moves:
                if mv[0] == sr and mv[1] == sc and mv[2] == r and mv[3] == c:
                    is_capture = self._apply_move(mv)
                    if is_capture:
                        self._half_moves = 0
                        # Check for continuation jump
                        new_captures = self._piece_captures(r, c)
                        # Stop multi-jump if piece was just kinged (reached promotion row)
                        just_kinged = self.board[r][c] == PLAYER_K and r == 0
                        if new_captures and not just_kinged:
                            self._jumping_piece = (r, c)
                            self.selected = None
                            self.sel_row, self.sel_col = r, c
                        else:
                            self.selected = None
                            self._jumping_piece = None
                            self.turn = 2
                            self._check_win_draw()
                    else:
                        self._half_moves += 1
                        self.selected = None
                        self._jumping_piece = None
                        self.turn = 2
                        self._check_win_draw()
                    return
            # Clicked own piece: re-select it
            if _is_player(self.board[r][c]) and (r, c) != (sr, sc):
                self.selected = None
                self._on_action()  # re-enter with no selection

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------

    def run_ai_turn(self) -> bool:
        """Run one AI turn. Return True if a move was made."""
        if self.winner is not None or self.turn != 2:
            return False
        moves = self._get_moves(2)
        if not moves:
            self.winner = "player"
            self.turn = 1
            return True
        # Prefer captures; among captures pick one that leads to most remaining captures
        captures = [m for m in moves if len(m) == 6]
        if captures:
            move = self._pick_best_capture(captures)
            self._apply_move(move)
            self._half_moves = 0
            # Check multi-jump
            fr, fc, tr, tc = move[0], move[1], move[2], move[3]
            next_caps = self._piece_captures(tr, tc)
            while next_caps:
                mv2 = random.choice(next_caps)
                self._apply_move(mv2)
                ntr, ntc = mv2[2], mv2[3]
                # Stop if piece was just kinged (AI kinging row = 7)
                if self.board[ntr][ntc] == AI_K and ntr == 7:
                    break
                next_caps = self._piece_captures(ntr, ntc)
                tr, tc = ntr, ntc
        else:
            move = random.choice(moves)
            self._apply_move(move)
            self._half_moves += 1
        self.turn = 1
        self._check_win_draw()
        return True

    def _pick_best_capture(self, captures: list[tuple]) -> tuple:
        """Pick the capture move that maximizes subsequent captures (greedy)."""
        best = captures[0]
        best_count = 0
        for mv in captures:
            count = len(self._piece_captures(mv[2], mv[3]))
            if count > best_count:
                best_count = count
                best = mv
        return best

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the checkers board to the DotPad.

        Args:
            pad: Active DotPad device instance.
        """
        builder = pad.builder()
        draw_grid(builder, _TOP, _LEFT, 8, 8, _CELL_H, _CELL_W)

        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == EMPTY:
                    continue
                crow, ccol = cell_top_left(_TOP, _LEFT, r, c, _CELL_H, _CELL_W)
                # Center of cell interior (cell interior is _CELL_H-1=4 tall, _CELL_W-1=6 wide)
                cr = crow + 1
                cc = ccol + 1
                if piece == PLAYER:
                    self._draw_piece_player(builder, cr, cc)
                elif piece == AI:
                    self._draw_piece_ai(builder, cr, cc)
                elif piece == PLAYER_K:
                    self._draw_piece_player(builder, cr, cc)
                    builder.draw_line(cr, cc + 1, 3)  # king crown
                elif piece == AI_K:
                    self._draw_piece_ai(builder, cr, cc)
                    builder.draw_line(cr, cc + 1, 3)  # king crown

        # Selection highlight
        if self.selected is not None:
            sr, sc = self.selected
            srow, scol = cell_top_left(_TOP, _LEFT, sr, sc, _CELL_H, _CELL_W)
            # Draw corners of selected cell
            builder.draw_line(srow - 1, scol - 1, 3)
            builder.draw_line(srow + _CELL_H - 2, scol - 1, 3)

        # Cursor indicator (small line at bottom of cursor cell)
        if self.winner is None and self.turn == 1:
            crow, ccol = cell_top_left(_TOP, _LEFT, self.sel_row, self.sel_col, _CELL_H, _CELL_W)
            builder.draw_line(crow + _CELL_H - 2, ccol + 1, 4)

        self._last_rows = send_diff(pad, builder, self._last_rows)
        self._send_status(pad)

    def _draw_piece_player(self, builder: dp.DotPadBuilder, r: int, c: int) -> None:
        """Draw a player piece (X shape, 3×3 dots)."""
        builder.draw_diag_line(r, c, 3, "ltr")
        builder.draw_diag_line(r, c + 2, 3, "rtl")

    def _draw_piece_ai(self, builder: dp.DotPadBuilder, r: int, c: int) -> None:
        """Draw an AI piece (small square, 3×3 dots)."""
        builder.draw_rectangle(r, c, r + 2, c + 2)

    def _send_status(self, pad: dp.DotPad) -> None:
        if self.winner == "player":
            self._status_msg = "YOU WIN"
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == "cpu":
            self._status_msg = "YOU LOSE"
            send_status(pad, "YOU LOSE F3 MENU")
        elif self.winner == "draw":
            self._status_msg = "DRAW"
            send_status(pad, "DRAW F3 MENU")
        elif self.turn == 1:
            if self.selected:
                self._status_msg = "F2 MOVE F3 CANCEL"
                send_status(pad, "F2 MOVE F3 CANCEL")
            else:
                self._status_msg = "F2 SELECT PIECE"
                send_status(pad, "F2 SELECT PIECE")
        else:
            self._status_msg = "AI THINKING"
            send_status(pad, "AI THINKING...")
