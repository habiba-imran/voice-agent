from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

from voiceagent.telemetry import CredentialFilter, log_metric


def test_log_redaction_covers_exception_and_nested_metadata():
    try:
        raise ValueError("synthetic-private-key")
    except ValueError:
        import sys

        record = logging.LogRecord(
            "test",
            logging.ERROR,
            "synthetic.py",
            1,
            "failed %s",
            ("synthetic-private-key",),
            sys.exc_info(),
        )
    record.details = {"nested": ["synthetic-private-key"], "prompt": "private prompt"}
    redact = CredentialFilter(["synthetic-private-key"])
    assert redact.filter(record)
    assert "synthetic-private-key" not in logging.Formatter().format(record)
    assert record.details == {"nested": ["<redacted>"], "prompt": "<omitted>"}


def test_only_finite_numeric_metric_fields_are_logged():
    logger = Mock()
    metric = SimpleNamespace(
        ttft=0.2, ttfb=float("nan"), prompt_tokens=12, transcript="private", api_key="private"
    )
    log_metric(metric, logger)
    record = json.loads(logger.info.call_args.args[0])
    assert record["ttft"] == 0.2  # Synthetic test data, not a measured provider latency.
    assert "ttfb" not in record and "transcript" not in record and "api_key" not in record


def test_native_interruption_metrics_keep_counts_without_payloads():
    from livekit.agents.metrics import InterruptionMetrics

    logger = Mock()
    log_metric(
        InterruptionMetrics(
            timestamp=0,
            label="synthetic",
            total_duration=0.2,
            prediction_duration=0.1,
            detection_delay=0.2,
            num_interruptions=1,
            num_backchannels=2,
            num_requests=3,
        ),
        logger,
    )
    record = json.loads(logger.info.call_args.args[0])
    assert record["num_interruptions"] == 1
    assert record["num_backchannels"] == 2
    assert record["num_requests"] == 3
    assert record["detection_delay"] == 0.2  # Synthetic fixture, not provider timing.
