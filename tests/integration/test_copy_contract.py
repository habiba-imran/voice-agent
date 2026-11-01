"""Offline Git/Docker policy and clean, nested editable-install verification."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from voiceagent.settings import PROJECT_ROOT

pytestmark = pytest.mark.integration


def test_git_and_build_exclusions():
    # pathspec checks the glob subset used here; actual Docker context inspection is a later gate.
    import pathspec

    git_rules = pathspec.GitIgnoreSpec.from_lines(
        (PROJECT_ROOT / ".gitignore").read_text().splitlines()
    )
    docker_rules = pathspec.GitIgnoreSpec.from_lines(
        (PROJECT_ROOT / ".dockerignore").read_text().splitlines()
    )
    for name in (
        ".env",
        ".env.local",
        ".env.production",
        "livekit.toml",
        "livekit.other.toml",
        ".venv/Scripts/python.exe",
        "evals/results/synthetic.wav",
    ):
        assert git_rules.match_file(name), name
        assert docker_rules.match_file(name), name
    assert not git_rules.match_file(".env.example")
    assert docker_rules.match_file(".env.example")
    for name in (
        "agent.py",
        "prompt.md",
        "config.example.yaml",
        "uv.lock",
        "src/voiceagent/settings.py",
    ):
        assert not git_rules.match_file(name), name
        assert not docker_rules.match_file(name), name


def test_copy_editable_install_and_foreign_cwd(tmp_path: Path):
    """Create a second venv offline; do not copy developer credentials or the original venv."""
    host = tmp_path / "unrelated host"
    destination = host / "nested" / "voiceagent"
    destination.mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "uv.lock",
        "agent.py",
        "prompt.md",
        "config.example.yaml",
        ".python-version",
        ".gitignore",
        ".dockerignore",
    ):
        shutil.copy2(PROJECT_ROOT / name, destination / name)
    shutil.copytree(
        PROJECT_ROOT / "src",
        destination / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        PROJECT_ROOT / "tests" / "unit",
        destination / "tests" / "unit",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(PROJECT_ROOT / "tests" / "conftest.py", destination / "tests" / "conftest.py")
    # The parent deliberately contains conflicting app imports and secrets. Neither is used.
    (host / "voiceagent.py").write_text("raise RuntimeError('wrong host import')\n")
    (host / ".env").write_text("GROQ_API_KEY=synthetic-host-credential-must-not-load\n")
    environment = dict(os.environ)
    for key in list(environment):
        if key.startswith(("VOICEAGENT_", "LIVEKIT_", "UV_")) or key in {
            "GROQ_API_KEY",
            "DEEPGRAM_API_KEY",
            "CARTESIA_API_KEY",
            "PYTHONPATH",
            "VIRTUAL_ENV",
        }:
            environment.pop(key)
    environment["UV_PYTHON"] = sys.executable
    cache = PROJECT_ROOT / ".uv-cache"
    if not cache.exists():
        # In fresh CI uv uses its normal cache populated by the required uv sync --locked step.
        cache_result = subprocess.run(
            ["uv", "cache", "dir"],
            capture_output=True,
            text=True,
            env=environment,
            check=True,
            timeout=30,
        )
        cache = Path(cache_result.stdout.strip())
    installed = subprocess.run(
        ["uv", "sync", "--locked", "--offline", "--cache-dir", str(cache)],
        cwd=destination,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert installed.returncode == 0, installed.stderr
    executable = destination / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    result = subprocess.run(
        [str(executable), str(destination / "agent.py"), "config"],
        cwd=host,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["credentials"]["groq_api_key"] == "<unset>"
    assert Path(data["prompt_path"]) == destination / "prompt.md"
    # Prompt edits take effect from the copy, independently of original module/CWD.
    (destination / "prompt.md").write_text("Synthetic copied prompt revision", encoding="utf-8")
    inspect_copy = subprocess.run(
        [
            str(executable),
            "-c",
            "from voiceagent.settings import load_settings; "
            "from voiceagent.prompts import session_prompt; "
            "print(session_prompt(load_settings()).text)",
        ],
        cwd=destination,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert inspect_copy.returncode == 0, inspect_copy.stderr
    assert inspect_copy.stdout.strip() == "Synthetic copied prompt revision"
    # Restore the generic policy before running the independent copy's foundation suite.
    shutil.copy2(PROJECT_ROOT / "prompt.md", destination / "prompt.md")
    suite = subprocess.run(
        [str(executable), "-m", "pytest", "-q", "tests/unit"],
        cwd=destination,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert suite.returncode == 0, suite.stdout + suite.stderr
