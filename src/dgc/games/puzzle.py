"""15 Slide Puzzle game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status


@dataclass
class FifteenPuzzle:
    """15 Slide Puzzle with braille numbers."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset and shuffle the puzzle."""
        # 0 represents the empty space.
        self.board = list(range(1, 16)) + [0]
        self.sel_row = 3
        self.sel_col = 3
        self._shuffle()
        self.winner = False
        self._last_rows: list[bytes] | None = None

    def _shuffle(self) -> None:
        """Shuffle by making valid moves to ensure solvability."""
        empty_idx = 15
        for _ in range(200):
            r, c = empty_idx // 4, empty_idx % 4
            neighbors = []
            if r > 0: neighbors.append(empty_idx - 4)
            if r < 3: neighbors.append(empty_idx + 4)
            if c > 0: neighbors.append(empty_idx - 1)
            if c < 3: neighbors.append(empty_idx + 1)
            
            move_idx = random.choice(neighbors)
            self.board[empty_idx], self.board[move_idx] = self.board[move_idx], self.board[empty_idx]
            empty_idx = move_idx
        
        # Sync selection with empty space.
        self.sel_row = empty_idx // 4
        self.sel_col = empty_idx % 4

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs."""
        if self.winner:
            return
        
        moved = False
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % 4
            moved = True
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % 4
            moved = True
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % 4
            moved = True
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % 4
            moved = True
            
        if "f2" in names:
            self._move_tile()
            self._check_winner()

    def _move_tile(self) -> None:
        """Move selected tile if it's adjacent to the empty space."""
        # Find empty space.
        empty_idx = self.board.index(0)
        er, ec = empty_idx // 4, empty_idx % 4
        
        # Check if selected is adjacent to empty.
        if ((abs(self.sel_row - er) == 1 and self.sel_col == ec) or
            (abs(self.sel_col - ec) == 1 and self.sel_row == er)):
            idx = self.sel_row * 4 + self.sel_col
            self.board[empty_idx], self.board[idx] = self.board[idx], self.board[empty_idx]
            # Move selection to the new empty spot.
            self.sel_row, self.sel_col = er, ec

    def _check_winner(self) -> None:
        target = list(range(1, 16)) + [0]
        if self.board == target:
            self.winner = True

    def render(self, pad: dp.DotPad) -> None:
        builder = pad.builder()
        
        top = 2
        left = 10
        cell_w = 10
        cell_h = 9
        
        # Draw Grid
        for i in range(5):
            # Vertical lines
            builder.draw_vline(top, left + i * cell_w, cell_h * 4 + 1)
            # Horizontal lines
            builder.draw_line(top + i * cell_h, left, cell_w * 4 + 1)
            
        # Draw Tiles
        for r in range(4):
            for c in range(4):
                val = self.board[r * 4 + c]
                if val == 0:
                    continue
                
                # Render number in braille
                # Center it roughly in the 10x9 cell.
                # One braille char is 2x3 dots + gaps.
                text_row = top + r * cell_h + 3
                text_col = left + c * cell_w + (2 if val < 10 else 1)
                
                builder.render_text(
                    str(val),
                    row=text_row,
                    col=text_col,
                    use_number_sign=False, # Save space
                    use_nemeth=True,
                    use_capital_sign=False
                )
        
        # Selection Cursor (short line at bottom of cell)
        if not self.winner:
            cursor_row = top + (self.sel_row + 1) * cell_h - 2
            cursor_col = left + self.sel_col * cell_w + 2
            builder.draw_line(cursor_row, cursor_col, 7)
            
        rows = builder.rows()
        builder.send(pad)
        self._last_rows = rows
        
        if self.winner:
            send_status(pad, "SOLVED! F3 MENU")
        else:
            send_status(pad, "PAN/F1/F4 MOVE F2 SLIDE")
