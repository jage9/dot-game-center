"""Backgammon game for Dot Game Center.

Rules:
- Standard backgammon (no doubling cube).
- Player = white, moves from point 24 down to point 1, bears off from points 1-6.
- AI = black, moves from point 1 up to point 24, bears off from points 19-24.
- Forced hits: landing on a single enemy checker sends it to the bar.
- Bar entry must happen before other moves.
- Bearing off once all checkers are in the home board.
- Win: first to bear off all 15 checkers.
- AI: greedy move selection minimizing own pip count.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status
from .helpers import send_diff

# Board conventions:
# self.points[i] = count at point index i (point number = i+1).
# Positive = player (white), negative = AI (black).
# Player moves: high index → low index (24→1), bears off from indices 0-5.
# AI moves: low index → high index (1→24), bears off from indices 18-23.

# Display layout on 60×40 dots:
# 12 points per row × 5 dots each = 60 (uses full width).
# Top row points 24-13 (indices 23-12), bottom row points 1-12 (indices 0-11).
# Bar: visual separator at dots column 28-32 (between 6th and 7th point of each half).
# Piece height: top points stack down from row 3; bottom points stack up from row 38.

_PT_W = 5          # dots wide per point display column
_TOP_PIECE_ROW = 3  # first dot row for pieces on top half
_BOT_PIECE_ROW = 38  # last dot row for pieces on bottom half
_BAR_LEFT = 28      # left dot column of bar separator
_BAR_RIGHT = 32     # right dot column of bar separator


def _pt_left_col(pt_idx: int) -> int:
    """Return the left dot column for a point (0-11 within its half)."""
    half_idx = pt_idx % 12  # 0-11 within top/bottom half
    if half_idx <= 5:
        # Left group of 6: cols 1-30
        return 1 + half_idx * _PT_W
    else:
        # Right group of 6: cols 33-57 (skip bar at 28-32)
        return _BAR_RIGHT + 1 + (half_idx - 6) * _PT_W


def _pt_is_top(pt_idx: int) -> bool:
    return pt_idx >= 12   # top row = indices 12-23


def _init_points() -> list[int]:
    """Return the standard starting checker positions."""
    pts = [0] * 24
    pts[23] = 2     # player on point 24
    pts[12] = 5     # player on point 13
    pts[7] = 3      # player on point 8
    pts[5] = 5      # player on point 6
    pts[0] = -2     # AI on point 1
    pts[11] = -5    # AI on point 12
    pts[16] = -3    # AI on point 17
    pts[18] = -5    # AI on point 19
    return pts


@dataclass
class Backgammon:
    """Backgammon game vs AI with greedy pip-count minimisation."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to starting position."""
        self.points: list[int] = _init_points()
        self.bar: list[int] = [0, 0]          # [player_bar, ai_bar]
        self.borne_off: list[int] = [0, 0]    # [player_off, ai_off]
        self.turn: int = 1                     # 1=player, 2=ai
        self.phase: str = "roll"               # "roll" | "move"
        self.dice: list[int] = []
        self.sel_row: int = 1   # 0=top half, 1=bottom half
        self.sel_col: int = 0   # 0-11 column within the half
        self.selected: Optional[int] = None    # selected source point index
        self.winner: Optional[str] = None
        self._last_rows: Optional[list[bytes]] = None
        self._status_msg: str = "F2 ROLL DICE"

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _pip_count(self, player: int) -> int:
        """Return the pip count for player (1 or 2)."""
        total = 0
        if player == 1:
            for i in range(24):
                if self.points[i] > 0:
                    total += self.points[i] * (i + 1)
            total += self.bar[0] * 25
        else:
            for i in range(24):
                if self.points[i] < 0:
                    total += (-self.points[i]) * (24 - i)
            total += self.bar[1] * 25
        return total

    def _all_home(self, player: int) -> bool:
        """Return True if all checkers are in the home board."""
        if player == 1:
            if self.bar[0] > 0:
                return False
            for i in range(6, 24):
                if self.points[i] > 0:
                    return False
        else:
            if self.bar[1] > 0:
                return False
            for i in range(0, 18):
                if self.points[i] < 0:
                    return False
        return True

    # ------------------------------------------------------------------
    # Move generation (one die at a time)
    # ------------------------------------------------------------------

    def _legal_moves_for_die(self, die: int, player: int) -> list[tuple[int, int]]:
        """Return legal (from_idx, to_idx) moves for one die value.

        from_idx = -1 means "from bar".
        to_idx = -1 (player) or 24 (AI) means "bear off".
        """
        moves: list[tuple[int, int]] = []
        if player == 1:
            self._gen_player_moves(die, moves)
        else:
            self._gen_ai_moves(die, moves)
        return moves

    def _gen_player_moves(self, die: int, moves: list) -> None:
        """Generate player (white) moves for one die."""
        if self.bar[0] > 0:
            # Must enter: target = 24 - die (point index)
            to_idx = 24 - die
            if 0 <= to_idx < 24 and self.points[to_idx] >= -1:
                moves.append((-1, to_idx))
            return
        home = self._all_home(1)
        for i in range(23, -1, -1):
            if self.points[i] <= 0:
                continue
            to_idx = i - die
            if to_idx >= 0:
                if self.points[to_idx] >= -1:
                    moves.append((i, to_idx))
            elif home:
                # Bearing off
                # Exact bear-off: point number == die
                if i + 1 == die:
                    moves.append((i, -1))
                # Higher die: can use if no checker on a higher home point
                elif i + 1 < die:
                    highest = max(
                        (j for j in range(6) if self.points[j] > 0),
                        default=-1
                    )
                    if highest == i:
                        moves.append((i, -1))

    def _gen_ai_moves(self, die: int, moves: list) -> None:
        """Generate AI (black) moves for one die."""
        if self.bar[1] > 0:
            to_idx = die - 1
            if 0 <= to_idx < 24 and self.points[to_idx] <= 1:
                moves.append((-1, to_idx))
            return
        home = self._all_home(2)
        for i in range(24):
            if self.points[i] >= 0:
                continue
            to_idx = i + die
            if to_idx < 24:
                if self.points[to_idx] <= 1:
                    moves.append((i, to_idx))
            elif home:
                if 24 - i == die:
                    moves.append((i, 24))
                elif 24 - i < die:
                    lowest = min(
                        (j for j in range(18, 24) if self.points[j] < 0),
                        default=25
                    )
                    if lowest == i:
                        moves.append((i, 24))

    def _apply_move(self, mv: tuple[int, int], player: int) -> None:
        """Apply a single (from_idx, to_idx) move in-place."""
        from_idx, to_idx = mv
        if player == 1:
            sign = 1
            bar_idx = 0
            enemy_sign = -1
            enemy_bar_idx = 1
        else:
            sign = -1
            bar_idx = 1
            enemy_sign = 1
            enemy_bar_idx = 0

        # Remove from source
        if from_idx == -1:
            self.bar[bar_idx] -= 1
        else:
            self.points[from_idx] -= sign

        # Place at destination
        if to_idx == -1 or to_idx == 24:
            self.borne_off[bar_idx] += 1
        else:
            # Hit single enemy checker
            if self.points[to_idx] == enemy_sign:
                self.points[to_idx] = 0
                self.bar[enemy_bar_idx] += 1
            self.points[to_idx] += sign

    def _check_win(self) -> None:
        if self.borne_off[0] == 15:
            self.winner = "player"
        elif self.borne_off[1] == 15:
            self.winner = "cpu"

    # ------------------------------------------------------------------
    # Player turn management
    # ------------------------------------------------------------------

    def _roll_dice(self) -> list[int]:
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        return [d1, d1, d1, d1] if d1 == d2 else [d1, d2]

    def _any_moves_left(self) -> bool:
        for d in set(self.dice):
            if self._legal_moves_for_die(d, 1):
                return True
        return False

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        F2 rolls dice (roll phase) or selects/confirms moves (move phase).
        F3 cancels current selection.
        F1/F4 switch between top/bottom row. panLeft/panRight move column.

        Args:
            names: List of key names.
        """
        if self.winner or self.turn != 1:
            return

        if "panLeft" in names:
            self.sel_col = max(0, self.sel_col - 1)
        if "panRight" in names:
            self.sel_col = min(11, self.sel_col + 1)
        if "f1" in names:
            self.sel_row = 0
        if "f4" in names:
            self.sel_row = 1

        if "f3" in names:
            self.selected = None
            if self.phase == "move":
                self._status_msg = "F2 SELECT PIECE"

        if "f2" in names:
            if self.phase == "roll":
                self._do_roll()
            else:
                self._do_move_action()

    def _sel_point_idx(self) -> int:
        """Convert (sel_row, sel_col) display position to point index (0-23)."""
        if self.sel_row == 0:
            # Top row: col 0 → point index 23, col 11 → point index 12
            return 23 - self.sel_col
        else:
            # Bottom row: col 0 → point index 0, col 11 → point index 11
            return self.sel_col

    def _do_roll(self) -> None:
        self.dice = self._roll_dice()
        self.phase = "move"
        self.selected = None
        doubles = len(self.dice) == 4
        dice_str = f"{self.dice[0]}+{self.dice[1]}"
        if doubles:
            dice_str += " DBL"
        self._status_msg = f"DICE:{dice_str} F2 MOVE"[:20]
        if not self._any_moves_left():
            self._status_msg = "NO MOVES PASS"
            self._end_player_turn()

    def _do_move_action(self) -> None:
        if self.selected is None:
            self._try_select_source()
        else:
            self._try_confirm_dest()

    def _try_select_source(self) -> None:
        """Try to select the source point at the cursor."""
        if self.bar[0] > 0:
            # Must use bar
            has_any = any(self._legal_moves_for_die(d, 1) for d in set(self.dice))
            if has_any:
                self.selected = -1
                self._status_msg = "BAR SELECT DEST"
            return
        pt = self._sel_point_idx()
        if self.points[pt] <= 0:
            self._status_msg = "NO PIECE HERE"
            return
        # Check if any die can move from here
        has_move = any(
            any(mv[0] == pt for mv in self._legal_moves_for_die(d, 1))
            for d in set(self.dice)
        )
        if has_move:
            self.selected = pt
            self._status_msg = f"PT{pt+1} SEL.F2 DEST"[:20]
        else:
            self._status_msg = "NO MOVES HERE"

    def _try_confirm_dest(self) -> None:
        """Try to move selected piece to cursor position."""
        src = self.selected
        pt = self._sel_point_idx()

        # Check bear-off trigger: if cursor is at rightmost area (col 11, bottom), treat as bear-off
        bear_off_target = -1

        for d in sorted(set(self.dice)):
            for mv in self._legal_moves_for_die(d, 1):
                if mv[0] != src:
                    continue
                dest = mv[1]
                # Match destination point or bear-off
                if dest == pt or (dest == -1 and self.sel_col == 11):
                    self._apply_move(mv, 1)
                    self.dice.remove(d)
                    self.selected = None
                    self._check_win()
                    if self.winner:
                        return
                    if not self.dice or not self._any_moves_left():
                        self._status_msg = "DONE"
                        self._end_player_turn()
                    else:
                        dice_str = "+".join(str(x) for x in self.dice)
                        self._status_msg = f"DICE:{dice_str} F2 MOVE"[:20]
                    return
        # Re-select different piece?
        if self.points[pt] > 0 and pt != src:
            self.selected = None
            self._try_select_source()
            return
        self._status_msg = "INVALID MOVE"

    def _end_player_turn(self) -> None:
        self.phase = "roll"
        self.dice = []
        self.selected = None
        self.turn = 2

    # ------------------------------------------------------------------
    # AI (greedy per-die, minimises own pip count)
    # ------------------------------------------------------------------

    def run_ai_turn(self) -> bool:
        """Run one AI turn. Return True if turn was played."""
        if self.winner is not None or self.turn != 2:
            return False
        dice = self._roll_dice()
        unique_dice = sorted(set(dice), reverse=True)
        remaining = dice[:]
        for _ in range(len(dice)):
            best_mv: Optional[tuple[int, int]] = None
            best_die: int = 0
            best_pip = self._pip_count(2)
            for d in sorted(set(remaining), reverse=True):
                for mv in self._legal_moves_for_die(d, 2):
                    # Evaluate move
                    self._apply_move(mv, 2)
                    pip = self._pip_count(2)
                    self._undo_move(mv, 2)
                    if pip < best_pip:
                        best_pip = pip
                        best_mv = mv
                        best_die = d
                    elif pip == best_pip and best_mv is None:
                        best_mv = mv
                        best_die = d
            if best_mv is None:
                break
            self._apply_move(best_mv, 2)
            remaining.remove(best_die)
            self._check_win()
            if self.winner:
                return True
        self.turn = 1
        self.phase = "roll"
        self._status_msg = "F2 ROLL DICE"
        return True

    def _undo_move(self, mv: tuple[int, int], player: int) -> None:
        """Undo a move that didn't hit (for pip evaluation only)."""
        from_idx, to_idx = mv
        if player == 1:
            sign = 1
            bar_idx = 0
        else:
            sign = -1
            bar_idx = 1

        if to_idx == -1 or to_idx == 24:
            self.borne_off[bar_idx] -= 1
        else:
            self.points[to_idx] -= sign

        if from_idx == -1:
            self.bar[bar_idx] += 1
        else:
            self.points[from_idx] += sign

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, pad: dp.DotPad) -> None:
        """Render the backgammon board to the DotPad.

        Args:
            pad: Active DotPad device instance.
        """
        builder = pad.builder()

        # Outer border
        builder.draw_rectangle(1, 1, 40, 60)
        # Bar vertical separators
        builder.draw_vline(1, _BAR_LEFT, 40)
        builder.draw_vline(1, _BAR_RIGHT, 40)
        # Middle horizontal separator (divides top/bottom halves)
        builder.draw_line(20, 1, _BAR_LEFT - 1)
        builder.draw_line(20, _BAR_RIGHT + 1, 60 - _BAR_RIGHT)
        builder.draw_line(21, 1, _BAR_LEFT - 1)
        builder.draw_line(21, _BAR_RIGHT + 1, 60 - _BAR_RIGHT)

        # Draw checker stacks
        for pt_idx in range(24):
            count = self.points[pt_idx]
            if count == 0:
                continue
            is_top = _pt_is_top(pt_idx)
            # For top row: display column is 23-pt_idx (0..11)
            # For bottom row: display column is pt_idx (0..11)
            disp_col = (23 - pt_idx) if is_top else pt_idx
            left = _pt_left_col(pt_idx)
            n = abs(count)
            is_player = count > 0
            for k in range(min(n, 8)):
                if is_top:
                    r = _TOP_PIECE_ROW + k * 2
                else:
                    r = _BOT_PIECE_ROW - k * 2
                # Player pieces: solid 3-dot line
                # AI pieces: two endpoint dots
                if is_player:
                    builder.draw_line(r, left + 1, 3)
                else:
                    builder.draw_line(r, left + 1, 1)
                    builder.draw_line(r, left + 3, 1)
            # Show overflow count as text if more than 8
            if n > 8:
                if is_top:
                    tr = _TOP_PIECE_ROW + 8 * 2
                else:
                    tr = _BOT_PIECE_ROW - 8 * 2
                builder.render_text(str(n), row=tr, col=left + 1, use_number_sign=False)

        # Draw bar checkers
        bar_c = _BAR_LEFT + 1
        for k in range(min(self.bar[0], 4)):
            r = 18 - k * 2
            builder.draw_line(r, bar_c, 3)
        for k in range(min(self.bar[1], 4)):
            r = 23 + k * 2
            builder.draw_line(r, bar_c, 3)

        # Borne-off counters (displayed in bar area)
        if self.borne_off[0] > 0:
            builder.render_text(str(self.borne_off[0]), row=6, col=bar_c, use_number_sign=False)
        if self.borne_off[1] > 0:
            builder.render_text(str(self.borne_off[1]), row=35, col=bar_c, use_number_sign=False)

        # Cursor indicator during player's move phase
        if self.winner is None and self.turn == 1 and self.phase == "move":
            pt = self._sel_point_idx()
            is_top = _pt_is_top(pt)
            left = _pt_left_col(pt)
            if is_top:
                cr = _TOP_PIECE_ROW - 1
            else:
                cr = _BOT_PIECE_ROW + 1
            # Clamp to valid range
            cr = max(1, min(40, cr))
            builder.draw_line(cr, left, _PT_W)

        self._last_rows = send_diff(pad, builder, self._last_rows)
        send_status(pad, self._status_msg[:20])
