"""Backgammon game logic and DotPad rendering."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

import dotpad as dp
from .utils import send_status

# Point column layout constants (see _point_col)
_POINT_WIDTH = 4   # dots wide per point
_BAR_COL = 26      # leftmost column of the bar area
_LEFT_START = 2    # leftmost column of point 13 / point 12


@dataclass
class Backgammon:
    """Standard backgammon: player=white (24→1), AI=black (1→24)."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset to standard starting position."""
        # points[1..24]: positive = white pieces, negative = black pieces
        self.points: list[int] = [0] * 26
        self.points[24] = 2
        self.points[13] = 5
        self.points[8] = 3
        self.points[6] = 5
        self.points[1] = -2
        self.points[12] = -5
        self.points[17] = -3
        self.points[19] = -5

        self.bar_white: int = 0
        self.bar_black: int = 0
        self.borne_white: int = 0
        self.borne_black: int = 0

        self.turn: str = "player"         # "player" or "ai"
        self.phase: str = "select_src"    # "select_src" or "select_dst"
        self.remaining_dice: list[int] = self._roll_dice()

        # Source/dest cycling state
        self._src_list: list[int] = []    # valid source points
        self._src_idx: int = 0
        self._dst_list: list[tuple[int, int]] = []   # (dst_point, die_value)
        self._dst_idx: int = 0
        self._selected_src: Optional[int] = None
        self._status_msg: str = ""

        self.winner: Optional[str] = None
        self._last_rows: list[bytes] | None = None
        self._update_sources()

    # ------------------------------------------------------------------
    # Dice
    # ------------------------------------------------------------------

    @staticmethod
    def _roll_dice() -> list[int]:
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        return [d1, d2, d1, d2] if d1 == d2 else [d1, d2]

    # ------------------------------------------------------------------
    # Legal move generation (player = white, moves 24 → 1)
    # ------------------------------------------------------------------

    def _all_white_in_home(self) -> bool:
        return self.bar_white == 0 and all(
            self.points[p] <= 0 for p in range(7, 25)
        )

    def _legal_player_moves_for_die(self, die: int) -> list[tuple[int, int]]:
        """Return (src_point, dst_point) pairs for a single die value.

        src_point 25 means the bar; dst_point 0 means bearing off.
        """
        moves: list[tuple[int, int]] = []
        if self.bar_white > 0:
            entry = 25 - die   # e.g. die=1 → enter at point 24
            if 1 <= entry <= 24 and self.points[entry] >= -1:
                moves.append((25, entry))
            return moves

        bearing_off = self._all_white_in_home()
        for p in range(1, 25):
            if self.points[p] <= 0:
                continue
            dst = p - die
            if dst >= 1:
                if self.points[dst] >= -1:   # empty, own, or single black (hit)
                    moves.append((p, dst))
            elif bearing_off:
                if dst == 0:
                    moves.append((p, 0))
                elif dst < 0 and not any(self.points[q] > 0 for q in range(p + 1, 7)):
                    moves.append((p, 0))
        return moves

    def _legal_player_moves(self) -> list[tuple[int, int, int]]:
        """Return (src, dst, die) for all legal player moves given remaining dice."""
        moves: list[tuple[int, int, int]] = []
        seen: set[int] = set()
        for die in self.remaining_dice:
            if die in seen:
                continue
            seen.add(die)
            for src, dst in self._legal_player_moves_for_die(die):
                moves.append((src, dst, die))
        return moves

    # ------------------------------------------------------------------
    # Legal move generation (AI = black, moves 1 → 24)
    # ------------------------------------------------------------------

    def _all_black_in_home(self) -> bool:
        return self.bar_black == 0 and all(
            self.points[p] >= 0 for p in range(1, 19)
        )

    def _legal_ai_moves_for_die(self, die: int) -> list[tuple[int, int]]:
        moves: list[tuple[int, int]] = []
        if self.bar_black > 0:
            entry = die   # enter at point die (1-6)
            if 1 <= entry <= 6 and self.points[entry] <= 1:
                moves.append((0, entry))
            return moves

        bearing_off = self._all_black_in_home()
        for p in range(1, 25):
            if self.points[p] >= 0:
                continue
            dst = p + die
            if dst <= 24:
                if self.points[dst] <= 1:    # empty, own black, or single white (hit)
                    moves.append((p, dst))
            elif bearing_off:
                if dst == 25:
                    moves.append((p, 25))
                elif dst > 25 and not any(self.points[q] < 0 for q in range(p + 1, 25)):
                    moves.append((p, 25))
        return moves

    def _legal_ai_moves(self) -> list[tuple[int, int, int]]:
        moves: list[tuple[int, int, int]] = []
        seen: set[int] = set()
        for die in self.remaining_dice:
            if die in seen:
                continue
            seen.add(die)
            for src, dst in self._legal_ai_moves_for_die(die):
                moves.append((src, dst, die))
        return moves

    # ------------------------------------------------------------------
    # Execute moves
    # ------------------------------------------------------------------

    def _execute_player_move(self, src: int, dst: int, die: int) -> None:
        """Apply one player move and remove the used die."""
        if src == 25:
            self.bar_white -= 1
        else:
            self.points[src] -= 1
        if dst == 0:
            self.borne_white += 1
        else:
            if self.points[dst] == -1:   # hit a black blot
                self.points[dst] = 0
                self.bar_black += 1
            self.points[dst] += 1
        self.remaining_dice.remove(die)

    def _execute_ai_move(self, src: int, dst: int, die: int) -> None:
        if src == 0:
            self.bar_black -= 1
        else:
            self.points[src] += 1   # remove black piece (add 1 since it's negative)
        if dst == 25:
            self.borne_black += 1
        else:
            if self.points[dst] == 1:   # hit a white blot
                self.points[dst] = 0
                self.bar_white += 1
            self.points[dst] -= 1
        self.remaining_dice.remove(die)

    # ------------------------------------------------------------------
    # Turn management
    # ------------------------------------------------------------------

    def _check_winner(self) -> None:
        if self.borne_white >= 15:
            self.winner = "player"
        elif self.borne_black >= 15:
            self.winner = "ai"

    def _update_sources(self) -> None:
        """Rebuild the cycling list of valid source points for the player."""
        moves = self._legal_player_moves()
        if not moves:
            self._src_list = []
            self._src_idx = 0
            self._selected_src = None
            self._status_msg = "NO MOVES PASS"
            return
        seen: dict[int, bool] = {}
        for m in moves:
            seen[m[0]] = True
        self._src_list = list(seen.keys())
        self._src_idx = 0
        self._selected_src = None
        self.phase = "select_src"
        self._status_msg = ""

    def _update_dests(self, src: int) -> None:
        """Rebuild the cycling list of valid destinations from src."""
        moves = self._legal_player_moves()
        dst_set: dict[int, int] = {}
        for s, d, die in moves:
            if s == src and d not in dst_set:
                dst_set[d] = die
        self._dst_list = list(dst_set.items())   # [(dst_point, die_value), ...]
        self._dst_idx = 0
        self.phase = "select_dst"

    # ------------------------------------------------------------------
    # Game API
    # ------------------------------------------------------------------

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names pressed.
        """
        if self.winner or self.turn != "player":
            return

        if self.phase == "select_src":
            if not self._src_list:
                return
            if "panLeft" in names or "f1" in names:
                self._src_idx = (self._src_idx - 1) % len(self._src_list)
            if "panRight" in names or "f4" in names:
                self._src_idx = (self._src_idx + 1) % len(self._src_list)
            if "f2" in names:
                self._selected_src = self._src_list[self._src_idx]
                self._update_dests(self._selected_src)

        elif self.phase == "select_dst":
            if not self._dst_list:
                return
            if "panLeft" in names or "f1" in names:
                self._dst_idx = (self._dst_idx - 1) % len(self._dst_list)
            if "panRight" in names or "f4" in names:
                self._dst_idx = (self._dst_idx + 1) % len(self._dst_list)
            if "f2" in names:
                dst_point, die = self._dst_list[self._dst_idx]
                self._execute_player_move(self._selected_src, dst_point, die)
                self._check_winner()
                if not self.winner:
                    self._update_sources()
                    if not self._src_list:
                        # No more moves; hand off to AI
                        self.turn = "ai"
                        self.phase = "select_src"
                        self._status_msg = "AI TURN"

    def run_ai_turn(self) -> bool:
        """Run the AI turn: roll dice and play random legal moves.

        Returns:
            True if the AI took a turn.
        """
        if self.winner is not None or self.turn != "ai":
            return False

        self.remaining_dice = self._roll_dice()
        while self.remaining_dice:
            moves = self._legal_ai_moves()
            if not moves:
                break
            src, dst, die = random.choice(moves)
            self._execute_ai_move(src, dst, die)
            self._check_winner()
            if self.winner:
                return True

        # Hand back to player
        self.turn = "player"
        self.remaining_dice = self._roll_dice()
        self._update_sources()
        return True

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _point_col(self, point: int) -> int:
        """Return leftmost dot column for a board point (1-24) or bar (0/25)."""
        if point in (0, 25):
            return _BAR_COL
        if 13 <= point <= 18:
            return _LEFT_START + (point - 13) * _POINT_WIDTH
        if 19 <= point <= 24:
            return _BAR_COL + _POINT_WIDTH + (point - 19) * _POINT_WIDTH
        if 7 <= point <= 12:
            return _LEFT_START + (12 - point) * _POINT_WIDTH
        # 1-6
        return _BAR_COL + _POINT_WIDTH + (6 - point) * _POINT_WIDTH

    def _draw_checker(
        self,
        builder: dp.DotPadBuilder,
        base_row: int,
        col: int,
        is_white: bool,
    ) -> None:
        """Draw a single checker (2 rows tall, 3 dots wide)."""
        if is_white:
            builder.draw_rectangle(base_row, col, base_row + 1, col + 2)
        else:
            builder.draw_line(base_row, col, 3)
            builder.draw_line(base_row + 1, col, 3)

    def _draw_stack(
        self,
        builder: dp.DotPadBuilder,
        point: int,
        count: int,
        is_top: bool,
    ) -> None:
        """Draw a stack of checkers at a given point."""
        col = self._point_col(point)
        n = min(abs(count), 9)
        is_white = count > 0
        for i in range(n):
            base_row = (1 + i * 2) if is_top else (39 - i * 2 - 1)
            self._draw_checker(builder, base_row, col, is_white)
        # Show numeric overflow for large stacks
        if abs(count) > 9:
            label_row = 1 if is_top else 37
            builder.render_text(str(abs(count)), label_row, col, use_number_sign=False)

    def render(self, pad: dp.DotPad) -> None:
        """Render the board to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        # Horizontal dividing lines between top/bar/bottom areas
        builder.draw_line(19, 0, 60)
        builder.draw_line(21, 0, 60)

        # Vertical bar separator lines
        builder.draw_vline(0, _BAR_COL - 1, 40)
        builder.draw_vline(0, _BAR_COL + _POINT_WIDTH, 40)

        # Draw pieces on points
        for p in range(1, 25):
            count = self.points[p]
            if count == 0:
                continue
            is_top = p >= 13
            self._draw_stack(builder, p, count, is_top)

        # Bar checkers
        if self.bar_white > 0:
            builder.render_text(
                f"W{self.bar_white}", 19, _BAR_COL, use_number_sign=False
            )
        if self.bar_black > 0:
            builder.render_text(
                f"B{self.bar_black}", 22, _BAR_COL, use_number_sign=False
            )

        # Cursor/selection indicators
        if self.turn == "player" and not self.winner:
            if self.phase == "select_src" and self._src_list:
                cur_src = self._src_list[self._src_idx]
                col = self._point_col(cur_src)
                builder.draw_line(20, col, _POINT_WIDTH)
            elif self.phase == "select_dst" and self._dst_list:
                # Highlight selected source
                assert self._selected_src is not None
                src_col = self._point_col(self._selected_src)
                builder.draw_line(20, src_col, _POINT_WIDTH)
                # Mark current destination
                dst_point, _ = self._dst_list[self._dst_idx]
                dst_col = self._point_col(dst_point)
                builder.draw_line(20, dst_col, _POINT_WIDTH)
                builder.draw_line(19, dst_col, _POINT_WIDTH)

        rows = builder.rows()
        if self._last_rows is None:
            for i, row_bytes in enumerate(rows, start=1):
                pad.send_display_line(i, row_bytes)
        else:
            for i, row_bytes in enumerate(rows, start=1):
                if row_bytes != self._last_rows[i - 1]:
                    pad.send_display_line(i, row_bytes)
        self._last_rows = rows

        # Status line
        if self.winner == "player":
            send_status(pad, "YOU WIN F3 MENU")
        elif self.winner == "ai":
            send_status(pad, "YOU LOSE F3 MENU")
        else:
            dice_str = ",".join(str(d) for d in self.remaining_dice)
            if self.turn == "player":
                if self.phase == "select_src":
                    send_status(pad, f"DICE:{dice_str} PAN F2 SRC")
                else:
                    send_status(pad, f"DICE:{dice_str} PAN F2 DST")
            else:
                send_status(pad, "AI THINKING...")
