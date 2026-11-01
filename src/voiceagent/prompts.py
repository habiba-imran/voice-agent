"""Read a bounded UTF-8 prompt exactly once for each new session."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .settings import ConfigurationError, Settings


@dataclass(frozen=True)
class PromptSnapshot:
    text: str
    sha256: str
    byte_length: int


def load_prompt(path: Path, *, max_bytes: int) -> PromptSnapshot:
    try:
        # Read bounded bytes even if a file grows while it is being read.
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
    except (OSError, ValueError):
        raise ConfigurationError("Prompt file is missing or unreadable") from None
    if len(raw) > max_bytes:
        raise ConfigurationError("Prompt exceeds limits.max_prompt_bytes")
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
    except UnicodeError:
        raise ConfigurationError("Prompt must be valid UTF-8") from None
    if not text:
        raise ConfigurationError("Prompt must not be empty")
    if "\x00" in text:
        raise ConfigurationError("Prompt must not contain NUL characters")
    normalized = text.encode("utf-8")
    return PromptSnapshot(text, hashlib.sha256(normalized).hexdigest(), len(normalized))


def session_prompt(settings: Settings) -> PromptSnapshot:
    """A snapshot is immutable; prompt edits take effect on the next session."""
    return load_prompt(settings.prompt_path, max_bytes=settings.limits.max_prompt_bytes)
