"""Simple game sound playback wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import miniaudio
except Exception:  # pragma: no cover - optional runtime dependency
    miniaudio = None


class SoundManager:
    """Best-effort sound playback for short game effects."""

    def __init__(self) -> None:
        self._enabled = True
        self._loaded = False
        self._devices: list[object] = []
        self._base = self._resolve_sounds_dir()
        self._files = {
            "win": self._base / "win.ogg",
            "lose": self._base / "lose.ogg",
            "move1": self._base / "move1.ogg",
            "move2": self._base / "move2.ogg",
            "fire": self._base / "fire.ogg",
            "hit": self._base / "hit.ogg",
            "place": self._base / "place.ogg",
            "select": self._base / "select.ogg",
        }
        self._load()

    @staticmethod
    def _resolve_sounds_dir() -> Path:
        """Resolve sounds path for source and PyInstaller runs."""
        if getattr(sys, "frozen", False):
            base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
            return base / "assets" / "sounds"
        # src/dgc/sound.py -> project root is parents[2]
        return Path(__file__).resolve().parents[2] / "assets" / "sounds"

    @property
    def enabled(self) -> bool:
        """Return current mute state."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Enable or mute sound output."""
        self._enabled = enabled

    def toggle(self) -> bool:
        """Toggle mute state; return new state."""
        self._enabled = not self._enabled
        return self._enabled

    def _load(self) -> None:
        if miniaudio is None:
            return
        try:
            self._loaded = any(path.exists() for path in self._files.values())
        except Exception:
            self._loaded = False

    def play(self, event: str) -> None:
        """Play a one-shot sound event if available."""
        if not self._enabled or not self._loaded or miniaudio is None:
            return
        path = self._files.get(event)
        if path is None or not path.exists():
            return
        try:
            # Keep recent device refs alive so one-shots can finish.
            if len(self._devices) > 24:
                self._devices = self._devices[-24:]
            device = miniaudio.PlaybackDevice()
            device.start(miniaudio.stream_file(str(path)))
            self._devices.append(device)
        except Exception:
            return
