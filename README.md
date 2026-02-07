# Dot Game Center (DGC)

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

## Menu Controls
- `F1/F4` move to previous or next menu item
- `F2` select menu item

## Games - all vs. computer
- Tic Tac Toe
- Connect 4
- Battleship

## In-Game Controls
- DotPad: `panLeft/panRight` move to previous or next column, `F1/F4` move to previous or next row, `F2` action
- Keyboard: arrow keys move, `Enter/Space` action, `Esc` back to menu
- On game over: `F3` returns to menu

## Notes
- Windows status bar shows last action for screen reader status commands.

## Contributing
Contributions are welcome. Please create an issue with bugs/feature ideas or submit a PR for consideration.

## License
- MIT
This project is licensed under the MIT License. See `LICENSE`.
