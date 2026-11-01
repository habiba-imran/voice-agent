"""Offline configuration commands; LiveKit CLI is imported only for worker modes."""

from __future__ import annotations

import argparse
import json
import sys

from .prompts import session_prompt
from .settings import ConfigurationError, load_settings


def main() -> None:
    if len(sys.argv) == 1 or sys.argv[1] in {"--help", "-h"}:
        parser = argparse.ArgumentParser(description="Direct-provider LiveKit voice worker")
        parser.add_argument(
            "command", nargs="?", choices=["config", "validate", "start", "dev", "console"]
        )
        parser.epilog = (
            "start/dev use the installed LiveKit module CLI. dev has no hot reload. "
            "console requires a LiveKit CLI TCP driver. Provider runs require approval."
        )
        parser.print_help()
        return
    if len(sys.argv) > 1 and sys.argv[1] in {"config", "validate"}:
        parser = argparse.ArgumentParser(description="Offline VoiceAgent configuration checks")
        parser.add_argument("command", choices=["config", "validate"])
        parser.add_argument("--config-path")
        parser.add_argument("--mode", choices=["console", "room"], default="room")
        args = parser.parse_args()
        try:
            settings = load_settings(config_path=args.config_path)
            if args.command == "config":
                print(json.dumps(settings.redacted(), indent=2))
            else:
                settings.require_credentials(room=args.mode == "room")
                prompt = session_prompt(settings)
                print(f"Configuration valid; prompt sha256={prompt.sha256}")
        except ConfigurationError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(2) from None
        return
    from .runtime import run

    try:
        run()
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
