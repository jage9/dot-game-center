"""Chess game for Dot Game Center.

Standard chess rules:
- Player = white, AI = black.
- Castling (king-side and queen-side), en passant, pawn promotion.
- Promotion: automatically promotes to queen.
- Check and checkmate detection.
- Depth-2 minimax with alpha-beta pruning for AI.
- Stalemate and 50-move draw.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import draw_grid, cell_top_left, send_diff

# Piece constants (positive = white/player, negative = black/AI)
EMPTY = 0
W_PAWN, W_KNIGHT, W_BISHOP, W_ROOK, W_QUEEN, W_KING = 1, 2, 3, 4, 5, 6
B_PAWN, B_KNIGHT, B_BISHOP, B_ROOK, B_QUEEN, B_KING = -1, -2, -3, -4, -5, -6

# Grid layout: 8×8 on 60×40 dots, cell_w=7, cell_h=5
_TOP = 1
_LEFT = 3
_CELL_H = 5
_CELL_W = 7

# Piece letter for status display
_PIECE_NAMES = {
    W_PAWN: "P", W_KNIGHT: "N", W_BISHOP: "B",
    W_ROOK: "R", W_QUEEN: "Q", W_KING: "K",
    B_PAWN: "p", B_KNIGHT: "n", B_BISHOP: "b",
    B_ROOK: "r", B_QUEEN: "q", B_KING: "k",
}

# Piece values for AI evaluation
_PIECE_VALUES = {
    W_PAWN: 100, W_KNIGHT: 320, W_BISHOP: 330,
    W_ROOK: 500, W_QUEEN: 900, W_KING: 20000,
    B_PAWN: -100, B_KNIGHT: -320, B_BISHOP: -330,
    B_ROOK: -500, B_QUEEN: -900, B_KING: -20000,
}

# Starting board (row 0 = rank 8 on screen, row 7 = rank 1)
_START_BOARD = [
    [B_ROOK, B_KNIGHT, B_BISHOP, B_QUEEN, B_KING, B_BISHOP, B_KNIGHT, B_ROOK],
    [B_PAWN] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [EMPTY] * 8,
    [W_PAWN] * 8,
    [W_ROOK, W_KNIGHT, W_BISHOP, W_QUEEN, W_KING, W_BISHOP, W_KNIGHT, W_ROOK],
]


def _is_white(v: int) -> bool:
    return v > 0


def _is_black(v: int) -> bool:
    return v < 0


def _is_enemy(v: int, side: int) -> bool:
    """Return True if v is an enemy piece for the given side (1=white,-1=black)."""
    if side == 1:
        return v < 0
    return v > 0


def _ib(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8


@dataclass
class _State:
    """Mutable game state passed around for move generation."""
    board: list[list[int]]
    castling: list[bool]   # [wK-side, wQ-side, bK-side, bQ-side]
    ep_sq: Optional[tuple[int, int]]   # en passant target square
    half_moves: int        # for 50-move rule


def _copy_state(s: _State) -> _State:
    return _State(
        board=[row[:] for row in s.board],
        castling=s.castling[:],
        ep_sq=s.ep_sq,
        half_moves=s.half_moves,
    )


def _gen_moves(s: _State, side: int) -> list[tuple]:
    """Generate all pseudo-legal moves for side (1=white, -1=black).

    Returns list of (fr, fc, tr, tc) tuples.
    Special moves also encoded in the tuple:
    - Castling: (fr, fc, tr, tc, 'castle', rook_fr, rook_fc, rook_tr, rook_tc)
    - En passant: (fr, fc, tr, tc, 'ep', cap_r, cap_c)
    - Promotion: (fr, fc, tr, tc, 'promo', new_piece)
    """
    moves = []
    for r in range(8):
        for c in range(8):
            p = s.board[r][c]
            if p == EMPTY:
                continue
            if (side == 1 and not _is_white(p)) or (side == -1 and not _is_black(p)):
                continue
            abs_p = abs(p)
            if abs_p == 1:
                _gen_pawn(s, r, c, side, moves)
            elif abs_p == 2:
                _gen_knight(s, r, c, side, moves)
            elif abs_p == 3:
                _gen_slider(s, r, c, side, moves, [(-1, -1), (-1, 1), (1, -1), (1, 1)])
            elif abs_p == 4:
                _gen_slider(s, r, c, side, moves, [(-1, 0), (1, 0), (0, -1), (0, 1)])
            elif abs_p == 5:
                _gen_slider(s, r, c, side, moves, [(-1, -1), (-1, 1), (1, -1), (1, 1),
                                                     (-1, 0), (1, 0), (0, -1), (0, 1)])
            elif abs_p == 6:
                _gen_king(s, r, c, side, moves)
    return moves


def _gen_pawn(s: _State, r: int, c: int, side: int, moves: list) -> None:
    dr = -1 if side == 1 else 1   # white moves up (r decreasing), black moves down
    start_r = 6 if side == 1 else 1
    promo_r = 0 if side == 1 else 7
    # Forward one
    nr = r + dr
    if _ib(nr, c) and s.board[nr][c] == EMPTY:
        if nr == promo_r:
            promo = W_QUEEN if side == 1 else B_QUEEN
            moves.append((r, c, nr, c, 'promo', promo))
        else:
            moves.append((r, c, nr, c))
            # Forward two from start
            if r == start_r and s.board[nr + dr][c] == EMPTY:
                moves.append((r, c, nr + dr, c))
    # Captures
    for dc in (-1, 1):
        nc = c + dc
        nr = r + dr
        if not _ib(nr, nc):
            continue
        target = s.board[nr][nc]
        if _is_enemy(target, side) and target != EMPTY:
            if nr == promo_r:
                promo = W_QUEEN if side == 1 else B_QUEEN
                moves.append((r, c, nr, nc, 'promo', promo))
            else:
                moves.append((r, c, nr, nc))
        # En passant
        elif s.ep_sq == (nr, nc):
            moves.append((r, c, nr, nc, 'ep', r, nc))


def _gen_knight(s: _State, r: int, c: int, side: int, moves: list) -> None:
    for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                    (1, -2), (1, 2), (2, -1), (2, 1)]:
        nr, nc = r + dr, c + dc
        if _ib(nr, nc) and not (side == 1 and _is_white(s.board[nr][nc])) \
                        and not (side == -1 and _is_black(s.board[nr][nc])):
            moves.append((r, c, nr, nc))


def _gen_slider(s: _State, r: int, c: int, side: int, moves: list, dirs: list) -> None:
    for dr, dc in dirs:
        nr, nc = r + dr, c + dc
        while _ib(nr, nc):
            target = s.board[nr][nc]
            if target == EMPTY:
                moves.append((r, c, nr, nc))
            elif _is_enemy(target, side):
                moves.append((r, c, nr, nc))
                break
            else:
                break
            nr, nc = nr + dr, nc + dc


def _gen_king(s: _State, r: int, c: int, side: int, moves: list) -> None:
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if _ib(nr, nc):
                target = s.board[nr][nc]
                if target == EMPTY or _is_enemy(target, side):
                    moves.append((r, c, nr, nc))
    # Castling
    if side == 1:
        if s.castling[0] and s.board[7][5] == EMPTY and s.board[7][6] == EMPTY:
            moves.append((7, 4, 7, 6, 'castle', 7, 7, 7, 5))
        if s.castling[1] and s.board[7][3] == EMPTY and s.board[7][2] == EMPTY and s.board[7][1] == EMPTY:
            moves.append((7, 4, 7, 2, 'castle', 7, 0, 7, 3))
    else:
        if s.castling[2] and s.board[0][5] == EMPTY and s.board[0][6] == EMPTY:
            moves.append((0, 4, 0, 6, 'castle', 0, 7, 0, 5))
        if s.castling[3] and s.board[0][3] == EMPTY and s.board[0][2] == EMPTY and s.board[0][1] == EMPTY:
            moves.append((0, 4, 0, 2, 'castle', 0, 0, 0, 3))


def _apply_move(s: _State, mv: tuple) -> None:
    """Apply a move to the state in-place."""
    fr, fc, tr, tc = mv[0], mv[1], mv[2], mv[3]
    piece = s.board[fr][fc]
    s.board[tr][tc] = piece
    s.board[fr][fc] = EMPTY
    s.ep_sq = None

    extra = mv[4] if len(mv) > 4 else None
    if extra == 'castle':
        # Move the rook
        rfr, rfc, rtr, rtc = mv[5], mv[6], mv[7], mv[8]
        s.board[rtr][rtc] = s.board[rfr][rfc]
        s.board[rfr][rfc] = EMPTY
    elif extra == 'ep':
        cr, cc = mv[5], mv[6]
        s.board[cr][cc] = EMPTY
    elif extra == 'promo':
        s.board[tr][tc] = mv[5]

    # Two-square pawn advance → set en passant square
    if abs(piece) == 1 and abs(tr - fr) == 2:
        ep_r = (fr + tr) // 2
        s.ep_sq = (ep_r, fc)

    # Update castling rights
    if piece == W_KING:
        s.castling[0] = False
        s.castling[1] = False
    elif piece == B_KING:
        s.castling[2] = False
        s.castling[3] = False
    elif piece == W_ROOK:
        if fr == 7 and fc == 7:
            s.castling[0] = False
        elif fr == 7 and fc == 0:
            s.castling[1] = False
    elif piece == B_ROOK:
        if fr == 0 and fc == 7:
            s.castling[2] = False
        elif fr == 0 and fc == 0:
            s.castling[3] = False

    # 50-move rule counter
    if abs(piece) == 1 or s.board[tr][tc] != piece:  # pawn move or capture already applied
        s.half_moves = 0
    else:
        s.half_moves += 1


def _find_king(board: list[list[int]], side: int) -> Optional[tuple[int, int]]:
    king = W_KING if side == 1 else B_KING
    for r in range(8):
        for c in range(8):
            if board[r][c] == king:
                return r, c
    return None


def _is_attacked(board: list[list[int]], r: int, c: int, by_side: int) -> bool:
    """Return True if square (r,c) is attacked by by_side."""
    # Pawns
    pdr = 1 if by_side == 1 else -1   # attacking pawns come from above (white) or below (black)
    pawn = W_PAWN if by_side == 1 else B_PAWN
    for dc in (-1, 1):
        pr, pc = r - pdr, c + dc
        if _ib(pr, pc) and board[pr][pc] == pawn:
            return True
    # Knights
    knight = W_KNIGHT if by_side == 1 else B_KNIGHT
    for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
                    (1, -2), (1, 2), (2, -1), (2, 1)]:
        nr, nc = r + dr, c + dc
        if _ib(nr, nc) and board[nr][nc] == knight:
            return True
    # Sliders: bishop/queen
    bishop = W_BISHOP if by_side == 1 else B_BISHOP
    queen = W_QUEEN if by_side == 1 else B_QUEEN
    for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        nr, nc = r + dr, c + dc
        while _ib(nr, nc):
            p = board[nr][nc]
            if p == bishop or p == queen:
                return True
            if p != EMPTY:
                break
            nr, nc = nr + dr, nc + dc
    # Sliders: rook/queen
    rook = W_ROOK if by_side == 1 else B_ROOK
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        while _ib(nr, nc):
            p = board[nr][nc]
            if p == rook or p == queen:
                return True
            if p != EMPTY:
                break
            nr, nc = nr + dr, nc + dc
    # King
    king = W_KING if by_side == 1 else B_KING
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if _ib(nr, nc) and board[nr][nc] == king:
                return True
    return False


def _in_check(board: list[list[int]], side: int) -> bool:
    """Return True if *side*'s king is in check."""
    kpos = _find_king(board, side)
    if kpos is None:
        return True
    return _is_attacked(board, kpos[0], kpos[1], -side)


