"""Battleship game logic and DotPad rendering."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Optional

import dotpad as dp
from .utils import send_status


SHIP_SIZES = [5, 4, 3, 3, 2]
SHIP_NAMES = ["CARRIER", "BATTLESHIP", "CRUISER", "SUB", "DESTROYER"]


@dataclass
class Battleship:
    """Battleship with user placement and hunt/target AI."""

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset game state."""
        self.player_board = [[0 for _ in range(10)] for _ in range(10)]
        self.player_ship_ids = [[0 for _ in range(10)] for _ in range(10)]
        self.enemy_board = [[0 for _ in range(10)] for _ in range(10)]
        self.enemy_ship_ids = [[0 for _ in range(10)] for _ in range(10)]
        self.player_shots = [[0 for _ in range(10)] for _ in range(10)]
        self.enemy_shots = [[0 for _ in range(10)] for _ in range(10)]
        self.place_index = 0
        self.orientation = "H"
        self.sel_row = 0
        self.sel_col = 0
        self.phase = "place"
        self.winner: Optional[str] = None
        self.last_message = f"PLACE {SHIP_NAMES[0]}"
        self.last_message_braille = f"PLACE {SHIP_NAMES[0]}"
        self._last_rows: list[bytes] | None = None
        self._place_enemy_ships()
        self._target_queue: list[tuple[int, int]] = []
        self._target_set: set[tuple[int, int]] = set()
        self._player_sunk_ids: set[int] = set()
        self._cpu_sunk_ids: set[int] = set()

    def handle_key(self, names: list[str]) -> None:
        """Handle DotPad key inputs.

        Args:
            names: List of key names.
        """
        if self.winner:
            return
        if "panLeft" in names:
            self.sel_col = (self.sel_col - 1) % 10
        if "panRight" in names:
            self.sel_col = (self.sel_col + 1) % 10
        if "f1" in names:
            self.sel_row = (self.sel_row - 1) % 10
        if "f4" in names:
            self.sel_row = (self.sel_row + 1) % 10
        if "f3" in names and self.phase == "place":
            self.orientation = "V" if self.orientation == "H" else "H"
        if "f2" in names:
            if self.phase == "place":
                self._place_ship()
            elif self.phase == "attack":
                self._fire()

    def _place_ship(self) -> None:
        ship_idx = self.place_index
        length = SHIP_SIZES[ship_idx]
        ship_name = SHIP_NAMES[ship_idx].lower()
        if not self._can_place(self.player_board, self.sel_row, self.sel_col, length, self.orientation):
            self.last_message = "INVALID PLACEMENT"
            self.last_message_braille = "INVALID PLACEMENT"
            return
        start = self._square_name(self.sel_row, self.sel_col)
        end_row = self.sel_row + (length - 1 if self.orientation == "V" else 0)
        end_col = self.sel_col + (length - 1 if self.orientation == "H" else 0)
        end = self._square_name(end_row, end_col)
        self._do_place(self.player_board, self.sel_row, self.sel_col, length, self.orientation)
        ship_id = ship_idx + 1
        self._do_place_id(self.player_ship_ids, self.sel_row, self.sel_col, length, self.orientation, ship_id)
        self.place_index += 1
        self.last_message = f"placed {ship_name} from {start} to {end}"
        self.last_message_braille = self.last_message
        self.last_message_braille = f"placed {ship_name}"
        if self.place_index >= len(SHIP_SIZES):
            self.phase = "attack"

    def _fire(self) -> None:
        if self.player_shots[self.sel_row][self.sel_col] != 0:
            self.last_message = "ALREADY FIRED"
            self.last_message_braille = "ALREADY FIRED"
            return
        hit = self.enemy_board[self.sel_row][self.sel_col] == 1
        self.player_shots[self.sel_row][self.sel_col] = 2 if hit else 1
        user_square = self._square_name(self.sel_row, self.sel_col)
        user_part = f"you hit {user_square}" if hit else f"you miss {user_square}"
        user_part_braille = f"y hit {user_square}" if hit else f"y miss {user_square}"
        sunk_parts: list[str] = []
        sunk_parts_braille: list[str] = []
        if hit:
            ship_id = self.enemy_ship_ids[self.sel_row][self.sel_col]
            if ship_id > 0 and self._is_ship_sunk(self.enemy_ship_ids, self.player_shots, ship_id):
                if ship_id not in self._player_sunk_ids:
                    self._player_sunk_ids.add(ship_id)
                    sunk = f"you sunk {SHIP_NAMES[ship_id - 1].lower()}"
                    sunk_parts.append(sunk)
                    sunk_parts_braille.append(sunk.replace("you", "y"))
        if self._all_sunk(self.enemy_board, self.player_shots):
            self.winner = "player"
            self.last_message = f"{user_part}, you win"
            self.last_message_braille = f"{user_part_braille} y win"
            return
        cpu_hit, cpu_square, cpu_sunk_name = self._enemy_turn()
        cpu_part = f"I hit {cpu_square}" if cpu_hit else f"I miss {cpu_square}"
        if cpu_sunk_name:
            sunk = f"I sunk {cpu_sunk_name.lower()}"
            sunk_parts.append(sunk)
            sunk_parts_braille.append(sunk)
        tail = f", {', '.join(sunk_parts)}" if sunk_parts else ""
        self.last_message = f"{user_part}, {cpu_part}{tail}"
        tail_braille = f" {' '.join(sunk_parts_braille)}" if sunk_parts_braille else ""
        self.last_message_braille = f"{user_part_braille} {cpu_part}{tail_braille}"

    def _enemy_turn(self) -> tuple[bool, str, str | None]:
        r, c = self._enemy_pick()
        hit = self.player_board[r][c] == 1
        self.enemy_shots[r][c] = 2 if hit else 1
        sunk_name: str | None = None
        if hit:
            ship_id = self.player_ship_ids[r][c]
            self._enqueue_from_hit_cluster(r, c)
            if ship_id > 0 and self._is_ship_sunk(self.player_ship_ids, self.enemy_shots, ship_id):
                if ship_id not in self._cpu_sunk_ids:
                    self._cpu_sunk_ids.add(ship_id)
                    sunk_name = SHIP_NAMES[ship_id - 1]
                # Reset targeting after a sink so we return to hunt mode cleanly.
                self._target_queue.clear()
                self._target_set.clear()
        if self._all_sunk(self.player_board, self.enemy_shots):
            self.winner = "cpu"
        return hit, self._square_name(r, c), sunk_name

    @staticmethod
    def _square_name(r: int, c: int) -> str:
        """Return board square label like A1..J0 (10 rendered as 0)."""
        col_num = c + 1
        col_label = "0" if col_num == 10 else str(col_num)
        return f"{chr(ord('A') + r)}{col_label}"

    @staticmethod
    def _fit_message(msg: str, limit: int = 20) -> str:
        """Normalize gameplay text for the graphics message line."""
        return msg.strip().upper()[:limit]

    def _enemy_pick(self) -> tuple[int, int]:
        while self._target_queue:
            r, c = self._target_queue.pop(0)
            self._target_set.discard((r, c))
            if self.enemy_shots[r][c] == 0:
                return r, c
        # Hunt on parity squares first for better ship coverage.
        parity = [(r, c) for r in range(10) for c in range(10) if self.enemy_shots[r][c] == 0 and (r + c) % 2 == 0]
        if parity:
            return random.choice(parity)
        options = [(r, c) for r in range(10) for c in range(10) if self.enemy_shots[r][c] == 0]
        return random.choice(options)

    def _enqueue_target(self, r: int, c: int) -> None:
        if not (0 <= r < 10 and 0 <= c < 10):
            return
        if self.enemy_shots[r][c] != 0:
            return
        key = (r, c)
        if key in self._target_set:
            return
        self._target_set.add(key)
        self._target_queue.append(key)

    def _enqueue_from_hit_cluster(self, r: int, c: int) -> None:
        """Prioritize shots extending known hit lines before neighbor probes."""
        cluster = self._connected_hits(r, c)
        if len(cluster) >= 2:
            rows = {rr for rr, _ in cluster}
            cols = {cc for _, cc in cluster}
            if len(rows) == 1:
                row = next(iter(rows))
                min_c = min(cc for _, cc in cluster)
                max_c = max(cc for _, cc in cluster)
                self._enqueue_target(row, min_c - 1)
                self._enqueue_target(row, max_c + 1)
                return
            if len(cols) == 1:
                col = next(iter(cols))
                min_r = min(rr for rr, _ in cluster)
                max_r = max(rr for rr, _ in cluster)
                self._enqueue_target(min_r - 1, col)
                self._enqueue_target(max_r + 1, col)
                return

        for rr, cc in cluster:
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                self._enqueue_target(rr + dr, cc + dc)

    def _connected_hits(self, r: int, c: int) -> list[tuple[int, int]]:
        """Return orthogonally connected enemy hit cells around (r, c)."""
        if not (0 <= r < 10 and 0 <= c < 10):
            return []
        if self.enemy_shots[r][c] != 2:
            return []
        out: list[tuple[int, int]] = []
        stack = [(r, c)]
        seen = set(stack)
        while stack:
            rr, cc = stack.pop()
            out.append((rr, cc))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = rr + dr, cc + dc
                key = (nr, nc)
                if key in seen:
                    continue
                if 0 <= nr < 10 and 0 <= nc < 10 and self.enemy_shots[nr][nc] == 2:
                    seen.add(key)
                    stack.append(key)
        return out

    def _all_sunk(self, ships: list[list[int]], shots: list[list[int]]) -> bool:
        for r in range(10):
            for c in range(10):
                if ships[r][c] == 1 and shots[r][c] != 2:
                    return False
        return True

    @staticmethod
    def _is_ship_sunk(ship_ids: list[list[int]], shots: list[list[int]], ship_id: int) -> bool:
        """Return True when all cells for ship_id have been hit."""
        for r in range(10):
            for c in range(10):
                if ship_ids[r][c] == ship_id and shots[r][c] != 2:
                    return False
        return True

    def _place_enemy_ships(self) -> None:
        for idx, length in enumerate(SHIP_SIZES):
            placed = False
            while not placed:
                orientation = random.choice(["H", "V"])
                r = random.randrange(10)
                c = random.randrange(10)
                if self._can_place(self.enemy_board, r, c, length, orientation):
                    self._do_place(self.enemy_board, r, c, length, orientation)
                    self._do_place_id(self.enemy_ship_ids, r, c, length, orientation, idx + 1)
                    placed = True

    def _can_place(self, board: list[list[int]], r: int, c: int, length: int, orientation: str) -> bool:
        if orientation == "H":
            if c + length > 10:
                return False
            return all(board[r][c + i] == 0 for i in range(length))
        if r + length > 10:
            return False
        return all(board[r + i][c] == 0 for i in range(length))

    def _do_place(self, board: list[list[int]], r: int, c: int, length: int, orientation: str) -> None:
        if orientation == "H":
            for i in range(length):
                board[r][c + i] = 1
        else:
            for i in range(length):
                board[r + i][c] = 1

    def _do_place_id(
        self,
        board: list[list[int]],
        r: int,
        c: int,
        length: int,
        orientation: str,
        ship_id: int,
    ) -> None:
        """Mark placed ship segments with a stable ship id."""
        if orientation == "H":
            for i in range(length):
                board[r][c + i] = ship_id
        else:
            for i in range(length):
                board[r + i][c] = ship_id

    def ship_name_at(self, row: int, col: int) -> str | None:
        """Return ship name at player board coordinate, if any."""
        if not (0 <= row < 10 and 0 <= col < 10):
            return None
        ship_id = self.player_ship_ids[row][col]
        if ship_id <= 0:
            return None
        idx = ship_id - 1
        if 0 <= idx < len(SHIP_NAMES):
            return SHIP_NAMES[idx]
        return None

    @staticmethod
    def ship_name_from_id(ship_id: int) -> str | None:
        """Return canonical ship name for a ship id."""
        idx = ship_id - 1
        if 0 <= idx < len(SHIP_NAMES):
            return SHIP_NAMES[idx]
        return None

    def render(self, pad: dp.DotPad) -> None:
        """Render the current game state to the DotPad.

        Args:
            pad: DotPad instance.
        """
        builder = pad.builder()

        top = 6
        left = 5
        step = 3

        # Column numbers with one number sign, placed one cell left of "1".
        builder.render_text_dots("3456", row=2, col=max(1, left - 3))
        builder.render_text("1", row=2, col=left, use_number_sign=False)
        for i in range(1, 10):
            col = left + i * step
            value = str((i + 1) % 10)
            builder.render_text(value, row=2, col=col, use_number_sign=False)

        # Row letters
        for i in range(10):
            row = top + i * step
            letter = chr(ord("A") + i)
            builder.render_text(letter, row=row, col=1)
            # Mirror row label at right edge for faster orientation.
            right_col = left + (10 * step) + 1
            builder.render_text(letter, row=row, col=right_col)

        # Grid contents
        if self.phase == "place":
            view_board = self.player_board
            view_shots = None
        else:
            view_board = self.enemy_board
            view_shots = self.player_shots

        for r in range(10):
            for c in range(10):
                dot_row = top + r * step
                dot_col = left + c * step
                if self.phase == "place" and view_board[r][c] == 1:
                    builder.draw_line(dot_row, dot_col, 2)
                    builder.draw_line(dot_row + 1, dot_col, 2)
                    # Connect adjacent ship segments with a single dot.
                    cur_id = self.player_ship_ids[r][c]
                    if c < 9 and cur_id != 0 and self.player_ship_ids[r][c + 1] == cur_id:
                        builder.render_text_dots("1", row=dot_row + 1, col=dot_col + 2)
                    if r < 9 and cur_id != 0 and self.player_ship_ids[r + 1][c] == cur_id:
                        builder.render_text_dots("1", row=dot_row + 2, col=dot_col + 1)
                if view_shots:
                    if view_shots[r][c] == 1:
                        builder.render_text_dots("1", row=dot_row, col=dot_col)
                    elif view_shots[r][c] == 2:
                        # Show hit ship cells with the same ship glyph style.
                        builder.draw_line(dot_row, dot_col, 2)
                        builder.draw_line(dot_row + 1, dot_col, 2)
                        ship_id = self.enemy_ship_ids[r][c]
                        # Connect only after this enemy ship is sunk.
                        if ship_id in self._player_sunk_ids:
                            if c < 9 and self.enemy_ship_ids[r][c + 1] == ship_id:
                                builder.render_text_dots("1", row=dot_row + 1, col=dot_col + 2)
                            if r < 9 and self.enemy_ship_ids[r + 1][c] == ship_id:
                                builder.render_text_dots("1", row=dot_row + 2, col=dot_col + 1)

        # Cursor
        cur_row = top + self.sel_row * step + 2
        cur_col = left + self.sel_col * step
        builder.draw_line(cur_row, cur_col, 2)
        # Current square in bottom-right corner of graphics area.
        builder.render_text(
            self._square_name(self.sel_row, self.sel_col),
            row=38,
            col=56,
            use_number_sign=False,
            use_nemeth=True,
        )
        # Orientation indicator: 3-cell ship graphic on right side, mid-height.
        if self.phase == "place":
            ind_row = 20
            ind_col = 50
            if self.orientation == "H":
                for i in range(3):
                    c = ind_col + i * 3
                    builder.draw_line(ind_row, c, 2)
                    builder.draw_line(ind_row + 1, c, 2)
            else:
                for i in range(3):
                    r = ind_row + i * 3
                    builder.draw_line(r, ind_col, 2)
                    builder.draw_line(r + 1, ind_col, 2)
        # Extra in-graphics status line at the bottom.
        msg = self.last_message_braille
        if self.phase == "place" and (not msg or msg.startswith("PLACE")):
            current = SHIP_NAMES[min(self.place_index, len(SHIP_NAMES) - 1)]
            msg = f"PLACE {current}"
        builder.render_text(
            self._fit_message(msg),
            row=38,
            col=1,
            use_number_sign=False,
            use_nemeth=True,
        )

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
        elif self.winner == "cpu":
            send_status(pad, "YOU LOSE F3 MENU")
        elif self.phase == "place":
            send_status(pad, "PAN/F1/F4 MV F2 PLC")
        else:
            send_status(pad, "PAN/F1/F4 MV F2 FIR")
