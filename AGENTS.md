# Repository Guidelines (DGC)

## Scope
These guidelines apply to the Dot Game Center app under `dgc/`.

## Project Structure
- `src/dgc/app.py`: wxPython UI + routing.
- `src/dgc/dotpad.py`: DotPad integration and rendering helpers.
- `src/dgc/games/`: game implementations.

## Build & Run
- `uv sync` — install deps.
- `uv pip install ../python/dist/dotpad-0.1.0-py3-none-any.whl` — install DotPad wrapper.
- `uv run dgc` — launch the app.

## Coding Style
- Python: 4-space indentation, snake_case functions, PascalCase classes.
- Docstrings use Google style.

## Testing
- Manual testing with DotPad hardware is required.
- Verify both UI and DotPad output for each game.
