# Dot Game Center (DGC)

A Windows-first game hub using wxPython and the DotPad device.

## Setup
From repo root:
```
cd dgc
.\setup.ps1
```

## Run
```
uv run dgc
```

## DotPad Wheel Location
- Keep DotPad artifacts in `vendor/dotpad/` inside this repo.
- `setup.ps1` installs the newest `dotpad-*.whl` from that folder.

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
