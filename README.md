# Dot Game Center (DGC)

## What it Is
Some games benefit from being able to ffeel the tactile or braille board while playing. While these games are perfectly playable with speech, having a dedicated graphical view of the board makes them easier to understand and provides multimodal output.
These games are designed to work with the Dot Pad X multiline braille display and graphics tablet, though are playable with speech alone if desired.

## How it Works
Dot Game Center is a Windows-first game app built with wxPython and DotPad.
It uses a  DotPad Python wheel and its `DotPad` class as the hardware layer.
That class handles both output areas on the device:
- the 20-cell text line for short prompts/status
- the 300-cell graphics grid for game boards and markers

DGC sits above that wrapper and focuses on gameplay, navigation, and accessibility.

## Setup from Source
From `dgc/`:
```
.\setup.ps1
```
- `setup.ps1` runs `uv sync` and installs the newest `dotpad-*.whl` from `vendor/dotpad/`.
- `uv` is required.
```
uv run dgc
```
or from Command Prompt:
```
dgc.bat
```

## Controls
Games can be controled both through the Dot Pad as well as the computer.

## Main Menu
- `F1/F4` move to previous or next menu item
- `F2` select menu item

## Games - all vs. computer
- Tic Tac Toe
- Connect 4
- Battleship

## Display-First Prototype Games
The following four games are display-first prototypes.  They render a correct
tactile initial board layout on the Dot Pad X and support cursor navigation,
but do not yet implement full move validation or an AI opponent.

- **15 Puzzle** — 4 × 4 sliding tile puzzle; F2 slides the selected tile toward the blank.
- **Backgammon** — Standard 24-point board with initial checker positions.
- **Checkers** — 8 × 8 draughts board with standard opening layout.
- **Chess** — 8 × 8 board with all pieces in standard starting positions.

Navigation for all prototype games: PanLeft/PanRight move left/right; F1/F4 move up/down.
F3 (or Escape) returns to the main menu.

## In-Game Controls
- DotPad: `panLeft/panRight` move to previous or next column, `F1/F4` move to previous or next row, `F2` perform action
- Keyboard: arrow keys move, `Enter/Space` action, `Escape` back to menu
- On game over: `F3` or `Escape` returns to menu

## Contributing
Contributions are welcome. Please create an issue with bugs/feature ideas or submit a PR for consideration.

## License
- MIT
This project is licensed under the MIT License. See `LICENSE`.
