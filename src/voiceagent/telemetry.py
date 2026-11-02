"""Numeric SDK metrics and credential redaction; no transcript or recording sink."""

from __future__ import annotations

import json
import logging
import math
import threading
from itertools import islice

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
    "total_duration",
    "prediction_duration",
    "detection_delay",
    "num_interruptions",
    "num_backchannels",
    "num_requests",
)

SENSITIVE_FIELDS = {
    "prompt",
    "instructions",
    "transcript",
    "messages",
    "content",
    "text",
    "body",
    "request",
    "response",
    "headers",
    "authorization",
    "api_key",
    "api_secret",
    "access_token",
    "token",
    "chat_ctx",
    "tool_arguments",
    "participant_identity",
    "livekit_url",
}
RESERVED_FIELDS = frozenset(logging.makeLogRecord({}).__dict__)
SDK_LOGGERS = (
    "livekit",
    "openai",
    "groq",
    "httpx",
    "httpcore",
    "aiohttp",
    "deepgram",
    "cartesia",
    "websockets",
    "urllib3",
    "asyncio",
)


def sensitive(name):
    lowered = str(name).lower()
    return (
        lowered in SENSITIVE_FIELDS
        or lowered.startswith("lk.pii.")
        or lowered.endswith(("_api_key", "_api_secret"))
    )


class CredentialFilter(logging.Filter):
    def __init__(self, values: list[str]):
        super().__init__()
        self.values = ()
        self.lock = threading.Lock()
        self.add_values(values)

    def add_values(self, values):
        with self.lock:
            combined = set(self.values).union(value for value in values if value)
            if len(combined) > 64:
                raise ValueError(
                    "Credential log filter capacity exceeded; restart worker for new settings"
                )
            # Replace longer credentials first when one is a prefix of another.
            self.values = tuple(sorted(combined, key=len, reverse=True))

    def clean(self, value: str) -> str:
        for secret in self.values:
            value = value.replace(secret, "<redacted>")
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        sdk = record.name.split(".", 1)[0] in SDK_LOGGERS
        if sdk:
            # SDK/provider exceptions may embed raw requests or TTS input in their message.
            record.msg = "sdk_event"
        else:
            record.args = self.clean_value(record.args)
            if isinstance(record.msg, dict):
                record.msg = self.clean_value(record.msg)
            else:
                record.msg = self.clean(record.getMessage())
        record.args = ()
        if record.exc_info:
            record.exc_text = record.exc_info[0].__name__
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = "<exception details omitted>"
        record.stack_info = None
        for name, value in list(record.__dict__.items()):
            if sensitive(name):
                record.__dict__[name] = "<omitted>"
            elif (
                sdk
                and name not in RESERVED_FIELDS
                and type(value) not in (int, float, bool, type(None))
            ):
                record.__dict__[name] = "<omitted>"
            else:
                record.__dict__[name] = self.clean_value(value)
        return True

    def clean_value(self, value, depth=0):
        if depth > 6:
            return "<omitted>"
        if isinstance(value, str):
            return self.clean(value)
        if isinstance(value, BaseException):
            return type(value).__name__
        if isinstance(value, dict):
            return {
                self.clean(str(key)): "<omitted>"
                if sensitive(key)
                else self.clean_value(item, depth + 1)
                for key, item in islice(value.items(), 64)
            }
        if isinstance(value, (list, tuple)):
            return type(value)(self.clean_value(item, depth + 1) for item in value[:64])
        if type(value) in (int, float, bool, type(None)):
            return value
        return type(value).__name__


def protect_logging(settings: Settings) -> None:
    values = [
        value.get_secret_value() if isinstance(value, SecretStr) else value
        for _, value in settings.credentials
    ]
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=settings.runtime.log_level)
    for handler in root.handlers:
        existing = next(
            (item for item in handler.filters if isinstance(item, CredentialFilter)), None
        )
        if existing is None:
            handler.addFilter(CredentialFilter(values))
        else:
            existing.add_values(values)


def log_metric(metric, logger: logging.Logger) -> None:
    record = {"event": "provider_metric", "kind": type(metric).__name__}
    for name in METRIC_FIELDS:
        value = getattr(metric, name, None)
        if isinstance(value, (int, float, bool)) and math.isfinite(value):
            record[name] = value
    # Component metrics are diagnostics, not a caller-heard E2E measurement.
    logger.info(json.dumps(record, allow_nan=False))
