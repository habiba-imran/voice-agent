"""Numeric SDK metrics and credential redaction; no transcript or recording sink."""

from __future__ import annotations

import json
import logging
import math
import traceback

from pydantic import SecretStr

from .settings import Settings

METRIC_FIELDS = (
    "duration",
    "ttft",
    "ttfb",
    "end_of_utterance_delay",
    "transcription_delay",
    "prompt_tokens",
    "completion_tokens",
    "prompt_cached_tokens",
    "tokens_per_second",
    "characters_count",
    "audio_duration",
    "cancelled",
)


class CredentialFilter(logging.Filter):
    def __init__(self, values: list[str]):
        super().__init__()
        self.values = tuple(value for value in values if value)

    def clean(self, value: str) -> str:
        for secret in self.values:
            value = value.replace(secret, "<redacted>")
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.clean(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = self.clean("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        for name, value in list(record.__dict__.items()):
            if name.startswith("lk.pii.") or name in {"prompt", "instructions", "transcript"}:
                record.__dict__[name] = "<omitted>"
            else:
                record.__dict__[name] = self.clean_value(value)
        return True

    def clean_value(self, value):
        if isinstance(value, str):
            return self.clean(value)
        if isinstance(value, BaseException):
            return type(value).__name__
        if isinstance(value, dict):
            return {
                key: "<omitted>"
                if key in {"prompt", "transcript", "instructions"} or str(key).startswith("lk.pii.")
                else self.clean_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return type(value)(self.clean_value(item) for item in value)
        return value


def protect_logging(settings: Settings) -> None:
    values = [
        value.get_secret_value() if isinstance(value, SecretStr) else value
        for _, value in settings.credentials
    ]
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=settings.runtime.log_level)
    for handler in root.handlers:
        for existing in list(handler.filters):
            if isinstance(existing, CredentialFilter):
                handler.removeFilter(existing)
        handler.addFilter(CredentialFilter(values))


def log_metric(metric, logger: logging.Logger) -> None:
    record = {"event": "provider_metric", "kind": type(metric).__name__}
    for name in METRIC_FIELDS:
        value = getattr(metric, name, None)
        if isinstance(value, (int, float, bool)) and math.isfinite(value):
            record[name] = value
    # Component metrics are diagnostics, not a caller-heard E2E measurement.
    logger.info(json.dumps(record, allow_nan=False))
