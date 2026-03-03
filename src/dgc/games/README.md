# Games

## Controls Reference

All games use DotPad hardware keys or PC keyboard equivalents:

| DotPad Key | PC Key | Action |
|------------|--------|--------|
| Pan Left   | ← Arrow | Move cursor left |
| Pan Right  | → Arrow | Move cursor right |
| F1         | ↑ Arrow | Move cursor up |
| F4         | ↓ Arrow | Move cursor down |
| F2         | Enter/Space | Confirm / Place / Select |
| F3         | (varies) | Alternate action |
| F1 + F4    | Escape | Return to main menu |
| F3 (game over) | F3 | Return to main menu |

---

## 15 Puzzle

Classic 4×4 sliding tile puzzle with tiles 1–15 and one blank space.

**Objective:** Arrange tiles in order 1–15 (left-to-right, top-to-bottom) with the blank at bottom-right.

**Controls:**
- Pan Left/Right, F1/F4 — move cursor to a tile
- F2 — slide tile at cursor toward the blank (only works if adjacent to blank)

**AI:** None (single-player puzzle).

**Notes:** Board is shuffled by 200 random valid moves to guarantee solvability.

---

## Backgammon

Standard backgammon. Player is White (moves from point 24 toward point 1). AI is Black (moves from point 1 toward point 24).

**Objective:** Bear off all 15 of your pieces before the opponent.

**Controls:**
- Pan Left/Right or F1/F4 — cycle through available source points
- F2 — select source point; then cycle destinations and press F2 to move
- Dice are rolled automatically at the start of each turn

**Rules:** Standard backgammon — hitting (blot → bar), bar re-entry, bearing off. Doubles grant 4 moves.

**AI:** Random legal move selection.

**Limitations:** Doubling cube not implemented. No gammon/backgammon scoring.

---

## Checkers

American Checkers (8×8 board). Player is Black (bottom, moves up). AI is Red (top, moves down).

**Objective:** Capture all opponent pieces or leave opponent with no legal moves.

**Controls:**
- Pan Left/Right, F1/F4 — move cursor
- F2 (first press) — select piece at cursor (must be your piece with legal moves)
- F2 (second press) — execute move / jump to cursor position

**Rules:**
- Pieces only on dark squares ((row+col)%2==1)
- Forced captures: if a jump is available, you must jump
- Multi-jump: complete all chained captures before ending your turn
- Kinging: Black reaches row 0 → king; Red reaches row 7 → king
- Kings move in all four diagonal directions

**AI:** Prefers longest capture chains; otherwise random.

**Display:** Player pieces shown as filled squares; AI pieces as circles; kings have an extra dot indicator.

---

## Chess

Standard chess. Player is White (bottom rows). AI is Black (top rows).

**Objective:** Checkmate the opponent's king.

**Controls:**
- Pan Left/Right, F1/F4 — move cursor
- F2 (first press) — select piece at cursor (must be your piece with legal moves)
- F2 (second press) — execute move to cursor position
- F3 — deselect current piece

**Rules:**
- All standard piece movements (Pawn, Knight, Bishop, Rook, Queen, King)
- Castling (both kingside and queenside), with standard conditions
- En passant pawn captures
- Pawn promotion: auto-promotes to Queen
- Check/checkmate detection
- Stalemate detection (draw)
- Legal move filtering: moves that leave your king in check are not allowed
- Legal destinations shown as dots in cell centers

**AI:** Random legal move selection.

**Limitations:** No 50-move rule, no threefold repetition draw. Promotion always to Queen.

---

## Render Helpers

`games/helpers/render_helpers.py` — shared drawing utilities for game renderers:
- `board_to_dot(row, col, top, left, cell_h, cell_w)` — board cell → dot coordinates
- `draw_grid(builder, top, left, rows, cols, cell_h, cell_w)` — draw grid lines
- `fill_cell(builder, top, left, row, col, cell_h, cell_w)` — fill a cell with dots
- `draw_piece_square(builder, r, c, size)` — rectangle outline piece
- `draw_piece_circle(builder, r, c, size)` — approximate circle piece
- `draw_piece_x(builder, r, c, size)` — X-shaped piece using diagonals
