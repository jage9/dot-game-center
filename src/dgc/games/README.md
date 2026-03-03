# New Games – Dot Game Center

This document describes the four games added to Dot Game Center: **15 Puzzle**, **Backgammon**, **Checkers**, and **Chess**.

---

## Controls (all games)

All games use the same 6-button input model as the existing games:

| Input | DotPad key | Keyboard key | Action |
|-------|-----------|--------------|--------|
| Move cursor left | `panLeft` | ← Arrow | Move cursor left |
| Move cursor right | `panRight` | → Arrow | Move cursor right |
| Move cursor up | `F1` | ↑ Arrow | Move cursor up / switch row |
| Move cursor down | `F4` | ↓ Arrow | Move cursor down / switch row |
| Confirm / Action | `F2` | Enter / Space | Select piece, confirm move, roll dice |
| Cancel / Back | `F3` | Escape | Cancel selection, undo (15 Puzzle) |
| Return to menu | `F1 + F4` | Escape (in menu) | Go back to main menu |

---

## 15 Puzzle

A classic 4×4 sliding tile puzzle with tiles numbered 1–15 and one empty space.

### Goal
Arrange tiles in order (1–15, left-to-right, top-to-bottom) with the empty space in the bottom-right corner.

### Controls
- **F1/F4/panLeft/panRight**: Move the cursor to a different tile.
- **F2**: Slide the tile under the cursor into the empty space (only works if the tile is adjacent to the empty space).
- **F3**: Undo the last move.

### Rules & Features
- Boards are always shuffled to a solvable state.
- An undo stack allows reversing moves.
- Move counter shown in the status line.

---

## Backgammon

Standard backgammon for one player vs a simple AI. No doubling cube.

### Board Layout (DotPad)
- **Top row** (dots row 1–19): Points 24 down to 13, left-to-right.
- **Bottom row** (dots row 22–40): Points 1 up to 12, left-to-right.
- **Bar**: Center column between points 6/7 and 18/19.
- Player (white) pieces shown as solid horizontal lines; AI (black) pieces as endpoint dots.

### Controls
- **F2** (roll phase): Roll the dice.
- **panLeft/panRight**: Move cursor left/right among points.
- **F1**: Switch cursor to the top row.
- **F4**: Switch cursor to the bottom row.
- **F2** (move phase, no selection): Select the source point at the cursor.
- **F2** (move phase, with selection): Confirm destination point at the cursor.
- **F3**: Cancel current piece selection.

### Rules & Features
- Dice automatically grant doubles (four moves).
- Bar entry is forced before other moves.
- Bearing off is handled when all checkers are in the home board.
- **AI**: Greedy pip-count minimisation — each die value is used to make the move that reduces the AI's total pip count the most.

### Limitations
- No doubling cube.
- No automatic bearing-off prompt (use the rightmost column, `sel_col=11` on the bottom row, as the bear-off destination).

---

## Checkers (American / English)

Standard American checkers on an 8×8 board.

### Goal
Capture all of the opponent's pieces, or leave the opponent with no legal moves.

### Setup
- Player plays **red** (X marks, moves upward from rows 5–7).
- AI plays **black** (square marks, moves downward from rows 0–2).
- Pieces occupy dark squares only.

### Controls
- **F1/F4/panLeft/panRight**: Move cursor one step (snaps to nearest dark square).
- **F2** (no selection): Select the player piece under the cursor.
- **F2** (piece selected): Move the selected piece to the cursor's destination.
- **F3**: Cancel the current piece selection.

### Rules & Features
- **Forced captures**: If any capture is available, the player must make a capture.
- **Multiple jumps**: After a capture, if another capture is possible with the same piece, the player may continue jumping (pressing F2 at each destination).
- **Kinging**: A piece reaching the opponent's back rank becomes a king (can move in both directions). Multi-jump stops when a piece is kinged.
- **Win**: Opponent has no pieces or no legal moves.
- **Draw**: 80 half-moves without a capture or kinging.
- **AI**: Prefers captures; picks the capture that creates the most subsequent capture opportunities; otherwise moves randomly.

---

## Chess

Standard chess for one player (white) vs a depth-2 minimax AI (black).

### Goal
Checkmate the opponent's king.

### Setup
- Player plays **white** (uppercase letters: P N B R Q K).
- AI plays **black** (lowercase letters: p n b r q k).
- Standard starting position.

### Controls
- **F1/F4/panLeft/panRight**: Move cursor one square.
- **F2** (no selection): Select the white piece under the cursor (highlights legal destinations with small markers).
- **F2** (piece selected): Move the selected piece to the cursor's destination.
- **F3**: Cancel the current piece selection.

### Rules & Features
- **Castling**: King-side and queen-side castling (if rights are intact and squares are clear).
- **En passant**: Pawn en passant captures are fully supported.
- **Pawn promotion**: Automatically promotes to queen.
- **Check detection**: Status line announces "CHECK!" when the player's king is in check.
- **Checkmate/stalemate**: Game ends with appropriate message.
- **50-move draw**: 100 half-moves without a pawn move or capture.
- **AI**: Depth-2 minimax with alpha-beta pruning; evaluates positions by material value.

---

## Rendering Notes

All four games render to the full 60×40 dot display of the DotPad:

- **15 Puzzle**: 4×4 grid with 13×9 dot cells; tile numbers in braille.
- **Checkers/Chess**: 8×8 grid with 7×5 dot cells; pieces as tactile symbols or braille letters.
- **Backgammon**: Full-width 60-dot layout; stacked dot-lines for pieces; bar and home areas indicated.

The status text line (20 cells) shows the current action and game state at all times.
