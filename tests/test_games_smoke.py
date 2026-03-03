"""Smoke tests for the four new game implementations."""

from __future__ import annotations

import sys
import os
import types
import unittest

# Ensure the src tree is on the path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# Minimal stub for dotpad so games can be imported without hardware.
# ---------------------------------------------------------------------------

class _FakeBuffer:
    def set_dot(self, row, col, on=True):
        pass
    def draw_braille_text(self, cells, start_row, start_col):
        pass
    def to_rows(self):
        return [bytes(30) for _ in range(10)]

class _FakeBuilder:
    def draw_line(self, row, col, length): pass
    def draw_vline(self, row, col, length): pass
    def draw_rectangle(self, r1, c1, r2, c2): pass
    def draw_diag_line(self, row, col, length, direction="ltr"): pass
    def render_text(self, text, row, col, **kw): pass
    def render_text_dots(self, dots, row, col): pass
    def rows(self):
        return [bytes(30) for _ in range(10)]

class _FakePad:
    def builder(self):
        return _FakeBuilder()
    def send_display_line(self, line, row_bytes):
        pass
    def send_text(self, text, **kw):
        pass

# Inject stub dotpad module so the game files can import it.
_dp = types.ModuleType("dotpad")
_dp.DotPad = _FakePad
_dp.DotPadBuilder = _FakeBuilder
sys.modules.setdefault("dotpad", _dp)


from dgc.games.fifteen_puzzle import FifteenPuzzle  # noqa: E402
from dgc.games.backgammon import Backgammon          # noqa: E402
from dgc.games.checkers import Checkers              # noqa: E402
from dgc.games.chess import Chess                    # noqa: E402


class TestFifteenPuzzle(unittest.TestCase):
    def test_initial_state(self):
        game = FifteenPuzzle()
        self.assertIsNone(game.winner)
        self.assertEqual(len(game.tiles), 4)
        self.assertEqual(len(game.tiles[0]), 4)
        # All tiles 0-15 present exactly once
        flat = [game.tiles[r][c] for r in range(4) for c in range(4)]
        self.assertEqual(sorted(flat), list(range(16)))

    def test_render_no_exception(self):
        game = FifteenPuzzle()
        pad = _FakePad()
        game.render(pad)  # Should not raise

    def test_run_ai_turn_returns_false(self):
        game = FifteenPuzzle()
        self.assertFalse(game.run_ai_turn())

    def test_handle_key_moves_cursor(self):
        game = FifteenPuzzle()
        game.cursor_row = 1
        game.cursor_col = 1
        game.handle_key(["panRight"])
        self.assertEqual(game.cursor_col, 2)
        game.handle_key(["f1"])
        self.assertEqual(game.cursor_row, 0)

    def test_win_detection(self):
        game = FifteenPuzzle()
        # Manually set solved state
        game.tiles = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, 0],
        ]
        game._check_win()
        self.assertEqual(game.winner, "win")

    def test_reset_produces_valid_puzzle(self):
        game = FifteenPuzzle()
        game.reset()
        flat = [game.tiles[r][c] for r in range(4) for c in range(4)]
        self.assertEqual(sorted(flat), list(range(16)))


class TestBackgammon(unittest.TestCase):
    def test_initial_state(self):
        game = Backgammon()
        self.assertIsNone(game.winner)
        self.assertEqual(game.turn, "player")
        # Standard starting pip counts
        self.assertEqual(game.points[24], 2)   # 2 white at point 24
        self.assertEqual(game.points[13], 5)   # 5 white at point 13
        self.assertEqual(game.points[1], -2)   # 2 black at point 1
        self.assertEqual(game.points[12], -5)  # 5 black at point 12

    def test_render_no_exception(self):
        game = Backgammon()
        game.render(_FakePad())

    def test_run_ai_turn_when_not_ai(self):
        game = Backgammon()
        self.assertEqual(game.turn, "player")
        result = game.run_ai_turn()
        self.assertFalse(result)  # Not AI's turn yet

    def test_ai_turn_runs(self):
        game = Backgammon()
        game.turn = "ai"
        result = game.run_ai_turn()
        self.assertTrue(result)
        # After AI turn, turn should return to player
        self.assertEqual(game.turn, "player")

    def test_handle_key_cycles_sources(self):
        game = Backgammon()
        idx_before = game._src_idx
        game.handle_key(["panRight"])
        # src_idx should have changed if there are sources
        if game._src_list:
            self.assertNotEqual(game._src_idx, idx_before)

    def test_dice_are_valid(self):
        game = Backgammon()
        self.assertIn(len(game.remaining_dice), [2, 4])
        for d in game.remaining_dice:
            self.assertIn(d, range(1, 7))