def _legal_moves(s: _State, side: int) -> list[tuple]:
    """Return truly legal moves (no self-check)."""
    pseudo = _gen_moves(s, side)
    legal = []
    for mv in pseudo:
        s2 = _copy_state(s)
        _apply_move(s2, mv)
        if not _in_check(s2.board, side):
            legal.append(mv)
    return legal


def _evaluate(board: list[list[int]]) -> int:
    """Static evaluation from white's perspective."""
    score = 0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p != EMPTY:
                score += _PIECE_VALUES.get(p, 0)
    return score


def _minimax(s: _State, depth: int, alpha: float, beta: float, side: int) -> float:
    """Minimax with alpha-beta. side=1 maximizes (white), side=-1 minimizes."""
    legal = _legal_moves(s, side)
    if not legal:
        if _in_check(s.board, side):
            # Checkmate
            return -20000 * side if side == 1 else 20000 * (-side)
        return 0  # Stalemate
    if depth == 0:
        return float(_evaluate(s.board))

    if side == 1:
        value = -math.inf
        for mv in legal:
            s2 = _copy_state(s)
            _apply_move(s2, mv)
            value = max(value, _minimax(s2, depth - 1, alpha, beta, -1))
            alpha = max(alpha, value)
            if beta <= alpha:
                break
        return value
    else:
        value = math.inf
        for mv in legal:
            s2 = _copy_state(s)
            _apply_move(s2, mv)
            value = min(value, _minimax(s2, depth - 1, alpha, beta, 1))
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value


