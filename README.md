# Dot Game Center (DGC)

## What it Is
Some games benefit from being able to ffeel the tactile or braille board while playing. While these games are perfectly playable with speech, having a dedicated graphical view of the board makes them easier to understand and provides multimodal output.
These games are designed to work with the Dot Pad X multiline braille display and graphics tablet, though are playable with speech alone if desired. 

## Getting Started
- [Download the latest release](https://github.com/jage9/dot-game-center/releases/latest)
- Unzip to a folder on your hard drive
- If using a Dot Pad, connect via USB
- Run dgc.exe.

## Games - All against the computer unless otherwise noted

### Tic Tac Toe
Play the classic game of Ex's and O's

### Connect 4
Place 4 of yor tiles in a row to win.

## Battleship
First, place your 5 ships, then try to destroy  your opponent's ships before they destroy yours.

# 15 Puzzle
The traditional sliding tile puzzle. Put the numbers in order from 1 to 15. If you get stuck, press F3 to have the computer autosolve.

## Controls
Games can be controled both through the Dot Pad as well as the computer.

## Main Menu
- `F1/F4` move to previous or next menu item
- `F2` select menu item

## In-Game Controls
- DotPad: `panLeft/panRight` move to previous or next column, `F1/F4` move to previous or next row, `F2` perform action
- Keyboard: arrow keys move, `Enter/Space` action, `Escape` back to menu
- On game over: `F3` or `Escape` returns to menu

## Technical Explanation
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

## Contributing
Contributions are welcome. Please create an issue with bugs/feature ideas or submit a PR for consideration.

## Building & Releasing

**Local build** (produces `dist/dgc/`):
```powershell
.\install.ps1
```

**Cut a release** (bumps version, tags, pushes — GitHub Actions builds and publishes automatically):
```powershell
.\release.ps1 0.3
```
The workflow builds on `windows-latest`, zips `dist/dgc/`, and attaches it to a GitHub Release.
First-time CI setup: run `uv run python _setup_ci.py` once to create `.github/workflows/release.yml`, then commit it.

## License
- MIT
This project is licensed under the MIT License. See `LICENSE`.

## Note
These games are not created by Dot Inc. No warranty is implied.