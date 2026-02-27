"""Checkers game logic and DotPad rendering."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Optional, List, Tuple

import dotpad as dp
from .utils import send_status


@dataclass
class Checkers:
    """Checkers with 8x8 grid and simple AI."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the board."""
        # 0: empty, 1: P1, 2: P1 King, 3: P2, 4: P2 King
        self.board = [[0 for _ in range(8)] for _ in range(8)]
        for r in range(3):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = 3 # AI
        for r in range(5, 8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    self.board[r][c] = 1 # Player
        
        self.sel_row = 5
        self.sel_col = 0
        self.selected_piece: Optional[Tuple[int, int]] = None
        self.valid_moves: List[Tuple[int, int]] = []
        self.turn = "player"
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        if self.winner or self.turn == "ai":
            return
            
        if "panLeft" in names: self.sel_col = (self.sel_col - 1) % 8
        if "panRight" in names: self.sel_col = (self.sel_col + 1) % 8
        if "f1" in names: self.sel_row = (self.sel_row - 1) % 8
        if "f4" in names: self.sel_row = (self.sel_row + 1) % 8
        
        if "f2" in names:
            self._handle_select()

    def _handle_select(self) -> None:
        target = (self.sel_row, self.sel_col)
        piece = self.board[self.sel_row][self.sel_col]
        
        if self.selected_piece:
            if target in self.valid_moves:
                self._make_move(self.selected_piece, target)
                self.selected_piece = None
                self.valid_moves = []
                self.turn = "ai"
                self._check_winner()
            else:
                # Deselect or select another of own piece
                if piece in (1, 2):
                    self.selected_piece = target
                    self.valid_moves = self._get_valid_moves(target)
                else:
                    self.selected_piece = None
                    self.valid_moves = []
        else:
            if piece in (1, 2):
                self.selected_piece = target
                self.valid_moves = self._get_valid_moves(target)

    def _get_valid_moves(self, pos: Tuple[int, int], board=None) -> List[Tuple[int, int]]:
        if board is None: board = self.board
        r, c = pos
        piece = board[r][c]
        moves = []
        
        # Directions: 1, 2 (Player) move up (-1); 3, 4 (AI) move down (+1). Kings move both.
        dirs = []
        if piece in (1, 2): dirs.append(-1)
        if piece in (3, 4): dirs.append(1)
        if piece in (2, 4): 
            if -1 not in dirs: dirs.append(-1)
            if 1 not in dirs: dirs.append(1)
            
        # Check jumps first (forced jump rule simplified here: prefer jumps)
        jumps = []
        for dr in dirs:
            for dc in [-1, 1]:
                nr, nc = r + dr, c + dc
                jr, jc = r + 2*dr, c + 2*dc
                if 0 <= jr < 8 and 0 <= jc < 8:
                    mid = board[nr][nc]
                    if mid != 0 and (mid in (1, 2)) != (piece in (1, 2)) and board[jr][jc] == 0:
                        jumps.append((jr, jc))
        
        if jumps: return jumps
        
        # Simple moves
        for dr in dirs:
            for dc in [-1, 1]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == 0:
                    moves.append((nr, nc))
        return moves

    def _make_move(self, start: Tuple[int, int], end: Tuple[int, int], board=None):
        if board is None: board = self.board
        sr, sc = start
        er, ec = end
        piece = board[sr][sc]
        
        board[er][ec] = piece
        board[sr][sc] = 0
        
        # Promotion
        if piece == 1 and er == 0: board[er][ec] = 2
        if piece == 3 and er == 7: board[er][ec] = 4
        
        # Capture
        if abs(sr - er) == 2:
            mr, mc = (sr + er) // 2, (sc + ec) // 2
            board[mr][mc] = 0

    def run_ai_turn(self) -> bool:
        if self.turn != "ai" or self.winner:
            return False
        
        best_move = self._get_best_ai_move()
        if best_move:
            self._make_move(best_move[0], best_move[1])
        
        self.turn = "player"
        self._check_winner()
        return True

    def _get_best_ai_move(self) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        all_moves = []
        for r in range(8):
            for c in range(8):
                if self.board[r][c] in (3, 4):
                    moves = self._get_valid_moves((r, c))
                    for m in moves:
                        all_moves.append(((r, c), m))
        
        if not all_moves: return None
        # Simple priority: jumps first, then random
        jumps = [move for move in all_moves if abs(move[0][0] - move[1][0]) == 2]
        if jumps: return random.choice(jumps)
        return random.choice(all_moves)

    def _check_winner(self) -> None:
        p1 = any(self.board[r][c] in (1, 2) for r in range(8) for c in range(8))
        p2 = any(self.board[r][c] in (3, 4) for r in range(8) for c in range(8))
        if not p1: self.winner = "AI"
        if not p2: self.winner = "PLAYER"

    def render(self, pad: dp.DotPad) -> None:
        builder = pad.builder()
        
        top = 1
        left = 10
        cell_size = 4 # 4x4 dots per cell
        
        # Board background (checkered pattern)
        for r in range(8):
            for c in range(8):
                if (r + c) % 2 == 1:
                    # Draw a single dot in middle of dark squares for tactile reference
                    builder.buffer.set_dot(top + r*cell_size + 2, left + c*cell_size + 2, True)
                    
        # Pieces
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p == 0: continue
                
                br = top + r*cell_size
                bc = left + c*cell_size
                
                if p in (1, 2): # Player: Hollow 3x3
                    builder.draw_rectangle(br + 1, bc + 1, br + 3, bc + 3)
                    if p == 2: # King: center dot
                        builder.buffer.set_dot(br + 2, bc + 2, True)
                else: # AI: Solid 2x2 or X
                    builder.buffer.set_dot(br + 1, bc + 1, True)
                    builder.buffer.set_dot(br + 1, bc + 3, True)
                    builder.buffer.set_dot(br + 3, bc + 1, True)
                    builder.buffer.set_dot(br + 3, bc + 3, True)
                    if p == 4: # King: center dot
                        builder.buffer.set_dot(br + 2, bc + 2, True)

        # Selection
        if self.selected_piece:
            sr, sc = self.selected_piece
            builder.draw_rectangle(top + sr*cell_size, left + sc*cell_size, top + sr*cell_size + 4, left + sc*cell_size + 4)
            
        # Cursor
        if not self.winner:
            cr, cc = self.sel_row, self.sel_col
            # Underline the current cell
            builder.draw_line(top + cr*cell_size + 4, left + cc*cell_size, 5)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows
        
        if self.winner:
            send_status(pad, f"{self.winner} WINS! F3 MENU")
        elif self.selected_piece:
            send_status(pad, "SELECT TARGET F2")
        else:
            send_status(pad, "PAN MOVE F2 SELECT")
import random
