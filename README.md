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

## In-Game Controls
- DotPad: `panLeft/panRight` move to previous or next column, `F1/F4` move to previous or next row, `F2` perform action
- Keyboard: arrow keys move, `Enter/Space` action, `Escape` back to menu
- On game over: `F3` or `Escape` returns to menu

## Contributing
Contributions are welcome. Please create an issue with bugs/feature ideas or submit a PR for consideration.

## License
- MIT
This project is licensed under the MIT License. See `LICENSE`.
