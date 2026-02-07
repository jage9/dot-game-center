"""Simple game sound playback wrapper."""

from __future__ import annotations

from array import array
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
            "tie": self._base / "tie.ogg",
            "move1": self._base / "move1.ogg",
            "move2": self._base / "move2.ogg",
            "fire": self._base / "fire.ogg",
            "hit": self._base / "hit.ogg",
            "place": self._base / "place.ogg",
            "select": self._base / "select.ogg",
        }
        self._volumes = {
            "fire": 0.5,
            "hit": 0.5,
            "place": 0.5,
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
            volume = self._volumes.get(event, 1.0)
            # Keep recent device refs alive so one-shots can finish.
            if len(self._devices) > 24:
                self._devices = self._devices[-24:]
            device = miniaudio.PlaybackDevice()
            stream = self._scaled_stream(str(path), volume)
            next(stream)
            device.start(stream)
            self._devices.append(device)
        except Exception:
            return

    @staticmethod
    def _scale_pcm(chunk: object, volume: float) -> object:
        """Scale SIGNED16 PCM chunks by volume."""
        if volume >= 0.999:
            return chunk
        if not isinstance(chunk, array) or chunk.typecode != "h":
            return chunk
        # Clamp to int16 range after gain.
        return array("h", (max(-32768, min(32767, int(sample * volume))) for sample in chunk))

    @staticmethod
    def _scaled_stream(filename: str, volume: float):
        """Stream PCM from file and apply software gain safely."""
        source = miniaudio.stream_file(filename)
        required_frames = yield
        silence = None
        while True:
            try:
                if required_frames is None:
                    chunk = next(source)
                else:
                    chunk = source.send(required_frames)
                if silence is None and isinstance(chunk, array):
                    silence = array(chunk.typecode, [0] * len(chunk))
                required_frames = yield SoundManager._scale_pcm(chunk, volume)
            except StopIteration:
                if silence is None:
                    silence = array("h")
                required_frames = yield silence
