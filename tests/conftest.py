from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from voiceagent.settings import PROJECT_ROOT, load_settings


@pytest.fixture
def project(tmp_path: Path) -> Path:
    for name in ("config.example.yaml", "prompt.md"):
        shutil.copy2(PROJECT_ROOT / name, tmp_path / name)
    return tmp_path


@pytest.fixture
def settings(project):
    return load_settings(project_root=project, environ={})
