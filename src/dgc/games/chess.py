"""Chess game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, List, Tuple

import dotpad as dp
from .utils import send_status


@dataclass
class Chess:
    """Simple Chess with braille letter pieces."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the board to standard chess starting position."""
        # Row 0: Black pieces (uppercase), Row 7: White pieces (lowercase)
        self.board = [["" for _ in range(8)] for _ in range(8)]
        
        # Black
        self.board[0] = ["R", "N", "B", "Q", "K", "B", "N", "R"]
        self.board[1] = ["P"] * 8
        
        # White
        self.board[7] = ["r", "n", "b", "q", "k", "b", "n", "r"]
        self.board[6] = ["p"] * 8
        
        self.sel_row = 7
        self.sel_col = 4
        self.selected_piece: Optional[Tuple[int, int]] = None
        self.valid_moves: List[Tuple[int, int]] = []
        self.turn = "white"
        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        if self.winner or self.turn == "black": # AI is black
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
                self.turn = "black"
            else:
                # Change selection if clicked on another white piece
                if piece != "" and piece.islower():
                    self.selected_piece = target
                    self.valid_moves = self._get_valid_moves(target)
                else:
                    self.selected_piece = None
                    self.valid_moves = []
        else:
            if piece != "" and piece.islower():
                self.selected_piece = target
                self.valid_moves = self._get_valid_moves(target)

    def _get_valid_moves(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        r, c = pos
        piece = self.board[r][c]
        if piece == "": return []
        
        moves = []
        is_white = piece.islower()
        p_type = piece.lower()
        
        # Simplified move validation
        if p_type == "p": # Pawn
            direction = -1 if is_white else 1
            # Forward
            if 0 <= r + direction < 8 and self.board[r + direction][c] == "":
                moves.append((r + direction, c))
            # Captures
            for dc in [-1, 1]:
                nc = c + dc
                nr = r + direction
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target != "" and target.islower() != is_white:
                        moves.append((nr, nc))
        elif p_type == "r": # Rook
            moves.extend(self._get_line_moves(r, c, [(0,1), (0,-1), (1,0), (-1,0)], is_white))
        elif p_type == "b": # Bishop
            moves.extend(self._get_line_moves(r, c, [(1,1), (1,-1), (-1,1), (-1,-1)], is_white))
        elif p_type == "n": # Knight
            for dr, dc in [(2,1), (2,-1), (-2,1), (-2,-1), (1,2), (1,-2), (-1,2), (-1,-2)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if self.board[nr][nc] == "" or self.board[nr][nc].islower() != is_white:
                        moves.append((nr, nc))
        elif p_type == "q": # Queen
            moves.extend(self._get_line_moves(r, c, [(0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)], is_white))
        elif p_type == "k": # King
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        if self.board[nr][nc] == "" or self.board[nr][nc].islower() != is_white:
                            moves.append((nr, nc))
        return moves

    def _get_line_moves(self, r, c, directions, is_white):
        moves = []
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                if self.board[nr][nc] == "":
                    moves.append((nr, nc))
                else:
                    if self.board[nr][nc].islower() != is_white:
                        moves.append((nr, nc))
                    break
                nr += dr
                nc += dc
        return moves

    def _make_move(self, start, end):
        sr, sc = start
        er, ec = end
        captured = self.board[er][ec]
        self.board[er][ec] = self.board[sr][sc]
        self.board[sr][sc] = ""
        
        if captured.lower() == "k":
            self.winner = "White" if captured.isupper() else "Black"

    def run_ai_turn(self) -> bool:
        if self.turn != "black" or self.winner:
            return False
            
        # Very simple AI: random valid move
        all_moves = []
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != "" and piece.isupper():
                    moves = self._get_valid_moves((r, c))
                    for m in moves:
                        all_moves.append(((r, c), m))
        
        if all_moves:
            # Prioritize captures
            captures = [move for move in all_moves if self.board[move[1][0]][move[1][1]] != ""]
            if captures:
                move = random.choice(captures)
            else:
                move = random.choice(all_moves)
            self._make_move(move[0], move[1])
        
        self.turn = "white"
        return True

    def render(self, pad: dp.DotPad) -> None:
        builder = pad.builder()
        
        top = 1
        left = 8
        cell_w = 6
        cell_h = 4
        
        # Grid
        for i in range(9):
            builder.draw_vline(top, left + i * cell_w, 33)
            builder.draw_line(top + i * cell_h, left, 49)
            
        # Pieces
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece == "": continue
                
                # Render braille letter
                builder.render_text(
                    piece,
                    row = top + r*cell_h + 1,
                    col = left + c*cell_w + 2,
                    use_number_sign=False,
                    use_capital_sign=False
                )
        
        # Selection / Cursor
        if not self.winner:
            # Underline current cursor
            builder.draw_line(top + (self.sel_row+1)*cell_h - 1, left + self.sel_col*cell_w + 1, 4)
            
            if self.selected_piece:
                sr, sc = self.selected_piece
                # Small mark in top-left of selected cell
                builder.buffer.set_dot(top + sr*cell_h + 1, left + sc*cell_w + 1, True)

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
        else:
            send_status(pad, f"{self.turn.upper()} TURN")
