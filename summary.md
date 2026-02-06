# DGC Summary

## What I built
- **Dot Game Center** app scaffold at `dgc/` with wxPython UI and DotPad integration.
- Three games with DotPad-first rendering:
  - **Tic Tac Toe** (minimax AI)
  - **Connect 4** (win/block/center heuristic)
  - **Battleship** (placement + hunt/target AI)

## Current status and validation
- Core app and game logic are implemented and wired into one runnable app entrypoint.
- This environment cannot fully validate wx UI plus DotPad hardware end-to-end.
- Rendering and controls were implemented from your agreed mappings and the current DotPad wrapper API.
- Final behavior confirmation still needs local Windows run with the real device connected.

## Project structure
- `dgc/src/dgc/app.py`: wxPython UI, menu, DotPad key listener, game routing.
- `dgc/src/dgc/games/`: game logic and rendering.
  - `tictactoe.py`, `connect4.py`, `battleship.py`
  - `utils.py` (row-to-dot helper)
- `dgc/pyproject.toml`, `dgc/README.md`, `dgc/AGENTS.md`.

## Controls (DotPad)
- **panLeft / panRight**: move column (all games)
- **f1 / f4**: move row
- **f2**: confirm/place/drop
- **f3**: rotate (Battleship placement)
- **f1 + f4**: return to menu (global chord)

## Menu rendering (DotPad)
- Uses a single-cell braille `g` marker in column 1.
- Menu text starts at column 5.
- Menu mirrors focus changes from keyboard tab/shift-tab in wx controls.

## Game rendering notes
### Tic Tac Toe
- 3x3 grid drawn in dots.
- X/O rendered as braille letters inside each cell.
- Focus indicator is a short horizontal line below the selected cell.
- Text line shows instructions and win/draw state.

### Connect 4
- 7 columns by 6 rows.
- Player piece = 3x3 square; CPU piece = compact 2x2 circle approximation.
- Cursor indicator moves across the top row to show drop column.
- Text line shows instructions and win/draw state.

### Battleship
- 10x10 grid with letters on the left and numbers on top.
- Row labels start at dot row 5, spaced every 3 dot rows.
- Column numbers start at dot col 5, spaced every 3 dot cols; one number sign is placed above.
- Placement phase shows player ships; attack phase shows hits and misses.
- Cursor is a short line below the selected cell.
- Sunk-ship-specific marker is not separate yet.

## AI notes
- **Tic Tac Toe**: full minimax (never loses).
- **Connect 4**: win/block/center heuristic.
- **Battleship**: hunt/target (queue neighboring cells after a hit, otherwise random hunt).

## Questions / open items
1. Board density: keep current fit-first spacing or switch to larger symbols.
2. Battleship symbols: keep current markers or add a distinct sunk marker.
3. Text verbosity: shorten or expand instruction lines.
4. Connect4 AI level: keep heuristic or upgrade to deeper minimax.

## How to run
From repo root:
```bash
cd dgc
uv sync
uv pip install ../python/dist/dotpad-0.1.0-py3-none-any.whl
uv run dgc
```

## Notes on packaging
- The app assumes a local wheel from `python/dist/`.
- Build wheel with `python/build_wheel.ps1`.
