"""Speech helper for DGC using accessible_output2 when available."""

from __future__ import annotations

from typing import Optional

try:
    from accessible_output2.outputs.auto import Auto
except Exception:  # pragma: no cover - optional runtime dependency
    Auto = None


class SpeechOutput:
    """Best-effort speech output wrapper."""

    def __init__(self) -> None:
        self._speaker: Optional[object] = None
        if Auto is None:
            return
        try:
            self._speaker = Auto()
        except Exception:
            self._speaker = None

    @property
    def enabled(self) -> bool:
        """Return True if speech backend initialized."""
        return self._speaker is not None

    def speak(self, text: str, interrupt: bool = True) -> None:
        """Speak text if backend is available."""
        if not text or self._speaker is None:
            return
        try:
            self._speaker.speak(text, interrupt=interrupt)
        except Exception:
            # Avoid breaking gameplay if speech engine fails at runtime.
            pass