@dataclass
class Chess:
    """Chess game vs AI (depth-2 minimax with alpha-beta pruning).

    Player = white (positive pieces), AI = black (negative pieces).
    """

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to starting position."""
        self._state = _State(
            board=[row[:] for row in _START_BOARD],
            castling=[True, True, True, True],
            ep_sq=None,
            half_moves=0,
        )
        self.sel_row: int = 7
        self.sel_col: int = 4
        self.selected: Optional[tuple[int, int]] = None
        self._legal_for_selected: list[tuple] = []
        self.turn: int = 1  # 1=player (white), -1=ai (black)
        self.winner: Optional[str] = None
        self._check: bool = False
        self._last_rows: Optional[list[bytes]] = None

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Navigation moves the cursor. F2 selects a piece (first press) then
        confirms the destination (second press). F3 cancels selection.

        Args:
            names: List of key names.
        """
        if self.winner or self.turn != 1:
            return
        if "panLeft" in names:
            self.sel_col = max(0, self.sel_col - 1)
        if "panRight" in names:
            self.sel_col = min(7, self.sel_col + 1)
        if "f1" in names:
            self.sel_row = max(0, self.sel_row - 1)
        if "f4" in names:
            self.sel_row = min(7, self.sel_row + 1)
        if "f3" in names:
            self.selected = None
            self._legal_for_selected = []
        if "f2" in names:
            self._on_action()

    def _on_action(self) -> None:
        r, c = self.sel_row, self.sel_col
        if self.selected is None:
            # Try to select a white piece
            p = self._state.board[r][c]
            if _is_white(p):
                moves = _legal_moves(self._state, 1)
                piece_moves = [m for m in moves if m[0] == r and m[1] == c]
                if piece_moves:
                    self.selected = (r, c)
                    self._legal_for_selected = piece_moves
        else:
            sr, sc = self.selected
            # Try to move to (r, c)
            for mv in self._legal_for_selected:
                if mv[2] == r and mv[3] == c:
                    _apply_move(self._state, mv)
                    self.selected = None
                    self._legal_for_selected = []
                    self.turn = -1
                    self._update_status()
                    return
            # Re-select different piece
            if self._state.board[r][c] > 0 and (r, c) != (sr, sc):
                self.selected = None
                self._on_action()  # recurse once to select new piece

    def _update_status(self) -> None:
        """Check for check/checkmate/stalemate/draw."""
        legal_for_ai = _legal_moves(self._state, -1)
        if not legal_for_ai:
            if _in_check(self._state.board, -1):
                self.winner = "player"   # white wins
            else:
                self.winner = "draw"     # stalemate
        elif self._state.half_moves >= 100:
            self.winner = "draw"
        self._check = _in_check(self._state.board, self.turn)

    # ------------------------------------------------------------------
    # AI
    # ------------------------------------------------------------------

    def run_ai_turn(self) -> bool:
        """Run one AI turn (depth-2 minimax). Return True if a move was made."""
        if self.winner is not None or self.turn != -1:
            return False
        legal = _legal_moves(self._state, -1)
        if not legal:
            if _in_check(self._state.board, -1):
                self.winner = "player"
            else:
                self.winner = "draw"
            return True
        best_mv = None
        best_val = math.inf
        alpha = -math.inf
        beta = math.inf
        random.shuffle(legal)  # randomize equally-scored moves
        for mv in legal:
            s2 = _copy_state(self._state)
            _apply_move(s2, mv)
            val = _minimax(s2, 1, alpha, beta, 1)
            if val < best_val:
                best_val = val
                best_mv = mv
            beta = min(beta, best_val)
        if best_mv:
            _apply_move(self._state, best_mv)
        self.turn = 1
        self._update_check_after_ai()
        return True

    def _update_check_after_ai(self) -> None:
        """Check game state after AI moves."""
        legal_player = _legal_moves(self._state, 1)
        if not legal_player:
            if _in_check(self._state.board, 1):
                self.winner = "cpu"
            else:
                self.winner = "draw"
        elif self._state.half_moves >= 100:
            self.winner = "draw"
        self._check = _in_check(self._state.board, 1)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the chess board to the DotPad.

        Args:
            pad: Active DotPad device instance.
        """
        builder = pad.builder()
        draw_grid(builder, _TOP, _LEFT, 8, 8, _CELL_H, _CELL_W)

        board = self._state.board
        dest_squares = {(m[2], m[3]) for m in self._legal_for_selected}

        for r in range(8):
            for c in range(8):
                p = board[r][c]
                if p == EMPTY:
                    continue
                crow, ccol = cell_top_left(_TOP, _LEFT, r, c, _CELL_H, _CELL_W)
                letter = _PIECE_NAMES.get(p, "?")
                # Render braille letter in the center of the cell
                builder.render_text(letter, row=crow + 1, col=ccol + 1, use_number_sign=False)

        # Highlight destination squares for selected piece
        for dr, dc in dest_squares:
            drow, dcol = cell_top_left(_TOP, _LEFT, dr, dc, _CELL_H, _CELL_W)
            builder.draw_line(drow + _CELL_H - 2, dcol + 1, 3)

        # Selection indicator
        if self.selected is not None:
            sr, sc = self.selected
            srow, scol = cell_top_left(_TOP, _LEFT, sr, sc, _CELL_H, _CELL_W)
            builder.draw_line(srow - 1, scol, 5)

        # Cursor indicator
        if self.winner is None and self.turn == 1:
            crow, ccol = cell_top_left(_TOP, _LEFT, self.sel_row, self.sel_col, _CELL_H, _CELL_W)
            builder.draw_line(crow + _CELL_H - 2, ccol + 2, 3)

        self._last_rows = send_diff(pad, builder, self._last_rows)
        self._send_status(pad)

    def _send_status(self, pad: dp.DotPad) -> None:
        if self.winner == "player":
            send_status(pad, "CHECKMATE YOU WIN")
        elif self.winner == "cpu":
            send_status(pad, "CHECKMATE YOU LOSE")
        elif self.winner == "draw":
            send_status(pad, "DRAW F3 MENU")
        elif self._check and self.turn == 1:
            send_status(pad, "CHECK! F2 SELECT")
        elif self.selected:
            send_status(pad, "F2 MOVE F3 CANCEL")
        elif self.turn == 1:
            send_status(pad, "F2 SELECT PIECE")
        else:
            send_status(pad, "AI THINKING...")
