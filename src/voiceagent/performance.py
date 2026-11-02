"""Bounded, numeric local observations. No conversations, audio, or remote exporter."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter, OrderedDict, deque
from uuid import uuid4

from livekit.agents import APITimeoutError
from livekit.agents.voice import io

METRICS = {
    "sdk_eou_s",
    "sdk_stt_finalization_s",
    "sdk_llm_ttft_s",
    "sdk_tts_ttfb_s",
    "sdk_llm_duration_s",
    "sdk_tts_duration_s",
    "sdk_playback_latency_s",
    "sdk_e2e_s",
    "sdk_llm_first_sentence_s",
    "sdk_stt_acquire_s",
    "sdk_tts_acquire_s",
    "sdk_prompt_tokens",
    "provider_llm_ttft_s",
    "provider_tts_ttfb_s",
    "sdk_completion_tokens",
    "positive_cached_tokens",
    "detected_end_to_final_event_s",
    "eot_hook_to_sink_accept_s",
    "eot_hook_to_handle_done_s",
    "speech_handle_lifecycle_s",
}


def identifier(value):
    return hashlib.sha256(value.encode()).hexdigest()[:16] if isinstance(value, str) else None


def distribution(values):
    """Linear-interpolated percentiles over available samples, never invented zeroes."""
    ordered = sorted(values)

    def percentile(fraction):
        position = (len(ordered) - 1) * fraction
        low = math.floor(position)
        return ordered[low] + (ordered[math.ceil(position)] - ordered[low]) * (position - low)

    return {
        "sample_count": len(ordered),
        "p50": percentile(0.5) if ordered else None,
        "p95": percentile(0.95) if ordered else None,
    }


class PerformanceObserver:
    def __init__(self, settings, *, clock=time.perf_counter, logger=None, origin="runtime"):
        self.clock, self.logger, self.origin = clock, logger, origin
        self.session_id = uuid4().hex
        self.window = settings.latency.metric_window
        self.config = {
            "stt": settings.stt.model,
            "turn_detection": settings.listening.turn_detection,
            "humanization": settings.humanization.enabled,
            "preemptive_llm": settings.latency.preemptive_llm,
        }
        self.series = {}
        self.counts = Counter()
        self.totals = Counter()
        self.usage_totals = Counter()
        self.active = OrderedDict()
        self.listeners = []
        self.detected_end = None
        self.pending_eot = None
        self.session = None

    def emit(self, event, **fields):
        if self.logger:
            self.logger.info(
                json.dumps(
                    {"event": event, "session_id": self.session_id, **fields}, allow_nan=False
                )
            )

    def sample(self, name, value, outcome="observed"):
        if name not in METRICS or outcome not in {
            "observed",
            "completed",
            "interrupted",
            "cancelled",
            "failed",
        }:
            return
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            return
        key = (name, outcome)
        self.series.setdefault(key, deque(maxlen=self.window)).append(value)
        self.totals[key] += 1

    def attach(self, session):
        self.session = session
        callbacks = {
            "speech_created": self.speech_created,
            "user_state_changed": self.user_state,
            "user_input_transcribed": self.transcribed,
            "conversation_item_added": self.item_added,
            "metrics_collected": self.metric,
            "error": self.error,
            "agent_false_interruption": self.false_interruption,
        }
        for event, callback in callbacks.items():
            session.on(event, callback)
            self.listeners.append((event, callback))

    def wrap_output(self):
        output = getattr(getattr(self.session, "output", None), "audio", None)
        if isinstance(output, io.AudioOutput):
            self.session.output.audio = ObservedAudioOutput(output, self)
        else:
            self.counts["output_observation_unavailable"] += 1

    def detach(self):
        off = getattr(self.session, "off", None)
        if callable(off):
            for event, callback in self.listeners:
                off(event, callback)
        self.listeners.clear()
        for entry in self.active.values():
            entry["handle"].remove_done_callback(self.speech_done)
        self.active.clear()

    def user_state(self, event):
        if event.new_state == "speaking":
            self.detected_end = None
            self.pending_eot = None
        elif event.old_state == "speaking" and event.new_state == "listening":
            self.detected_end = self.clock()

    def transcribed(self, event):
        if event.is_final:
            self.counts["stt_final_events"] += 1
            if self.detected_end is not None:
                self.sample("detected_end_to_final_event_s", self.clock() - self.detected_end)

    def end_of_turn(self):
        # Public Agent.on_user_turn_completed entry, not a reconstructed acoustic timestamp.
        self.pending_eot = self.clock()
        self.counts["eot_hooks"] += 1

    def speech_created(self, event):
        handle = event.speech_handle
        if handle.id in self.active:
            return
        if len(self.active) >= self.window:
            _, previous = self.active.popitem(last=False)
            previous["handle"].remove_done_callback(self.speech_done)
            self.counts["evicted_active_handles"] += 1
        self.active[handle.id] = {
            "handle": handle,
            "start": self.clock(),
            "eot": None,
            "first_frame": None,
            "failed": False,
        }
        self.counts["speech_handles"] += 1
        handle.add_done_callback(self.speech_done)
        self.emit("speech_created", speech_id=identifier(handle.id))

    def claim_eot(self, entry):
        if entry["eot"] is None and entry["handle"].scheduled and self.pending_eot is not None:
            entry["eot"], self.pending_eot = self.pending_eot, None

    def frame_accepted(self, handle):
        entry = self.active.get(handle.id) if handle is not None else None
        if entry is None or entry["first_frame"] is not None:
            return
        self.claim_eot(entry)
        entry["first_frame"] = self.clock()
        self.emit("first_sink_frame", speech_id=identifier(handle.id))

    def speech_done(self, handle):
        entry = self.active.pop(handle.id, None)
        if entry is None:
            return
        self.claim_eot(entry)
        outcome = (
            "failed"
            if entry["failed"]
            else "cancelled"
            if not handle.scheduled
            else "interrupted"
            if handle.interrupted
            else "completed"
        )
        now = self.clock()
        self.counts[f"speech_{outcome}"] += 1
        self.sample("speech_handle_lifecycle_s", now - entry["start"], outcome)
        if entry["eot"] is not None:
            self.sample("eot_hook_to_handle_done_s", now - entry["eot"], outcome)
            if entry["first_frame"] is not None:
                self.sample(
                    "eot_hook_to_sink_accept_s", entry["first_frame"] - entry["eot"], outcome
                )
        self.emit("speech_done", speech_id=identifier(handle.id), outcome=outcome)

    def item_added(self, event):
        item = event.item
        fields = getattr(item, "metrics", None) or {}
        outcome = (
            "observed"
            if getattr(item, "role", None) == "user"
            else ("interrupted" if getattr(item, "interrupted", False) else "completed")
        )
        values = {}
        for key, metric in {
            "end_of_turn_delay": "sdk_eou_s",
            "transcription_delay": "sdk_stt_finalization_s",
            "llm_node_ttft": "sdk_llm_ttft_s",
            "tts_node_ttfb": "sdk_tts_ttfb_s",
            "llm_node_ttfs": "sdk_llm_first_sentence_s",
            "playback_latency": "sdk_playback_latency_s",
            "e2e_latency": "sdk_e2e_s",
        }.items():
            value = fields.get(key)
            self.sample(metric, value, outcome)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                values[metric] = value
        # Never serialize the ChatMessage, its content, or unvalidated metric metadata.
        self.emit(
            "turn_metrics",
            item_id=identifier(getattr(item, "id", None)),
            outcome=outcome,
            values=values,
            request_ids=[
                identifier(value)
                for value in fields.get("provider_request_ids", [])[:16]
                if isinstance(value, str)
            ],
        )

    def metric(self, event):
        metric = event.metrics
        kind = getattr(metric, "type", None)
        outcome = "cancelled" if getattr(metric, "cancelled", False) else "completed"
        if kind == "llm_metrics":
            self.sample("sdk_llm_duration_s", metric.duration, outcome)
            self.sample("provider_llm_ttft_s", getattr(metric, "ttft", None), outcome)
            # Node TTFT is taken from ChatMessage metrics to avoid mixing/double counting.
            for field in ("prompt_tokens", "completion_tokens"):
                self.sample(f"sdk_{field}", getattr(metric, field, None), outcome)
                value = getattr(metric, field, None)
                if type(value) is int and value >= 0:
                    self.usage_totals[field] += value
            cached = getattr(metric, "prompt_cached_tokens", None)
            if type(cached) is int and cached > 0:
                self.sample("positive_cached_tokens", cached, outcome)
                self.usage_totals["positive_cached_tokens"] += cached
            else:
                self.counts["cache_reporting_unknown_or_zero"] += 1
            self.counts["llm_cancelled_requests"] += int(bool(getattr(metric, "cancelled", False)))
        elif kind == "tts_metrics":
            self.sample("sdk_tts_duration_s", metric.duration, outcome)
            self.sample("provider_tts_ttfb_s", getattr(metric, "ttfb", None), outcome)
            self.counts["tts_cancelled_requests"] += int(bool(getattr(metric, "cancelled", False)))
        if kind in {"stt_metrics", "tts_metrics"}:
            prefix = "stt" if kind == "stt_metrics" else "tts"
            self.sample(f"sdk_{prefix}_acquire_s", getattr(metric, "acquire_time", None))
            reused = getattr(metric, "connection_reused", None)
            if type(reused) is bool:
                self.counts[f"{prefix}_connection_observations"] += 1
                self.counts[f"{prefix}_reused_connections"] += int(reused)
        if kind in {"llm_metrics", "tts_metrics", "stt_metrics"}:
            self.emit(
                "provider_request",
                kind=kind,
                speech_id=identifier(getattr(metric, "speech_id", None)),
                request_id=identifier(getattr(metric, "request_id", None)),
                outcome=outcome,
            )

    def error(self, event):
        error = event.error
        inner = getattr(error, "error", error)
        timed_out = isinstance(inner, (TimeoutError, APITimeoutError))
        recoverable = bool(getattr(error, "recoverable", False))
        status = getattr(inner, "status_code", None)
        self.counts["provider_errors"] += 1
        self.counts["provider_timeouts"] += int(timed_out)
        self.counts["recoverable_error_events"] += int(recoverable)
        handle = getattr(self.session, "current_speech", None)
        if not recoverable and handle is not None and handle.id in self.active:
            self.active[handle.id]["failed"] = True
        self.emit(
            "provider_error",
            timeout=timed_out,
            recoverable=recoverable,
            status_code=status if type(status) is int and 100 <= status <= 599 else None,
        )

    def false_interruption(self, event):
        self.counts["false_interruptions"] += 1
        self.counts["false_interruptions_resumed"] += int(event.resumed)

    def report(self):
        observed = {name for name, _ in self.series}
        return {
            "schema_version": 1,
            "origin": self.origin,
            "session_id": self.session_id,
            "config": self.config,
            "clock": {
                "local_intervals": "monotonic_perf_counter",
                "sdk_intervals": "reported unchanged; some SDK anchors use wall time",
            },
            "caller_heard_latency": None,
            "retry_attempt_count": None,
            "cache_zero_provenance": "SDK cannot distinguish unreported from zero",
            "sample_window": self.window,
            "counts": dict(self.counts),
            "sdk_usage_totals": dict(self.usage_totals),
            "unobserved": sorted(METRICS - observed),
            "metrics": {
                f"{name}/{outcome}": {
                    **distribution(values),
                    "total_count": self.totals[(name, outcome)],
                }
                for (name, outcome), values in sorted(self.series.items())
            },
        }


class ObservedAudioOutput(io.AudioOutput):
    """Transparent sink wrapper: observes acceptance, never edits/queues audio."""

    def __init__(self, sink, observer):
        super().__init__(
            label="voiceagent-metrics",
            next_in_chain=sink,
            sample_rate=sink.sample_rate,
            capabilities=io.AudioOutputCapabilities(pause=True),
        )
        self.observer = observer

    async def capture_frame(self, frame):
        # Capture identity before the await: downstream backpressure may span a turn change.
        handle = self.observer.session.current_speech
        await super().capture_frame(frame)
        await self.next_in_chain.capture_frame(frame)
        self.observer.frame_accepted(handle)

    def flush(self):
        super().flush()
        self.next_in_chain.flush()

    def clear_buffer(self):
        self.next_in_chain.clear_buffer()
