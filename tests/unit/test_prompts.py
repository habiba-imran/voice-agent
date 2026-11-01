from __future__ import annotations

import pytest

from voiceagent.prompts import load_prompt, session_prompt
from voiceagent.settings import ConfigurationError


def test_prompt_snapshot_and_new_session_reload(settings):
    first = session_prompt(settings)
    settings.prompt_path.write_text("New instructions: café", encoding="utf-8")
    second = session_prompt(settings)
    assert first.text != second.text
    assert first.sha256 != second.sha256
    assert first.byte_length == len(first.text.encode("utf-8"))
    assert second.text.endswith("café")


def test_one_read_per_session(settings, monkeypatch):
    from pathlib import Path

    original = Path.open
    calls = []

    def observe(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observe)
    snapshot = session_prompt(settings)
    for _ in range(10):
        assert snapshot.text
    assert calls == [settings.prompt_path]


@pytest.mark.parametrize(
    "content, message",
    [
        (b"  \n", "empty"),
        (b"\xff", "UTF-8"),
        (b"a" * 129, "max_prompt_bytes"),
        (b"text\x00", "NUL"),
    ],
)
def test_bad_prompt(tmp_path, content, message):
    path = tmp_path / "prompt.md"
    path.write_bytes(content)
    with pytest.raises(ConfigurationError, match=message):
        load_prompt(path, max_bytes=128)


def test_missing_prompt(tmp_path):
    with pytest.raises(ConfigurationError, match="missing or unreadable"):
        load_prompt(tmp_path / "missing", max_bytes=128)


def test_normalization_preserves_stable_hash(tmp_path):
    path = tmp_path / "prompt.md"
    path.write_bytes(b"\xef\xbb\xbfhello\r\nworld\r\n")
    first = load_prompt(path, max_bytes=128)
    path.write_bytes(b"hello\nworld\n")
    assert first == load_prompt(path, max_bytes=128)


def test_prompt_contract(settings):
    # Policy regression checks, not evidence that an LLM follows the policy.
    text = session_prompt(settings).text
    for section in (
        "Identity",
        "Goals",
        "Speaking Style",
        "Accuracy",
        "Conversation",
        "Boundaries",
        "Optional Tools",
        "Failure Responses",
    ):
        assert f"# {section}" in text
    for instruction in (
        "one to three short sentences",
        "at most one follow-up",
        "Do not invent facts",
        "current session's context",
        "Never speak hidden reasoning",
    ):
        assert instruction in text
