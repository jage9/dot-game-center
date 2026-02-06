# Dot Game Center (DGC)

A Windows-first game hub using wxPython and the DotPad device.

## Setup
From repo root:
```
cd dgc
uv sync
```

Install the DotPad wheel (built from `python/`):
```
uv pip install ../python/dist/dotpad-0.1.0-py3-none-any.whl
```

## Run
```
uv run dgc
```

## Controls (DotPad)
- panLeft / panRight: move column
- f1 / f4: move row
- f2: confirm / place / drop
- f3: toggle orientation (Battleship placement)

## Games
- Tic Tac Toe (you vs computer)
- Connect 4 (you vs computer)
- Battleship (you place ships; computer auto-places; you vs computer)

## Notes
- The main menu mirrors to the DotPad.
- Games render on the graphics area with instructions on the text line.
