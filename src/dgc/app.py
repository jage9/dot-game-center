"""Dot Game Center main application."""

from __future__ import annotations

import queue
import random
import threading
import wx
import wx.adv
import wx.grid as gridlib

import dotpad as dp
from dotpad.serial_driver import PacketType

from .games import TicTacToe, Connect4, Battleship
from .games.utils import send_status
from .sound import SoundManager
from .speech import SpeechOutput


MENU_ITEMS = ["Tic Tac Toe", "Connect 4", "Battleship", "Exit"]
APP_TITLE = "Dot Game Center"
MENU_LINK_LABEL = "visit atguys.com"
MENU_LINK_URL = "https://www.atguys.com"


class MainFrame(wx.Frame):
    """Main wxPython frame for Dot Game Center."""

    def __init__(self) -> None:
        super().__init__(None, title=APP_TITLE, size=(520, 360))
        self.pad = None
        self._pad_port = "?"
        self._connect_lock = threading.Lock()
        self._connect_pad()
        self.speech = SpeechOutput()
        self.sound = SoundManager()

        self.mode = "menu"
        self.menu_index = 0
        self.current_game = None
        self._cpu_pending = False
        self._cpu_timer: wx.CallLater | None = None
        self._menu_render_pending = False
        self._menu_force_pending = False
        self._last_menu_state: tuple[int, str] | None = None
        self._pad_lock = threading.Lock()
        self._write_queue: queue.Queue = queue.Queue(maxsize=1)
        self._writer_stop = threading.Event()
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()

        self.panel = wx.Panel(self)
        self.panel.SetName(APP_TITLE)
        self.panel.SetLabel(APP_TITLE)
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-1, 280])
        self.status_bar.SetStatusText("Ready.", 0)
        self._set_connection_status()
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.buttons = []

        for idx, label in enumerate(MENU_ITEMS):
            btn = wx.Button(self.panel, label=label)
            btn.Bind(wx.EVT_BUTTON, lambda evt, i=idx: self.on_menu_select(i))
            btn.Bind(wx.EVT_SET_FOCUS, lambda evt, i=idx: self.on_button_focus(evt, i))
            self.sizer.Add(btn, 0, wx.ALL | wx.EXPAND, 6)
            self.buttons.append(btn)
        self.menu_link = wx.adv.HyperlinkCtrl(
            self.panel,
            id=wx.ID_ANY,
            label=MENU_LINK_LABEL,
            url=MENU_LINK_URL,
        )
        self.menu_link.Bind(wx.EVT_SET_FOCUS, self.on_link_focus)
        self.sizer.Add(self.menu_link, 0, wx.ALL, 6)

        self.game_panel = wx.Panel(self.panel)
        self.game_panel.SetName("Game")
        self.game_panel.SetLabel("Game")
        self.game_sizer = wx.BoxSizer(wx.VERTICAL)
        self.game_grid = gridlib.Grid(self.game_panel)
        self.game_grid.CreateGrid(1, 1)
        self.game_grid.EnableEditing(False)
        self.game_grid.SetName("Game board")
        self.game_grid.SetToolTip("Game board")
        self.game_grid.SetRowLabelSize(56)
        self.game_grid.SetColLabelSize(30)
        self.game_grid.Bind(gridlib.EVT_GRID_SELECT_CELL, self._on_grid_select)
        self.game_sizer.Add(self.game_grid, 1, wx.ALL | wx.EXPAND, 6)
        self.game_panel.SetSizer(self.game_sizer)
        self.game_panel.Hide()
        self.sizer.Add(self.game_panel, 1, wx.ALL | wx.EXPAND, 0)

        self.panel.SetSizer(self.sizer)
        self.buttons[0].SetFocus()
        self.request_menu_render(force=True)

        # Poll key packets on the UI thread so serial read/write stays single-threaded.
        self.key_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_key_timer, self.key_timer)
        self.key_timer.Start(50)
        self.reconnect_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_reconnect_timer, self.reconnect_timer)
        self.reconnect_timer.Start(1000)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def on_close(self, event) -> None:
        if hasattr(self, "key_timer") and self.key_timer.IsRunning():
            self.key_timer.Stop()
        if hasattr(self, "reconnect_timer") and self.reconnect_timer.IsRunning():
            self.reconnect_timer.Stop()
        self._writer_stop.set()
        self._enqueue_pad_write(None)
        if self._writer_thread.is_alive():
            self._writer_thread.join(timeout=0.5)
        if self._cpu_timer is not None and self._cpu_timer.IsRunning():
            self._cpu_timer.Stop()
        with self._pad_lock:
            if self.pad is not None:
                try:
                    self.pad.clear_all()
                except Exception:
                    pass
                try:
                    self.pad.close()
                except Exception:
                    pass
                self.pad = None
        event.Skip()

    def _connect_pad(self) -> bool:
        """Try to connect DotPad once; return True on success."""
        if self.pad is not None:
            return True
        if not self._connect_lock.acquire(blocking=False):
            return False
        try:
            try:
                new_pad = dp.DotPad()
            except Exception:
                self.pad = None
                return False
            self.pad = new_pad
            self._pad_port = getattr(new_pad, "port", "?")
            return True
        finally:
            self._connect_lock.release()

    def _set_connection_status(self) -> None:
        """Update right status bar field with DotPad connection state."""
        if self.pad is None:
            self.status_bar.SetStatusText("Dot Pad disconnected", 1)
        else:
            self.status_bar.SetStatusText(f"Dot Pad connected on {self._pad_port}", 1)

    def _on_reconnect_timer(self, _event) -> None:
        """Retry DotPad connection once per second when disconnected."""
        if self.pad is None:
            self._connect_pad()
            self._set_connection_status()

    def _mark_pad_disconnected(self) -> None:
        """Drop current pad handle after I/O failure."""
        if self.pad is not None:
            try:
                self.pad.close()
            except Exception:
                pass
            self.pad = None
        self._set_connection_status()

    def _on_key_timer(self, _event) -> None:
        """Poll pending key notifications without blocking UI."""
        if self.pad is None:
            return
        processed = 0
        max_per_tick = 6
        while processed < max_per_tick:
            if not self._pad_lock.acquire(blocking=False):
                break
            try:
                ser = getattr(self.pad, "_ser", None)
                # Avoid blocking UI: only parse when serial bytes are already queued.
                if ser is None or ser.in_waiting <= 0:
                    break
                pkt = self.pad.read_packet(timeout=0.001)
            except Exception:
                self._mark_pad_disconnected()
                break
            finally:
                self._pad_lock.release()
            if not pkt or pkt.packet_type is None:
                break
            if pkt.packet_type in (
                PacketType.NTF_KEYS_SCROLL,
                PacketType.NTF_KEYS_PERKINS,
                PacketType.NTF_KEYS_ROUTING,
                PacketType.NTF_KEYS_FUNCTION,
            ):
                group_num = pkt.packet_type.value[1]
                keys = self.pad._decode_keys(pkt.args)
                if not keys:
                    processed += 1
                    continue
                names = self.pad._map_key_names(group_num, keys)
                if names:
                    self.on_pad_keys(names)
            processed += 1

    def _writer_loop(self) -> None:
        """Run queued DotPad write jobs on a background thread."""
        while not self._writer_stop.is_set():
            try:
                job = self._write_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if job is None:
                continue
            with self._pad_lock:
                try:
                    job()
                except Exception:
                    wx.CallAfter(self._mark_pad_disconnected)

    def _enqueue_pad_write(self, job) -> None:
        """Queue a DotPad write job, replacing stale pending work."""
        if self._write_queue.full():
            try:
                self._write_queue.get_nowait()
            except queue.Empty:
                pass
        self._write_queue.put_nowait(job)

    def on_button_focus(self, event: wx.FocusEvent, idx: int) -> None:
        """Track menu focus changes from keyboard navigation."""
        self.set_menu_index(idx)
        event.Skip()

    def on_link_focus(self, event: wx.FocusEvent) -> None:
        """Track focus changes for the At Guys link."""
        self.set_menu_index(len(MENU_ITEMS))
        event.Skip()

    def _focus_menu_index(self, idx: int) -> None:
        """Move keyboard focus to the menu control for idx."""
        if idx < len(MENU_ITEMS):
            self.buttons[idx].SetFocus()
        else:
            self.menu_link.SetFocus()

    def _set_status(self, text: str) -> None:
        """Update frame status bar text for screen-reader status commands."""
        self.status_bar.SetStatusText(text, 0)

    def set_menu_index(self, idx: int) -> None:
        if idx == self.menu_index:
            return
        self.menu_index = idx
        if self.mode == "menu":
            self.request_menu_render()

    def on_menu_select(self, idx: int) -> None:
        if idx == len(MENU_ITEMS):
            wx.LaunchDefaultBrowser(MENU_LINK_URL)
            self._set_status("Visit atguys.com")
            self.sound.play("select")
            return
        if idx == len(MENU_ITEMS) - 1:
            self.sound.play("select")
            self.Close()
            return
        self.sound.play("select")
        self.start_game(idx)

    def start_game(self, idx: int) -> None:
        if idx == 0:
            game = TicTacToe()
        elif idx == 1:
            game = Connect4()
        else:
            game = Battleship()
        self.current_game = game
        self._cpu_pending = False
        self.mode = "game"
        self._last_menu_state = None
        game_name = MENU_ITEMS[idx]
        for btn in self.buttons:
            btn.Hide()
        self.menu_link.Hide()
        self.game_panel.Show()
        self.game_panel.SetName(game_name)
        self.game_panel.SetLabel(game_name)
        self._setup_game_grid()
        self._update_game_grid()
        self._set_status(f"Playing: {game_name}")
        self.SetTitle(f"{APP_TITLE} - {game_name}")
        self.Layout()
        self.render_game()
        if isinstance(game, Battleship):
            self._set_status("Place your ships.")
            if self.speech.enabled:
                self.speech.speak("Place your ships.")
        # Keep focus on the frame to avoid announcing the generic panel object.
        self.SetFocus()

    def back_to_menu(self) -> None:
        self._cpu_pending = False
        if self._cpu_timer is not None and self._cpu_timer.IsRunning():
            self._cpu_timer.Stop()
        self.mode = "menu"
        self.current_game = None
        self.game_panel.Hide()
        self.game_panel.SetName("Game")
        self.game_panel.SetLabel("Game")
        for btn in self.buttons:
            btn.Show()
        self.menu_link.Show()
        self._focus_menu_index(self.menu_index)
        self.Layout()
        self._set_status("Ready.")
        self.SetTitle(APP_TITLE)
        self.request_menu_render(force=True)

    def request_menu_render(self, force: bool = False) -> None:
        """Coalesce menu renders to avoid flooding serial writes."""
        if self.mode != "menu":
            return
        if force:
            self._last_menu_state = None
            self._menu_force_pending = True
        if self._menu_render_pending:
            return
        self._menu_render_pending = True
        wx.CallAfter(self._render_menu_now)

    def _draw_menu_indicator(self, builder: dp.DotPadBuilder, row: int, col: int) -> None:
        """Draw a 3x3 rectangle indicator."""
        builder.draw_rectangle(row, col, row + 2, col + 2)

    def on_pad_keys(self, names: list[str]) -> None:
        if self.mode == "game" and self._cpu_pending:
            return

        # Global menu chord
        if "f1" in names and "f4" in names:
            self.back_to_menu()
            return

        if self.mode == "menu":
            menu_count = len(MENU_ITEMS) + 1  # plus atguys.com link
            nav_pressed = False
            if "f1" in names:
                nav_pressed = True
                self.menu_index = (self.menu_index - 1) % menu_count
                self._focus_menu_index(self.menu_index)
            if "f4" in names:
                nav_pressed = True
                self.menu_index = (self.menu_index + 1) % menu_count
                self._focus_menu_index(self.menu_index)
            if "f2" in names:
                self.on_menu_select(self.menu_index)
                return
            if nav_pressed:
                # Redraw on each menu navigation key press.
                self.request_menu_render(force=False)
        else:
            if self.current_game:
                if self._game_over():
                    if "f3" in names:
                        self.back_to_menu()
                        return
                    return
                before = self._capture_game_state(self.current_game)
                self.current_game.handle_key(names)
                self._speak_game_event(names, before, self.current_game)
                self._play_human_sound(names, before, self.current_game)
                self._update_game_grid()
                self.render_game()
                if self._should_schedule_cpu_turn(names, before, self.current_game):
                    self._schedule_cpu_turn()

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Handle keyboard shortcuts for game navigation."""
        code = event.GetKeyCode()
        if self.mode == "game":
            if code == wx.WXK_TAB:
                # Disable Tab navigation in games; use DotPad keys/arrows instead.
                return
            if code == wx.WXK_ESCAPE:
                self.back_to_menu()
                return
            if self._cpu_pending:
                return
            if code == wx.WXK_F3 and self._game_over():
                self.back_to_menu()
                return
            if code == wx.WXK_LEFT:
                self.on_pad_keys(["panLeft"])
                return
            if code == wx.WXK_RIGHT:
                self.on_pad_keys(["panRight"])
                return
            if code == wx.WXK_UP:
                self.on_pad_keys(["f1"])
                return
            if code == wx.WXK_DOWN:
                self.on_pad_keys(["f4"])
                return
            if code in (wx.WXK_RETURN, wx.WXK_SPACE):
                self.on_pad_keys(["f2"])
                return
        event.Skip()

    def _setup_game_grid(self) -> None:
        """Configure grid dimensions for the active game."""
        if not self.current_game:
            return
        if isinstance(self.current_game, TicTacToe):
            rows, cols = 3, 3
        elif isinstance(self.current_game, Connect4):
            rows, cols = self.current_game.rows, self.current_game.cols
        else:
            rows, cols = 10, 10
        cur_rows = self.game_grid.GetNumberRows()
        cur_cols = self.game_grid.GetNumberCols()
        if cur_rows < rows:
            self.game_grid.AppendRows(rows - cur_rows)
        elif cur_rows > rows:
            self.game_grid.DeleteRows(0, cur_rows - rows)
        if cur_cols < cols:
            self.game_grid.AppendCols(cols - cur_cols)
        elif cur_cols > cols:
            self.game_grid.DeleteCols(0, cur_cols - cols)
        self.game_grid.SetDefaultColSize(42, resizeExistingCols=True)
        self.game_grid.SetDefaultRowSize(28, resizeExistingRows=True)
        if isinstance(self.current_game, TicTacToe):
            for r in range(rows):
                self.game_grid.SetRowLabelValue(r, chr(ord("A") + r))
            for c in range(cols):
                self.game_grid.SetColLabelValue(c, str(c + 1))
        elif isinstance(self.current_game, Connect4):
            for r in range(rows):
                self.game_grid.SetRowLabelValue(r, f"R{r + 1}")
            for c in range(cols):
                self.game_grid.SetColLabelValue(c, str(c + 1))
        else:
            for r in range(rows):
                self.game_grid.SetRowLabelValue(r, chr(ord("A") + r))
            for c in range(cols):
                self.game_grid.SetColLabelValue(c, str(c + 1))

    def _update_game_grid(self) -> None:
        """Mirror current game state into the on-screen grid."""
        if not self.current_game:
            return
        if isinstance(self.current_game, TicTacToe):
            for r in range(3):
                for c in range(3):
                    cell = self.current_game.board[r][c] or "."
                    self.game_grid.SetCellValue(r, c, cell)
            self.game_grid.SetGridCursor(self.current_game.sel_row, self.current_game.sel_col)
        elif isinstance(self.current_game, Connect4):
            for r in range(self.current_game.rows):
                for c in range(self.current_game.cols):
                    val = self.current_game.board[r][c]
                    cell = "X" if val == 1 else "O" if val == 2 else "."
                    self.game_grid.SetCellValue(r, c, cell)
            self.game_grid.SetGridCursor(0, self.current_game.sel_col)
        elif isinstance(self.current_game, Battleship):
            if self.current_game.phase == "place":
                board = self.current_game.player_board
                for r in range(10):
                    for c in range(10):
                        cell = "S" if board[r][c] else "."
                        self.game_grid.SetCellValue(r, c, cell)
            else:
                shots = self.current_game.player_shots
                for r in range(10):
                    for c in range(10):
                        shot = shots[r][c]
                        cell = "." if shot == 0 else "o" if shot == 1 else "x"
                        self.game_grid.SetCellValue(r, c, cell)
            self.game_grid.SetGridCursor(self.current_game.sel_row, self.current_game.sel_col)
        self.game_grid.ForceRefresh()

    def _on_grid_select(self, event: gridlib.GridEvent) -> None:
        """Handle cell selection changes from keyboard/mouse navigation."""
        if self.mode != "game" or not self.current_game:
            event.Skip()
            return
        r = event.GetRow()
        c = event.GetCol()
        if isinstance(self.current_game, TicTacToe):
            self.current_game.sel_row = r
            self.current_game.sel_col = c
        elif isinstance(self.current_game, Connect4):
            self.current_game.sel_col = c
        elif isinstance(self.current_game, Battleship):
            self.current_game.sel_row = r
            self.current_game.sel_col = c
        self.render_game()
        event.Skip()

    def _game_over(self) -> bool:
        """Return True if the active game is in a terminal state."""
        return bool(self.current_game and getattr(self.current_game, "winner", None) is not None)

    def _restart_game(self) -> None:
        """Restart the active game in place."""
        if not self.current_game:
            return
        self.current_game.reset()
        self._setup_game_grid()
        self._update_game_grid()
        self.render_game()

    def render_menu(self) -> None:
        # Backward-compatible entrypoint.
        self.request_menu_render()

    def _render_menu_now(self) -> None:
        self._menu_render_pending = False
        if self.mode != "menu":
            return
        force = self._menu_force_pending
        self._menu_force_pending = False
        prev_index = self._last_menu_state[0] if self._last_menu_state else None
        state = (self.menu_index, self.mode)
        if state == self._last_menu_state:
            return
        if self.pad is None:
            return
        builder = self.pad.builder()
        # Header occupies the first 8 dot rows.
        # Keep 3-dot cell spacing so capital prefix has its own cell.
        builder.render_text_dots("6", row=1, col=1)   # D prefix
        builder.render_text("d", row=1, col=4)
        builder.render_text("ot", row=1, col=7)
        builder.render_text_dots("6", row=1, col=16)  # G prefix
        builder.render_text("g", row=1, col=19)
        builder.render_text("ame", row=1, col=22)
        builder.render_text_dots("6", row=1, col=34)  # C prefix
        builder.render_text("c", row=1, col=37)
        builder.render_text("enter", row=1, col=40)

        menu_top = 9  # Move menu list down by 8 dot rows.
        for idx, label in enumerate(MENU_ITEMS):
            row = menu_top + idx * 4
            if idx == self.menu_index:
                self._draw_menu_indicator(builder, row, 1)
            builder.render_text(label, row=row, col=6)
        link_row = self._menu_item_row(len(MENU_ITEMS))
        if self.menu_index == len(MENU_ITEMS):
            self._draw_menu_indicator(builder, link_row, 1)
        builder.render_text(MENU_LINK_LABEL, row=link_row, col=5)

        # Full redraw on initial/menu-entry; partial redraw for indicator movement.
        if force or prev_index is None:
            rows = builder.rows()

            def full_job() -> None:
                if self.pad is None:
                    return
                for i, row_bytes in enumerate(rows, start=1):
                    self.pad.send_display_line(i, row_bytes)
                send_status(self.pad, "F1/F4 MOVE F2 SELECT")

            self._enqueue_pad_write(full_job)
        else:
            rows = builder.rows()
            cur_line = self._menu_indicator_line(self.menu_index)
            prev_line = self._menu_indicator_line(prev_index)

            def partial_job() -> None:
                if self.pad is None:
                    return
                self.pad.send_display_line(cur_line, rows[cur_line - 1])
                if prev_line != cur_line:
                    self.pad.send_display_line(prev_line, rows[prev_line - 1])

            self._enqueue_pad_write(partial_job)
        self._last_menu_state = state

    @staticmethod
    def _menu_item_row(index: int) -> int:
        """Return dot row for a menu item index."""
        if index < len(MENU_ITEMS):
            return 9 + index * 4
        return 38

    @staticmethod
    def _menu_indicator_line(index: int) -> int:
        """Return 1-based graphics line for the menu indicator row."""
        dot_row = MainFrame._menu_item_row(index)
        return ((dot_row - 1) // 4) + 1

    @staticmethod
    def _capture_game_state(game: object) -> dict[str, object]:
        """Capture minimal pre-input state for speech diffing."""
        state: dict[str, object] = {}
        if isinstance(game, TicTacToe):
            state["sel_row"] = game.sel_row
            state["sel_col"] = game.sel_col
            state["board"] = [row[:] for row in game.board]
        elif isinstance(game, Connect4):
            state["sel_col"] = game.sel_col
            state["board"] = [row[:] for row in game.board]
        elif isinstance(game, Battleship):
            state["sel_row"] = game.sel_row
            state["sel_col"] = game.sel_col
            state["phase"] = game.phase
            state["orientation"] = game.orientation
            state["place_index"] = game.place_index
            state["player_shots"] = [row[:] for row in game.player_shots]
        state["winner"] = getattr(game, "winner", None)
        return state

    @staticmethod
    def _count_token(board: list[list[object]], value: object) -> int:
        return sum(1 for row in board for cell in row if cell == value)

    @staticmethod
    def _count_marked(board: list[list[int]]) -> int:
        return sum(1 for row in board for cell in row if cell != 0)

    @staticmethod
    def _new_shot_coord(before: list[list[int]], after: list[list[int]]) -> tuple[int, int, int] | None:
        """Return (row, col, shot_value) for newly marked shot cell."""
        for r in range(len(after)):
            for c in range(len(after[r])):
                if before[r][c] == 0 and after[r][c] != 0:
                    return r, c, after[r][c]
        return None

    def _should_schedule_cpu_turn(self, names: list[str], before: dict[str, object], game: object) -> bool:
        """Return True if this input created a valid human move and CPU should play."""
        if "f2" not in names or getattr(game, "winner", None) is not None:
            return False
        if isinstance(game, TicTacToe):
            prev = before.get("board")
            if not isinstance(prev, list):
                return False
            p_before = self._count_token(prev, game.player_mark)
            o_before = self._count_token(prev, game.ai_mark)
            p_now = self._count_token(game.board, game.player_mark)
            o_now = self._count_token(game.board, game.ai_mark)
            return p_now > p_before and o_now == o_before
        if isinstance(game, Connect4):
            prev = before.get("board")
            if not isinstance(prev, list):
                return False
            p_before = self._count_token(prev, 1)
            c_before = self._count_token(prev, 2)
            p_now = self._count_token(game.board, 1)
            c_now = self._count_token(game.board, 2)
            return p_now > p_before and c_now == c_before
        if isinstance(game, Battleship):
            if before.get("phase") != "attack" or game.phase != "attack":
                return False
            prev = before.get("player_shots")
            if not isinstance(prev, list):
                return False
            return self._count_marked(game.player_shots) > self._count_marked(prev)
        return False

    def _schedule_cpu_turn(self) -> None:
        """Schedule CPU move 1.5-2.0 seconds after player action."""
        self._cpu_pending = True
        if self._cpu_timer is not None and self._cpu_timer.IsRunning():
            self._cpu_timer.Stop()
        delay_ms = random.randint(1500, 2000)
        self._cpu_timer = wx.CallLater(delay_ms, self._run_cpu_turn)

    def _run_cpu_turn(self) -> None:
        """Execute delayed CPU turn and refresh game/speech."""
        self._cpu_pending = False
        if self.mode != "game" or not self.current_game or self._game_over():
            return
        before = self._capture_game_state(self.current_game)
        did_move = False
        cpu_hit = False
        cpu_square = ""
        if isinstance(self.current_game, TicTacToe):
            did_move = self.current_game.run_ai_turn()
        elif isinstance(self.current_game, Connect4):
            did_move = self.current_game.run_ai_turn()
        elif isinstance(self.current_game, Battleship):
            before_enemy = [row[:] for row in self.current_game.enemy_shots]
            did_move = self.current_game.run_cpu_turn()
            if did_move:
                shot = self._new_shot_coord(before_enemy, self.current_game.enemy_shots)
                if shot:
                    cpu_hit = shot[2] == 2
                    cpu_square = self.current_game._square_name(shot[0], shot[1])
        if not did_move:
            return
        if isinstance(self.current_game, Battleship):
            game_ref = self.current_game
            if cpu_square and self.speech.enabled:
                self.speech.speak(f"I shoot {cpu_square}")
            self.sound.play("fire")
            if cpu_hit:
                wx.CallLater(500, lambda: self.sound.play("hit"))
            wx.CallLater(500, lambda: self._announce_battleship_cpu_shot(game_ref, cpu_square, cpu_hit))
        else:
            self.sound.play("move2")
            self._speak_cpu_event(before, self.current_game)
        self._update_game_grid()
        self.render_game()

    def _speak_cpu_event(self, before: dict[str, object], game: object) -> None:
        """Speak/announce CPU turn updates."""
        msg = ""
        if isinstance(game, TicTacToe):
            prev = before.get("board")
            if isinstance(prev, list):
                for rr in range(3):
                    for cc in range(3):
                        if prev[rr][cc] == "" and game.board[rr][cc] == game.ai_mark:
                            msg = f"Computer places {game.ai_mark} at {chr(ord('A') + rr)}{cc + 1}"
                            break
                    if msg:
                        break
        elif isinstance(game, Connect4):
            prev = before.get("board")
            if isinstance(prev, list):
                for rr in range(game.rows):
                    for cc in range(game.cols):
                        if prev[rr][cc] == 0 and game.board[rr][cc] == 2:
                            msg = f"circle dropped in col {cc + 1}"
                            break
                    if msg:
                        break
        elif isinstance(game, Battleship):
            msg = game.last_message

        if msg:
            self._set_status(msg)
            if self.speech.enabled:
                self.speech.speak(msg)

        if getattr(game, "winner", None) is not None:
            end_msg = self._game_end_message(game)
            if end_msg:
                self._set_status(end_msg)
                if self.speech.enabled:
                    self.speech.speak(end_msg, interrupt=False)
                if "YOU WIN" in end_msg.upper():
                    self.sound.play("win")
                elif "YOU LOSE" in end_msg.upper():
                    self.sound.play("lose")
                elif "DRAW" in end_msg.upper():
                    self.sound.play("tie")

    def _announce_battleship_user_shot(self, game: Battleship, square: str, hit: bool) -> None:
        """Speak/status player Battleship shot timed to SFX."""
        outcome = "hit" if hit else "miss"
        msg = f"{square}, {outcome}"
        game.last_message = msg
        game.last_message_braille = f"y {outcome} {square.lower()}"
        self._set_status(msg)
        if self.speech.enabled:
            self.speech.speak(outcome)
            if game.pending_user_sunk_speech:
                self.speech.speak(game.pending_user_sunk_speech, interrupt=False)
        game.pending_user_sunk_speech = None
        self.render_game()
        if getattr(game, "winner", None) is not None:
            end_msg = self._game_end_message(game)
            if end_msg:
                self._set_status(end_msg)
                if self.speech.enabled:
                    self.speech.speak(end_msg, interrupt=False)
                if "YOU WIN" in end_msg.upper():
                    self.sound.play("win")
                elif "YOU LOSE" in end_msg.upper():
                    self.sound.play("lose")
                elif "DRAW" in end_msg.upper():
                    self.sound.play("tie")

    def _announce_battleship_cpu_shot(self, game: Battleship, square: str, hit: bool) -> None:
        """Speak/status CPU Battleship shot timed to SFX."""
        outcome = "hit" if hit else "miss"
        if square:
            msg = f"I shoot {square}, {outcome}"
            game.last_message = msg
            game.last_message_braille = f"i {outcome} {square.lower()}"
            self._set_status(msg)
            if self.speech.enabled:
                self.speech.speak(outcome)
        self.render_game()
        if getattr(game, "winner", None) is not None:
            end_msg = self._game_end_message(game)
            if end_msg:
                self._set_status(end_msg)
                if self.speech.enabled:
                    self.speech.speak(end_msg, interrupt=False)
                if "YOU WIN" in end_msg.upper():
                    self.sound.play("win")
                elif "YOU LOSE" in end_msg.upper():
                    self.sound.play("lose")
                elif "DRAW" in end_msg.upper():
                    self.sound.play("tie")

    def _speak_game_event(self, names: list[str], before: dict[str, object], game: object) -> None:
        """Speak movement and placement updates as one combined message."""
        parts: list[str] = []
        nav = {"panLeft", "panRight", "f1", "f4"}
        moved = any(key in names for key in nav)
        placed = "f2" in names

        if isinstance(game, TicTacToe):
            if moved:
                row = game.sel_row
                col = game.sel_col
                old_row = int(before.get("sel_row", row))
                old_col = int(before.get("sel_col", col))
                if row != old_row or col != old_col:
                    square = f"{chr(ord('A') + row)}{col + 1}"
                    mark = game.board[row][col]
                    if mark:
                        parts.append(f"{square}, {mark}")
                    else:
                        parts.append(f"{square}, blank")
            if placed:
                prev = before.get("board")
                if isinstance(prev, list):
                    player_square = None
                    ai_square = None
                    for rr in range(3):
                        for cc in range(3):
                            if prev[rr][cc] == "" and game.board[rr][cc] == game.player_mark:
                                player_square = f"{chr(ord('A') + rr)}{cc + 1}"
                            if prev[rr][cc] == "" and game.board[rr][cc] == game.ai_mark:
                                ai_square = f"{chr(ord('A') + rr)}{cc + 1}"
                    if player_square:
                        parts.append(f"You place {game.player_mark} at {player_square}")
                    if ai_square:
                        parts.append(f"Computer places {game.ai_mark} at {ai_square}")
        elif isinstance(game, Connect4):
            if moved:
                col = game.sel_col + 1
                old_col = int(before.get("sel_col", col - 1)) + 1
                if col != old_col:
                    parts.append(f"col {col}")
            if placed:
                prev = before.get("board")
                if isinstance(prev, list):
                    dropped_col = None
                    for rr in range(game.rows):
                        for cc in range(game.cols):
                            if prev[rr][cc] == 0 and game.board[rr][cc] == 1:
                                dropped_col = cc + 1
                                break
                        if dropped_col is not None:
                            break
                    if dropped_col is not None:
                        parts.append(f"square dropped in col {dropped_col}")
        elif isinstance(game, Battleship):
            if moved:
                row = game.sel_row + 1
                col = game.sel_col + 1
                old_row = int(before.get("sel_row", row - 1)) + 1
                old_col = int(before.get("sel_col", col - 1)) + 1
                if row != old_row or col != old_col:
                    square = game._square_name(game.sel_row, game.sel_col)
                    if game.phase == "place":
                        ship_name = game.ship_name_at(game.sel_row, game.sel_col)
                        if ship_name:
                            parts.append(f"{square}, {ship_name}")
                        else:
                            parts.append(square)
                    else:
                        shot = game.player_shots[game.sel_row][game.sel_col]
                        if shot == 1:
                            parts.append(f"{square}, miss")
                        elif shot == 2:
                            ship_id = game.enemy_ship_ids[game.sel_row][game.sel_col]
                            if ship_id in game._player_sunk_ids and ship_id > 0:
                                ship_name = game.ship_name_from_id(ship_id)
                                if ship_name:
                                    parts.append(f"{square}, {ship_name}")
                                else:
                                    parts.append(f"{square}, hit")
                            else:
                                parts.append(f"{square}, hit")
                        else:
                            parts.append(square)
            if "f3" in names and game.phase == "place":
                parts.append("horizontal" if game.orientation == "H" else "vertical")
            if placed:
                if before.get("phase") == "place":
                    if before.get("place_index") != game.place_index or game.last_message == "INVALID PLACEMENT":
                        parts.append(game.last_message)
                elif before.get("phase") == "attack":
                    prev = before.get("player_shots")
                    if isinstance(prev, list) and self._count_marked(game.player_shots) == self._count_marked(prev):
                        parts.append(game.last_message)

        if parts:
            msg = ", ".join(parts)
            battleship_nav_only = (
                isinstance(game, Battleship)
                and moved
                and not placed
                and "f3" not in names
            )
            if not battleship_nav_only:
                self._set_status(msg)
            if self.speech.enabled:
                self.speech.speak(msg)

        prev_winner = before.get("winner")
        now_winner = getattr(game, "winner", None)
        if prev_winner is None and now_winner is not None:
            if isinstance(game, Battleship):
                return
            end_msg = self._game_end_message(game)
            if end_msg:
                self._set_status(end_msg)
                if self.speech.enabled:
                    self.speech.speak(end_msg, interrupt=False)
                if "YOU WIN" in end_msg.upper():
                    self.sound.play("win")
                elif "YOU LOSE" in end_msg.upper():
                    self.sound.play("lose")
                elif "DRAW" in end_msg.upper():
                    self.sound.play("tie")

    def _play_human_sound(self, names: list[str], before: dict[str, object], game: object) -> None:
        """Play player action sounds."""
        if "f2" not in names:
            return
        if isinstance(game, Battleship) and before.get("phase") == "place":
            if before.get("place_index") != game.place_index:
                self.sound.play("place")
            return
        if isinstance(game, Battleship) and before.get("phase") == "attack":
            prev = before.get("player_shots")
            if isinstance(prev, list):
                shot = self._new_shot_coord(prev, game.player_shots)
                if shot is not None:
                    square = game._square_name(shot[0], shot[1])
                    hit = shot[2] == 2
                    if self.speech.enabled:
                        self.speech.speak(square)
                    self.sound.play("fire")
                    if hit:
                        wx.CallLater(500, lambda: self.sound.play("hit"))
                    wx.CallLater(500, lambda: self._announce_battleship_user_shot(game, square, hit))
            return
        if isinstance(game, TicTacToe):
            prev = before.get("board")
            if isinstance(prev, list):
                if self._count_token(game.board, game.player_mark) > self._count_token(prev, game.player_mark):
                    self.sound.play("move1")
            return
        if isinstance(game, Connect4):
            prev = before.get("board")
            if isinstance(prev, list):
                if self._count_token(game.board, 1) > self._count_token(prev, 1):
                    self.sound.play("move1")

    @staticmethod
    def _game_end_message(game: object) -> str:
        """Return spoken/status game-over message for current game."""
        if isinstance(game, TicTacToe):
            if game.winner == "draw":
                return "Draw. F3 menu."
            if game.winner == game.player_mark:
                return "You win. F3 menu."
            if game.winner == game.ai_mark:
                return "You lose. F3 menu."
        elif isinstance(game, Connect4):
            if game.winner == -1:
                return "Draw. F3 menu."
            if game.winner == 1:
                return "You win. F3 menu."
            if game.winner == 2:
                return "You lose. F3 menu."
        elif isinstance(game, Battleship):
            if game.winner == "player":
                return "You win. F3 menu."
            if game.winner == "cpu":
                return "You lose. F3 menu."
        return ""

    def render_game(self) -> None:
        if not self.current_game or self.mode != "game" or self.pad is None:
            return
        game = self.current_game

        def game_job() -> None:
            # Skip stale jobs queued before mode/game changed.
            if self.mode != "game" or self.current_game is not game or self.pad is None:
                return
            game.render(self.pad)

        self._enqueue_pad_write(game_job)


def main() -> None:
    app = wx.App(False)
    frame = MainFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
