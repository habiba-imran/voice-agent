"""Root entrypoint for local and LiveKit worker commands after uv sync --locked."""

import sys
from pathlib import Path

# SDK discovery adds this directory ahead of the host CWD, but editable src is later
# on sys.path. Prefer this copy's package even if the host also has voiceagent.py.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from voiceagent.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
else:
    # Current LiveKit CLI discovery requires a global AgentServer object.
    # Registration alone creates no provider clients and makes no provider requests.
    from voiceagent.runtime import build_server
    from voiceagent.settings import load_settings

    server = build_server(load_settings())
