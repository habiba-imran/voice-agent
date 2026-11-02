"""Typed, network-free configuration with explicit, portable source precedence."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SECRET_NAMES = {
    "LIVEKIT_API_KEY": "livekit_api_key",
    "LIVEKIT_API_SECRET": "livekit_api_secret",
    "DEEPGRAM_API_KEY": "deepgram_api_key",
    "GROQ_API_KEY": "groq_api_key",
    "CARTESIA_API_KEY": "cartesia_api_key",
}


class ConfigurationError(ValueError):
    """Actionable configuration error whose message contains no input values."""


def livekit_url_diagnostics(value: str) -> dict[str, str]:
    """Bounded labels only; never return URL text, hostnames, ports or parser errors."""
    try:
        url = urlsplit(value)
        scheme = url.scheme if url.scheme in {"wss", "https", "ws", "http"} else "unsupported"
        hostname = url.hostname
    except ValueError:
        return {"livekit_url_scheme": "unparseable", "livekit_url_host_category": "unknown"}
    if not hostname:
        category = "unknown"
    else:
        try:
            loopback = ip_address(hostname).is_loopback
        except ValueError:
            loopback = hostname == "localhost"
        category = "loopback" if loopback else "non-loopback"
    return {"livekit_url_scheme": scheme, "livekit_url_host_category": category}


class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, frozen=True, allow_inf_nan=False
    )


class Credentials(Model):
    livekit_url: str = ""
    livekit_api_key: SecretStr = SecretStr("")
    livekit_api_secret: SecretStr = SecretStr("")
    deepgram_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    cartesia_api_key: SecretStr = SecretStr("")


class STTSettings(Model):
    model: Literal["nova-3", "flux-general-en"] = "nova-3"
    language: Literal["en"] = "en"
    keyterms: tuple[Annotated[str, Field(min_length=1, max_length=100)], ...] = ()
    eot_threshold: float | None = Field(default=None, ge=0.5, le=0.9)
    eager_eot_threshold: float | None = Field(default=None, ge=0.3, le=0.9)
    eot_timeout_ms: int | None = Field(default=None, ge=500, le=60000)


class LLMSettings(Model):
    model: Literal["openai/gpt-oss-20b"] = "openai/gpt-oss-20b"
    reasoning_effort: Literal["low", "medium", "high"] = "low"
    max_output_tokens: int = Field(default=256, ge=16, le=4096)
    temperature: float = Field(default=0.6, ge=0, le=2)
    history_messages: int = Field(default=24, ge=2, le=200)


class TTSSettings(Model):
    model: Literal["sonic-3"] = "sonic-3"
    voice_id: UUID | None = None
    language: Literal["en"] = "en"
    emotion: Literal["neutral", "calm", "content", "excited", "sympathetic"] = "neutral"
    speed: float = Field(default=1.0, ge=0.6, le=1.5)
    volume: float = Field(default=1.0, ge=0.5, le=2.0)


class VADSettings(Model):
    min_speech_duration: float = Field(default=0.05, ge=0.01, le=1)
    min_silence_duration: float = Field(default=0.55, ge=0.1, le=3)
    prefix_padding_duration: float = Field(default=0.5, ge=0, le=2)
    activation_threshold: float = Field(default=0.5, gt=0, lt=1)


class ListeningSettings(Model):
    turn_detection: Literal["vad", "semantic", "stt"] = "vad"
    endpointing_mode: Literal["fixed", "dynamic"] = "fixed"
    endpointing_alpha: float = Field(default=0.9, gt=0, lt=1)
    min_endpoint_delay: float = Field(default=0.5, ge=0, le=10)
    max_endpoint_delay: float = Field(default=3.0, ge=0, le=30)
    vad: VADSettings = Field(default_factory=VADSettings)

    @model_validator(mode="after")
    def ordered_delays(self) -> ListeningSettings:
        if self.min_endpoint_delay > self.max_endpoint_delay:
            raise ValueError("min_endpoint_delay must not exceed max_endpoint_delay")
        return self


class InterruptionSettings(Model):
    enabled: bool = True
    mode: Literal["vad", "adaptive"] = "vad"
    allow_cloud_inference: bool = False
    min_duration: float = Field(default=0.5, ge=0.1, le=5)
    min_words: int = Field(default=0, ge=0, le=10)
    false_interruption_timeout: float | None = Field(default=2.0, ge=0.1, le=10)
    resume_false_interruption: bool = True
    discard_audio_if_uninterruptible: bool = True
    backchannel_boundary: (
        tuple[Annotated[float, Field(ge=0, le=5)], Annotated[float, Field(ge=0, le=5)]] | None
    ) = (1.0, 1.0)

    @model_validator(mode="after")
    def explicit_cloud_opt_in(self) -> InterruptionSettings:
        if self.mode == "adaptive" and not self.allow_cloud_inference:
            raise ValueError("Adaptive interruption requires explicit allow_cloud_inference opt-in")
        return self


class LatencySettings(Model):
    preemptive_llm: bool = False
    preemptive_tts: Literal[False] = False
    metrics: bool = True
    metric_window: int = Field(default=256, ge=16, le=10000)


class HumanizationSettings(Model):
    enabled: bool = False
    default_style: Literal[
        "neutral", "conversational", "reassuring", "thoughtful", "curious", "enthusiastic"
    ] = "conversational"
    emotion: Literal[
        "auto",
        "neutral",
        "calm",
        "content",
        "excited",
        "sympathetic",
        "curious",
        "confident",
        "contemplative",
    ] = "auto"
    speed: float | None = Field(default=None, ge=0.6, le=1.5)
    volume: float | None = Field(default=None, ge=0.5, le=2)
    disfluencies: Literal["contextual", "off"] = "contextual"
    max_leading_fillers_per_turn: Literal[0, 1] = 1
    filler_cooldown_turns: int = Field(default=3, ge=1, le=20)
    pauses: Literal["punctuation"] = "punctuation"
    pace: Literal["baseline", "measured", "lively"] = "baseline"
    emotional_range: Literal["baseline"] = "baseline"
    markup: Literal[False] = False
    laughter: Literal[False] = False


class RuntimeSettings(Model):
    dispatch: Literal["auto", "explicit"] = "explicit"
    agent_name: str = Field(default="voiceagent", pattern=r"^[a-z][a-z0-9_-]{0,62}$")
    greeting: str | None = Field(default=None, max_length=500)
    max_session_seconds: float = Field(default=1800, ge=10, le=14400)
    idle_timeout_seconds: float = Field(default=120, ge=5, le=3600)
    hook_timeout_seconds: float = Field(default=2, gt=0, le=30)
    log_level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    startup_timeout_seconds: float = Field(default=30, ge=1, le=120)
    drain_timeout_seconds: float = Field(default=5, ge=0, le=30)
    shutdown_timeout_seconds: float = Field(default=10, ge=1, le=60)


class IdentitySettings(Model):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=500)


class GreetingSettings(Model):
    wait_for_playback_ready: bool = False
    mode: Literal["user_first", "custom", "dynamic"] = "user_first"
    text: str | None = Field(default=None, min_length=1, max_length=500)
    instructions: str = Field(
        default="Greet the participant in one short, natural sentence. Then listen.",
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def coherent_greeting(self):
        if self.wait_for_playback_ready and self.mode == "user_first":
            raise ValueError("Playback-ready greeting requires custom or dynamic mode")
        if self.mode == "custom" and (self.text is None or not self.text.strip()):
            raise ValueError("Custom greeting requires nonblank greeting.text")
        if self.mode != "custom" and self.text is not None:
            raise ValueError("greeting.text applies only to custom mode")
        return self


class EndingSettings(Model):
    enabled: bool = False
    detect_explicit: bool = False
    farewell_mode: Literal["custom", "generated", "none"] = "custom"
    farewell: str = Field(default="Goodbye!", min_length=1, max_length=500)
    instructions: str = Field(
        default="Say a brief, polite farewell in one sentence. Do not ask a question.",
        min_length=1,
        max_length=500,
    )
    timeout_seconds: float = Field(default=10, ge=1, le=30)


class Limits(Model):
    request_timeout_seconds: float = Field(default=10, gt=0, le=60)
    max_retries: Literal[0] = 0
    retry_interval_seconds: float = Field(default=2, ge=1, le=30)
    max_prompt_bytes: int = Field(default=32768, ge=128, le=262144)
    max_metadata_bytes: int = Field(default=2048, ge=0, le=8192)
    max_tool_steps: int = Field(default=3, ge=0, le=5)
    max_llm_requests: int = Field(default=100, ge=1, le=1000)
    max_input_bytes: int = Field(default=8192, ge=128, le=65536)


class Settings(Model):
    credentials: Credentials = Field(default_factory=Credentials, repr=False)
    stt: STTSettings = Field(default_factory=STTSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    listening: ListeningSettings = Field(default_factory=ListeningSettings)
    interruption: InterruptionSettings = Field(default_factory=InterruptionSettings)
    latency: LatencySettings = Field(default_factory=LatencySettings)
    humanization: HumanizationSettings = Field(default_factory=HumanizationSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    greeting: GreetingSettings = Field(default_factory=GreetingSettings)
    ending: EndingSettings = Field(default_factory=EndingSettings)
    limits: Limits = Field(default_factory=Limits)
    prompt_path: Path = PROJECT_ROOT / "prompt.md"

    @model_validator(mode="after")
    def validate_profiles(self) -> Settings:
        if self.runtime.greeting and "greeting" in self.model_fields_set:
            raise ValueError("Use greeting settings or legacy runtime.greeting, not both")
        if self.ending.enabled and self.limits.max_tool_steps == 0:
            raise ValueError("Ending tool requires limits.max_tool_steps > 0")
        if self.ending.detect_explicit and not self.ending.enabled:
            raise ValueError("Explicit ending detection requires ending.enabled")
        if self.ending.detect_explicit and self.latency.preemptive_llm:
            raise ValueError("Explicit ending detection requires preemptive_llm=false")
        flux = self.stt.model.startswith("flux-")
        if flux != (self.listening.turn_detection == "stt"):
            raise ValueError("Flux requires stt turn detection; Nova requires vad or semantic")
        if not flux and (
            self.stt.eot_threshold is not None
            or self.stt.eager_eot_threshold is not None
            or self.stt.eot_timeout_ms is not None
        ):
            raise ValueError("Flux thresholds cannot be used with Nova")
        if flux and self.listening.endpointing_mode != "fixed":
            raise ValueError("Flux owns endpointing; dynamic endpointing applies only to Nova")
        # Locked audio detector starts predictions after 200 ms silence and requires
        # another 50 ms before the VAD closes the segment (SDK 1.8.10 invariant).
        if (
            self.listening.turn_detection == "semantic"
            and self.listening.vad.min_silence_duration < 0.25
        ):
            raise ValueError("Semantic turn detection requires vad.min_silence_duration >= 0.25")
        if self.stt.eager_eot_threshold is not None:
            if self.stt.eager_eot_threshold > (self.stt.eot_threshold or 0.7):
                raise ValueError("Flux eager_eot_threshold must not exceed eot_threshold")
        if len(self.stt.keyterms) > 100:
            raise ValueError("at most 100 STT keyterms are supported")
        return self

    @property
    def opening(self) -> GreetingSettings:
        if self.runtime.greeting:
            return GreetingSettings(mode="custom", text=self.runtime.greeting)
        return self.greeting

    def require_credentials(self, *, room: bool) -> None:
        names = ["DEEPGRAM_API_KEY", "GROQ_API_KEY", "CARTESIA_API_KEY"]
        if room:
            names += ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
        elif self.interruption.mode == "adaptive":
            names += ["LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
        missing = [
            name
            for name in names
            if not getattr(self.credentials, SECRET_NAMES[name]).get_secret_value().strip()
        ]
        if room and not self.credentials.livekit_url.strip():
            missing.append("LIVEKIT_URL")
        if missing:
            raise ConfigurationError("Missing required credentials: " + ", ".join(missing))
        if room:
            try:
                url = urlsplit(self.credentials.livekit_url)
                valid = (
                    # Agents 1.8.10 maps https->wss and http->ws at its transport boundary.
                    url.scheme in {"wss", "https", "ws", "http"}
                    and url.hostname
                    and url.port != 0
                    and url.username is None
                    and url.password is None
                    and not url.query
                    and not url.fragment
                    and (
                        url.scheme in {"wss", "https"}
                        or url.hostname in {"localhost", "127.0.0.1", "::1"}
                    )
                )
            except ValueError:
                valid = False
            if not valid:
                raise ConfigurationError(
                    "LIVEKIT_URL requires wss://host or https://host; "
                    "ws:// or http:// only on loopback; "
                    "no URL credentials/query/fragment"
                )
        if self.tts.voice_id is None:
            raise ConfigurationError("Set VOICEAGENT_TTS__VOICE_ID to an authorized Cartesia UUID")

    def redacted(self) -> dict:
        result = self.model_dump(mode="json")
        secrets = [
            value.get_secret_value()
            for name, value in self.credentials
            if name != "livekit_url" and value.get_secret_value()
        ]

        def redact(value):
            if isinstance(value, str):
                for secret in sorted(secrets, key=len, reverse=True):
                    value = value.replace(secret, "<redacted>")
                return value
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items()}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        result = redact(result)
        # URLs can contain credentials or query tokens. Do not print them either.
        result["credentials"] = {
            name: "<set>"
            if (value.get_secret_value() if isinstance(value, SecretStr) else value)
            else "<unset>"
            for name, value in self.credentials
        }
        return result


def _merge(base: dict, override: Mapping) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _portable_path(path: str | Path, root: Path) -> Path:
    if not isinstance(path, (str, Path)) or "\x00" in str(path):
        raise ConfigurationError("Config and prompt paths must be valid strings or Paths")
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


def _env_settings(values: Mapping[str, str | None]) -> dict:
    result: dict = {}
    credentials: dict = {}
    for key, value in values.items():
        if value is None or not value.strip():
            continue
        if key in SECRET_NAMES:
            credentials[SECRET_NAMES[key]] = value
        elif key == "LIVEKIT_URL":
            credentials["livekit_url"] = value
        elif key == "VOICEAGENT_PROMPT_PATH":
            result["prompt_path"] = value
        elif key.startswith("VOICEAGENT_") and "__" in key:
            parts = key.removeprefix("VOICEAGENT_").lower().split("__")
            if parts[0] == "credentials":
                raise ConfigurationError("Use the documented provider credential variable names")
            target = result
            for part in parts[:-1]:
                child = target.setdefault(part, {})
                if not isinstance(child, dict):
                    raise ConfigurationError("Conflicting nested environment settings")
                target = child
            try:
                target[parts[-1]] = json.loads(value)
            except (ValueError, TypeError):
                target[parts[-1]] = value
    if credentials:
        result["credentials"] = credentials
    return result


def load_settings(
    *,
    overrides: Mapping | None = None,
    config_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> Settings:
    """Overrides > process env > customization .env.local > root .env.local > YAML > defaults.

    An optional public customization/host/agent.yaml overlays the base YAML, below
    dotenv/environment/constructor overrides.
    Explicit relative config/prompt paths resolve from the copied project root.
    No parent .env files, current working directory, or network access are used.
    """
    env = os.environ if environ is None else environ
    if overrides is not None and not isinstance(overrides, Mapping):
        raise ConfigurationError("Constructor overrides must be a mapping")
    try:
        local = dotenv_values(project_root / ".env.local", interpolate=False, encoding="utf-8-sig")
        custom = dotenv_values(
            project_root / "customization" / ".env.local", interpolate=False, encoding="utf-8-sig"
        )
        local = {
            **local,
            **{key: value for key, value in custom.items() if value and value.strip()},
        }
    except (OSError, UnicodeError):
        raise ConfigurationError("Cannot read project .env.local as UTF-8") from None
    path = config_path or env.get("VOICEAGENT_CONFIG_PATH") or local.get("VOICEAGENT_CONFIG_PATH")
    config = _portable_path(path or "config.example.yaml", project_root)
    try:
        with config.open("rb") as handle:
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise ConfigurationError("Configuration exceeds 65536 bytes")
        data = yaml.safe_load(raw.decode("utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError):
        raise ConfigurationError(
            "Cannot read configuration: expected a readable UTF-8 YAML file"
        ) from None
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration must be a YAML mapping")
    if "credentials" in data:
        raise ConfigurationError("Credentials are forbidden in YAML; use environment or .env.local")
    host_profile = project_root / "customization" / "host" / "agent.yaml"
    if host_profile.exists():
        try:
            with host_profile.open("rb") as handle:
                host_raw = handle.read(65537)
            if len(host_raw) > 65536:
                raise ConfigurationError("Host configuration exceeds 65536 bytes")
            host = yaml.safe_load(host_raw.decode("utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError, RecursionError):
            raise ConfigurationError("Cannot read public host configuration") from None
        if not isinstance(host, dict) or "credentials" in host:
            raise ConfigurationError("Host configuration must be a mapping without credentials")
        data = _merge(data, host)
    data = _merge(data, _env_settings(local))
    data = _merge(data, _env_settings(env))
    data = _merge(data, overrides or {})
    data["prompt_path"] = _portable_path(data.get("prompt_path", "prompt.md"), project_root)
    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        # Never include Pydantic input values or user-supplied text in errors.
        errors = exc.errors()
        fields = sorted(
            {
                ".".join(map(str, (*error["loc"][:-1], "<unknown>")))
                if error["type"] == "extra_forbidden"
                else ".".join(map(str, error["loc"])) or "profile"
                for error in errors
            }
        )
        # Our cross-field validators use fixed messages, which make conflicts actionable.
        reasons = sorted(
            {
                error["msg"].removeprefix("Value error, ")
                for error in errors
                if error["type"] == "value_error"
            }
        )
        detail = "; " + "; ".join(reasons) if reasons else ""
        raise ConfigurationError(
            "Invalid configuration fields: " + ", ".join(fields) + detail
        ) from None
