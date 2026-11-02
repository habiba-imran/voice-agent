# Optional speech delivery

Humanization remains **off by default**. Phase 4's live listening gate is **BLOCKED**. Text and
fake-audio tests do not certify naturalness, pitch, prosody or audible latency. The earlier Phase
2/3 real-audio gates must also pass before choosing production defaults.

Select non-secret YAML with `VOICEAGENT_CONFIG_PATH`, or use nested environment overrides such as
`VOICEAGENT_HUMANIZATION__DISFLUENCIES=off`. Restart after configuration changes. For a future
authorized A/B comparison:

```yaml
humanization:
  enabled: true
  default_style: conversational
  emotion: auto
  speed: null
  volume: null
  pace: baseline
  disfluencies: contextual
  max_leading_fillers_per_turn: 1
  filler_cooldown_turns: 3
  pauses: punctuation
  markup: false
  laughter: false
```

This example does not authorize provider consumption. Existing secrets and voice selection are
untouched. `config.example.yaml` reproduces typed defaults with humanization disabled.

| Setting | Default | Behavior |
| --- | --- | --- |
| `enabled` | false | Off restores baseline provider controls and unmodified LLM streaming |
| `default_style` | conversational | Language guidance: neutral, conversational, reassuring, thoughtful, curious, enthusiastic |
| `emotion` | auto | Omit emotional guidance so Sonic interprets the text; explicit choices: neutral, calm, content, excited, sympathetic, curious, confident, contemplative |
| `speed` | null | Explicit 0.6–1.5 request guidance overrides pace |
| `volume` | null | Explicit 0.5–2.0 request guidance; otherwise inherits `tts.volume` |
| `pace` | baseline | Application preset: baseline inherits `tts.speed`; measured multiplies by 0.95, lively by 1.05, bounded to 0.6–1.5 |
| `disfluencies` | contextual | Permit rare main-LLM hesitation; off forbids optional hesitation |
| `max_leading_fillers_per_turn` | 1 | Hard cap of 0 or 1 recognized leading hesitation per text-bearing generation |
| `filler_cooldown_turns` | 3 | At least three intervening text-bearing generations before another hesitation |
| `pauses` | punctuation | Preserve punctuation; no explicit timed pauses |
| `markup`, `laughter` | false | Active markup/nonverbals rejected pending separate validation |

The existing `emotional_range: baseline` value remains for configuration compatibility; it does
not define a numeric emotion range. Unsupported fields such as pitch or emotion intensity fail
validation. Pace multipliers are application policy, not measured quality recommendations.

## Direct Cartesia capabilities

Installed plugin inspection and in-memory WebSocket tests verify constructor/update controls,
serialization to Sonic 3 generation_config, per-stream option snapshots, distinct context IDs,
pool reuse and cancellation cleanup. Only the first emotion in a list is serialized, so this
module accepts a single validated emotion. No dedicated pitch/intensity parameter is exposed.
Current provider documentation uses a 1.5 speed ceiling; the SDK source warns at 2.0. This module
keeps its conservative existing 1.5 limit. No new dependency is required.

With `emotion: auto`, no provider emotion field is sent. Context-sensitive delivery relies on
the existing Groq reply's emotional wording and Sonic's interpretation of that text. Static
emotion remains available. The module never guesses emotions using keywords or another model,
and never mutates a shared TTS client during active generation. Default style adds stable language
guidance after the external prompt and before untrusted metadata, preserving the static prefix.

Direct Sonic documents inline speech tags and laughter; the installed plugin can forward complete
tags. This is distinct from LiveKit's Inference-only expressive session path. Active SSML, timed
breaks and laughter are disabled here; forwarding tests cannot prove a tag is interpreted rather
than spoken. The session keeps `expressive=False` and direct Cartesia billing. No Inference TTS
substitution is added. Voice type/selection can affect controls; availability/licensing is unverified.

## Fillers and streaming safety

The main LLM may generate a rare appropriate leading `hmm`, `uh`, `um` or `umm`. A per-agent
budget permits one or none, normalizes an accepted prefix to a comma/space, removes repeated
prefixes and treats um/umm as one family. It never inserts random fillers or separate filler-only
TTS requests. Empty/tool-only generations do not advance the cooldown. Canceled text-bearing
output counts conservatively. This is a generated-text limit, not a caller-heard frequency claim.

“Well”, “Actually” and “you know” can carry meaning, so they are not mechanically stripped or
inserted. Quoted, technical and mid-sentence text remains intact. Instructions discourage fillers
there; a global hard cap on every semantic use of these words is not claimed.

When enabled, a per-generation guard removes recognized speech controls: emotion, speed, volume,
break, spell, speak, prosody, phoneme, and known laughter/sigh stage tokens. It handles split and
escaped delimiters, nested wrappers and cancellation. It never emits active SSML or interprets
break durations. URLs, numbers, identifiers, comparisons and unknown technical angle expressions
are preserved. This is a speech-control guard, not a general XML/HTML sanitizer.

The guard buffers only possible control prefixes and at most 64 characters of ambiguous leading
text. Recognized attributes are discarded without accumulating them. An unclosed recognized tag
discards ambiguous attributes through newline/EOF; this can lose malformed content, so markup is
forbidden by the prompt. Plain text before/after recovery remains usable. No punctuation rewrite
is applied to the substantive answer. Technical/factual regression cases run at every split point.

Cleaned content feeds both TTS and history. Input chunks' tool calls, usage and metadata are
preserved without mutation. Pending fragments are dropped on cancellation. There are no extra
requests, timers, tasks, queues, full-response buffers or client recreations. Native LiveKit
turn-taking/playout cancellation remains in control. Phase 5 measures text-processing overhead
and synthetic sink timing in [PERFORMANCE.md](PERFORMANCE.md) and PHASE_REPORT.md. Real provider
first-audio cost remains unmeasured; unchanged architecture is not proof of zero overhead.

Safe fallback is plain text/punctuation and an explicit ordinary or neutral profile. Disable the
feature to restore baseline tts settings, or choose neutral style/emotion, speed/volume 1 and
disfluencies off. Invalid configuration fails before requests. Provider errors never trigger an
automatic replay or provider switch after partial audio.

See [the listening protocol](../evals/humanization_ab.md). The revised prompt has not been sent
to Groq; earlier live text results apply to the previous prompt only.