class TestCheckers(unittest.TestCase):
    def test_initial_state(self):
        game = Checkers()
        self.assertIsNone(game.winner)
        # Count pieces: 12 black, 12 red
        black_count = sum(1 for r in range(8) for c in range(8) if game.board[r][c] > 0)
        red_count = sum(1 for r in range(8) for c in range(8) if game.board[r][c] < 0)
        self.assertEqual(black_count, 12)
        self.assertEqual(red_count, 12)

    def test_render_no_exception(self):
        game = Checkers()
        game.render(_FakePad())

    def test_run_ai_turn(self):
        game = Checkers()
        result = game.run_ai_turn()
        self.assertTrue(result)

    def test_handle_key_navigation(self):
        game = Checkers()
        game.cursor_row = 4
        game.cursor_col = 4
        game.handle_key(["panLeft"])
        self.assertEqual(game.cursor_col, 3)
        game.handle_key(["f4"])
        self.assertEqual(game.cursor_row, 5)

    def test_player_move(self):
        """Player should be able to select and move a black piece."""
        game = Checkers()
        # Black pieces are on rows 5-7 on dark squares; find one with legal moves
        all_moves = game._get_all_moves(1)
        self.assertTrue(len(all_moves) > 0)
        # Select the piece
        fr, fc = all_moves[0][0]
        tr, tc = all_moves[0][-1]
        game.cursor_row, game.cursor_col = fr, fc
        game.handle_key(["f2"])  # select
        self.assertIsNotNone(game.selected)
        game.cursor_row, game.cursor_col = tr, tc
        game.handle_key(["f2"])  # move
        self.assertIsNone(game.selected)

    def test_reset(self):
        game = Checkers()
        game.run_ai_turn()
        game.reset()
        black_count = sum(1 for r in range(8) for c in range(8) if game.board[r][c] > 0)
        self.assertEqual(black_count, 12)


class TestChess(unittest.TestCase):
    def test_initial_state(self):
        game = Chess()
        self.assertIsNone(game.winner)
        self.assertEqual(game.turn, 1)  # White's turn
        # Check a few standard positions
        self.assertEqual(game.board[0][0], -4)  # black rook
        self.assertEqual(game.board[7][4], 6)   # white king
        self.assertEqual(game.board[0][4], -6)  # black king

    def test_render_no_exception(self):
        game = Chess()
        game.render(_FakePad())

    def test_run_ai_turn_white_turn(self):
        game = Chess()
        # Should return False when it's white's turn
        self.assertFalse(game.run_ai_turn())

    def test_run_ai_turn_black(self):
        game = Chess()
        game.turn = -1
        result = game.run_ai_turn()
        self.assertTrue(result)
        self.assertEqual(game.turn, 1)  # After black moves, white's turn

    def test_white_pawn_moves(self):
        """White pawns should have forward moves available."""
        game = Chess()
        # e2 pawn should be able to move to e3 or e4
        moves = game._all_legal_moves(1)
        self.assertTrue(len(moves) > 0)

    def test_handle_key_select_move(self):
        game = Chess()
        # Move cursor to e2 (row 6, col 4)
        game.cursor_row = 6
        game.cursor_col = 4
        game.handle_key(["f2"])  # select white pawn
        self.assertEqual(game.selected, (6, 4))
        self.assertTrue(len(game.legal_dests) > 0)

    def test_full_white_move(self):
        """Player should be able to move a pawn."""
        game = Chess()
        game.cursor_row = 6
        game.cursor_col = 4
        game.handle_key(["f2"])  # select e2 pawn
        # Move to e4
        game.cursor_row = 4
        game.cursor_col = 4
        game.handle_key(["f2"])  # move
        self.assertEqual(game.board[4][4], 1)  # white pawn at e4
        self.assertEqual(game.board[6][4], 0)  # e2 is now empty
        self.assertEqual(game.turn, -1)  # black's turn

    def test_reset(self):
        game = Chess()
        game.handle_key(["f2"])
        game.reset()
        self.assertEqual(game.board[7][4], 6)  # white king back
        self.assertEqual(game.turn, 1)

    def test_deselect_with_f3(self):
        game = Chess()
        game.cursor_row = 6
        game.cursor_col = 4
        game.handle_key(["f2"])  # select
        self.assertIsNotNone(game.selected)
        game.handle_key(["f3"])  # deselect
        self.assertIsNone(game.selected)


if __name__ == "__main__":
    unittest.main()
