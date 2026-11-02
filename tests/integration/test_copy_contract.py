"""Offline Git/Docker policy and clean, nested editable-install verification."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

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
        "console-recordings/session/transcript.json",
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
        "Dockerfile",
        "compose.yaml",
    ):
        shutil.copy2(PROJECT_ROOT / name, destination / name)
    # Only inert deployment metadata travels with a copy, never a real Cloud binding.
    for folder, name in (
        ("deploy", "livekit.toml.example"),
        ("docs", "CONTAINER_PINS.json"),
    ):
        (destination / folder).mkdir()
        shutil.copy2(PROJECT_ROOT / folder / name, destination / folder / name)
    shutil.copytree(
        PROJECT_ROOT / "src",
        destination / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(
        PROJECT_ROOT / "scripts",
        destination / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(PROJECT_ROOT / "tests" / "fixtures", destination / "tests" / "fixtures")
    # Copy only the non-secret prepared scenario template, never local evaluation artifacts.
    (destination / "evals").mkdir()
    shutil.copy2(
        PROJECT_ROOT / "evals" / "livekit_scenarios.yaml",
        destination / "evals" / "livekit_scenarios.yaml",
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
    configured_cache = os.environ.get("UV_CACHE_DIR")
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
    if configured_cache:
        cache = Path(configured_cache).resolve()
    else:
        # Use the cache selected by setup, not a stale directory left by earlier diagnostics.
        cache_result = subprocess.run(
            ["uv", "cache", "dir"],
            capture_output=True,
            text=True,
            env=environment,
            check=True,
            timeout=30,
        )
        cache = Path(cache_result.stdout.strip())
    executable = destination / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheelhouse = os.environ.get("VOICEAGENT_TEST_WHEELHOUSE")
    if wheelhouse:
        # A wheelhouse supplies dependencies on networks that cannot sustain large downloads.
        # Still build a new environment and validate every runtime artifact against uv.lock.
        requirements = destination / "locked-test-requirements.txt"
        bootstrap = [
            ["uv", "venv", "--python", sys.executable, str(destination / ".venv")],
            [
                "uv",
                "export",
                "--locked",
                "--offline",
                "--format",
                "requirements-txt",
                "--no-emit-project",
                "--output-file",
                str(requirements),
                "--quiet",
            ],
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(executable),
                "--offline",
                "--no-index",
                "--find-links",
                str(Path(wheelhouse).resolve()),
                "--require-hashes",
                "-r",
                str(requirements),
                "--link-mode",
                "copy",
            ],
        ]
        for command in bootstrap:
            prepared = subprocess.run(
                [*command, "--cache-dir", str(cache)],
                cwd=destination,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
            )
            assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    install_command = [
        "uv",
        "sync",
        "--locked",
        "--offline",
        "--cache-dir",
        str(cache),
        "--link-mode",
        "copy",
    ]
    if wheelhouse:
        install_command += ["--find-links", str(Path(wheelhouse).resolve())]
    installed = subprocess.run(
        install_command,
        cwd=destination,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert installed.returncode == 0, installed.stderr
    discovered = subprocess.run(
        [
            str(executable),
            "-c",
            "from pathlib import Path; import importlib; "
            "from livekit.agents.cli.discover import get_import_data; "
            f"data=get_import_data(path=Path({str(destination / 'agent.py')!r})); "
            "mod=importlib.import_module(data.module_data.module_import_str); "
            "from livekit.agents import AgentServer; "
            "assert isinstance(getattr(mod,data.app_name),AgentServer); print(data.app_name)",
        ],
        cwd=host,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert discovered.returncode == 0, discovered.stderr
    assert discovered.stdout.strip() == "server"
    help_result = subprocess.run(
        [str(executable), str(destination / "agent.py"), "start", "--help"],
        cwd=host,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "--log-format" in help_result.stdout
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
    config_path = destination / "config.example.yaml"
    original_config = config_path.read_text(encoding="utf-8")
    copied_config = yaml.safe_load(original_config)
    copied_config["tts"]["speed"] = 1.1
    config_path.write_text(yaml.safe_dump(copied_config), encoding="utf-8")
    changed = subprocess.run(
        [str(executable), str(destination / "agent.py"), "config"],
        cwd=host,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert changed.returncode == 0, changed.stderr
    assert json.loads(changed.stdout)["tts"]["speed"] == 1.1
    config_path.write_text(original_config, encoding="utf-8")
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
        timeout=180,
    )
    assert suite.returncode == 0, suite.stdout + suite.stderr
