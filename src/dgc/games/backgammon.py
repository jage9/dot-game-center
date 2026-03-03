"""Backgammon game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, List, Tuple

import dotpad as dp
from .utils import send_status


@dataclass
class Backgammon:
    """Backgammon with tactile points, bar, and basic AI."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the board to standard backgammon setup."""
        # board[0..23] are the points. Positive for Player (0->23), Negative for AI (23->0).
        self.board = [0] * 24
        self.board[0] = 2
        self.board[5] = -5
        self.board[7] = -3
        self.board[11] = 5
        self.board[12] = -5
        self.board[16] = 3
        self.board[18] = 5
        self.board[23] = -2
        
        self.bar = [0, 0] # [Player, AI]
        self.home = [0, 0] # [Player, AI]
        
        self.dice = []
        self.sel_point = 0
        self.selected_point: Optional[int] = None # -1 for bar, 0-23 for board
        self.turn = "player"
        self.winner: Optional[str] = None
        self.phase = "roll"
        self._last_rows: list[bytes] | None = None

    def handle_key(self, names: list[str]) -> None:
        if self.winner or self.turn == "ai":
            return
            
        if "panLeft" in names: self.sel_point = (self.sel_point - 1) % 24
        if "panRight" in names: self.sel_point = (self.sel_point + 1) % 24
        if "f1" in names or "f4" in names:
            # Jump between top and bottom
            self.sel_point = 23 - self.sel_point
            
        if "f2" in names:
            if self.phase == "roll":
                self._roll_dice()
            elif self.phase == "move":
                self._handle_move()

    def _roll_dice(self):
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        if d1 == d2:
            self.dice = [d1] * 4
        else:
            self.dice = [d1, d2]
        self.phase = "move"
        if not self._get_all_valid_moves("player"):
            self._end_turn()

    def _handle_move(self):
        # Must move from bar first
        if self.bar[0] > 0:
            if self.selected_point is None:
                self.selected_point = -1 # Select bar
                return
        
        if self.selected_point is None:
            if self.board[self.sel_point] > 0:
                self.selected_point = self.sel_point
        else:
            # Try move to sel_point or home
            # Special case: 'home' move if sel_point is same as selection
            # (or if we add a dedicated button, but let's use sel_point for now)
            if self._try_move(self.selected_point, self.sel_point, "player"):
                self.selected_point = None
                if not self.dice or not self._get_all_valid_moves("player"):
                    self._end_turn()
            else:
                # Toggle selection
                if self.bar[0] == 0 and self.board[self.sel_point] > 0:
                    self.selected_point = self.sel_point
                else:
                    self.selected_point = None

    @staticmethod
    def _move_distance(start: int, end: int, player: str) -> int:
        """Return die distance for a proposed move."""
        if player == "player":
            return end + 1 if start == -1 else end - start
        return 24 - end if start == -1 else start - end

    def _try_move(self, start: int, end: int, player: str) -> bool:
        """Attempt to move a piece. player is 'player' or 'ai'."""
        # Validate source checker.
        if start == -1:
            if player == "player" and self.bar[0] <= 0:
                return False
            if player == "ai" and self.bar[1] <= 0:
                return False
        else:
            if not (0 <= start < 24):
                return False
            if player == "player" and self.board[start] <= 0:
                return False
            if player == "ai" and self.board[start] >= 0:
                return False

        dist = self._move_distance(start, end, player)
                
        if dist not in self.dice:
            # Check for bearing off
            if start != -1 and self._can_bear_off(player) and end == start: # Simple home move
                # Find largest die >= required distance
                req = (24 - start) if player == "player" else (start + 1)
                best_die = -1
                for d in self.dice:
                    if d >= req:
                        if best_die == -1 or d < best_die: best_die = d
                if best_die != -1:
                    self.board[start] -= 1 if player == "player" else -1
                    self.home[0 if player == "player" else 1] += 1
                    self.dice.remove(best_die)
                    return True
            return False
            
        # Target validation
        if not (0 <= end < 24):
            return False
        target = self.board[end]
        if player == "player":
            if target < -1: return False # Blocked
            if start != -1: self.board[start] -= 1
            else: self.bar[0] -= 1
            
            if target == -1: # Hit
                self.board[end] = 1
                self.bar[1] += 1
            else:
                self.board[end] += 1
        else: # AI
            if target > 1: return False # Blocked
            if start != -1: self.board[start] += 1
            else: self.bar[1] -= 1
            
            if target == 1: # Hit
                self.board[end] = -1
                self.bar[0] += 1
            else:
                self.board[end] -= 1
                
        self.dice.remove(dist)
        return True

    def _can_bear_off(self, player: str) -> bool:
        if player == "player":
            if self.bar[0] > 0: return False
            for i in range(18):
                if self.board[i] > 0: return False
        else:
            if self.bar[1] > 0: return False
            for i in range(6, 24):
                if self.board[i] < 0: return False
        return True

    def _get_all_valid_moves(self, player: str) -> List[Tuple[int, int]]:
        moves = []
        possible_starts = []
        if player == "player":
            if self.bar[0] > 0: possible_starts = [-1]
            else: possible_starts = [i for i, v in enumerate(self.board) if v > 0]
            
            for s in possible_starts:
                for d in set(self.dice):
                    target = (d - 1) if s == -1 else (s + d)
                    if 0 <= target < 24:
                        if self.board[target] >= -1: moves.append((s, target))
                    elif self._can_bear_off("player"):
                        moves.append((s, s)) # Represent home move as self-target
        else: # AI
            if self.bar[1] > 0: possible_starts = [-1]
            else: possible_starts = [i for i, v in enumerate(self.board) if v < 0]
            
            for s in possible_starts:
                for d in set(self.dice):
                    target = (24 - d) if s == -1 else (s - d)
                    if 0 <= target < 24:
                        if self.board[target] <= 1: moves.append((s, target))
                    elif self._can_bear_off("ai"):
                        moves.append((s, s))
        return moves

    def _end_turn(self):
        self._check_winner()
        if self.winner: return
        self.turn = "ai" if self.turn == "player" else "player"
        self.phase = "roll"
        self.dice = []
        self.selected_point = None

    def run_ai_turn(self) -> bool:
        if self.turn != "ai" or self.winner: return False
        
        # 1. Roll
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        self.dice = [d1] * 4 if d1 == d2 else [d1, d2]
        
        # 2. Move AI
        safety = 0
        while self.dice:
            safety += 1
            if safety > 64:
                break
            moves = self._get_all_valid_moves("ai")
            if not moves: break
            # Prioritize hits, then bearing off, then random
            hits = [m for m in moves if m[1] != m[0] and self.board[m[1]] == 1]
            home = [m for m in moves if m[0] == m[1]]
            
            if hits: move = random.choice(hits)
            elif home: move = random.choice(home)
            else: move = random.choice(moves)
            
            if not self._try_move(move[0], move[1], "ai"):
                # Keep AI from stalling forever on any unexpected invalid move.
                dist = self._move_distance(move[0], move[1], "ai")
                if dist in self.dice:
                    self.dice.remove(dist)
                elif self.dice:
                    self.dice.pop(0)
            
        self._end_turn()
        return True

    def _check_winner(self):
        if self.home[0] == 15: self.winner = "PLAYER"
        if self.home[1] == 15: self.winner = "AI"

    def render(self, pad: dp.DotPad) -> None:
        builder = pad.builder()
        
        # The Board: two halves of 6 points
        # Points: 11..0 (Bottom Right to Bottom Left), 12..23 (Top Left to Top Right)
        bar_col = 30 # Middle column for the bar
        
        # Draw Bar Line
        builder.draw_vline(1, bar_col, 40)
        builder.draw_vline(1, bar_col + 1, 40)
        
        for i in range(12):
            # Bottom (0..11)
            # 0..5 on right, 6..11 on left
            if i < 6: bx = 56 - i * 4
            else: bx = 26 - (i - 6) * 4
            
            count_b = self.board[i]
            self._draw_stack(builder, bx, 38, count_b, "up")
            
            # Top (12..23)
            # 12..17 on left, 18..23 on right
            if i < 6: tx = 6 + i * 4
            else: tx = 36 + (i - 6) * 4
            
            count_t = self.board[12 + i]
            self._draw_stack(builder, tx, 2, count_t, "down")

        # Draw pieces on the bar
        if self.bar[0] > 0: # Player on bar (White)
            self._draw_stack(builder, bar_col - 2, 20, self.bar[0], "up")
        if self.bar[1] > 0: # AI on bar (Black)
            self._draw_stack(builder, bar_col + 3, 20, -self.bar[1], "down")

        # Cursor
        cp = self.sel_point
        if cp < 12:
            if cp < 6: cx = 56 - cp * 4
            else: cx = 26 - (cp - 6) * 4
            builder.draw_line(39, cx, 2)
        else:
            ti = cp - 12
            if ti < 6: tx = 6 + ti * 4
            else: tx = 36 + (ti - 6) * 4
            builder.draw_line(1, tx, 2)

        # Selection indicator
        if self.selected_point is not None:
            if self.selected_point == -1:
                builder.render_text_dots("1", row=20, col=bar_col - 4)
            else:
                if self.selected_point < 12:
                    if self.selected_point < 6:
                        sx = 56 - self.selected_point * 4
                    else:
                        sx = 26 - (self.selected_point - 6) * 4
                    builder.render_text_dots("1", row=37, col=sx)
                else:
                    si = self.selected_point - 12
                    if si < 6:
                        sx = 6 + si * 4
                    else:
                        sx = 36 + (si - 6) * 4
                    builder.render_text_dots("1", row=3, col=sx)

        rows = builder.rows()
        sent_ok = True
        first_frame = self._last_rows is None
        if first_frame:
            for i, row_bytes in enumerate(rows, start=1):
                if not pad.send_display_line(i, row_bytes):
                    sent_ok = False
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    if not pad.send_display_line(i, row_bytes):
                        sent_ok = False
        if first_frame and not sent_ok:
            sent_ok = True
            for i, row_bytes in enumerate(rows, start=1):
                if not pad.send_display_line(i, row_bytes):
                    sent_ok = False
        if sent_ok:
            self._last_rows = rows
        
        if self.winner == "PLAYER":
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == "AI":
            send_status(pad, "YOU LOSE F3 MENU")
        elif self.phase == "roll":
            send_status(pad, "F2 TO ROLL")
        else:
            dice_str = " ".join(map(str, self.dice))
            status = f"DICE {dice_str} F2 MV"
            if self._can_bear_off("player"):
                status = f"DICE {dice_str} F2 HOME"
            send_status(pad, status)

    def _draw_stack(self, builder, x, start_y, count, direction):
        c = abs(count)
        for h in range(c):
            if direction == "up": r = start_y - h * 2
            else: r = start_y + h * 2
            
            if 1 <= r <= 40:
                builder.buffer.set_dot(r, x, True)
                builder.buffer.set_dot(r, x + 1, True)
                if count < 0: # AI pattern: diagonal slash
                    builder.buffer.set_dot(r + 1, x, True)
