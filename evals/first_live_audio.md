# Live-audio acceptance checklist — qualitative smoke reported; formal gates pending

The owner reports a running Cloud deployment and at least one audible Deepgram → Groq → Cartesia
microphone conversation at revision 1fe4b9f, reported 2026-11-02. This is qualitative evidence only:
exact turn count, timings, errors, cleanup and formal interruption results are unavailable.
It does not establish that the detailed checklist below was run. Additional tests remain unapproved.

This checklist prepares a local worker in a designated LiveKit test room; no cloud deployment
is required. No new command below that starts a worker or calls providers is authorized by this
review. The previous five Groq text requests do not cover additional voice/simulation use. Fill keys
locally in the existing ignored .env.local; never paste them into chat or this document.

## Before requesting approval

- Confirm target project/region and exclusive test room, named dispatch voiceagent (or the actual
  configured name), authorized Cartesia voice UUID/language and provider model/account access.
  A UUID or local configuration check does not prove permission/quota.
- Agree a fresh bounded budget: number of voice turns, STT audio duration, TTS character allowance,
  Groq requests/output-token limit, LiveKit room minutes, timeout/stop rules and who monitors cost.
  Default requests are capped and retries off, but settings alone are not a currency budget.
- Obtain permission for provider/LiveKit consumption and microphone or approved input playback.
  Request audio recording/raw transcript export separately, with purpose, storage location,
  retention and access controls. Default is no recording/export.
- Use only generic synthetic conversation content. Keep humanization, preemptive LLM/TTS, active
  markup/laughter and adaptive Cloud inference off for the first baseline. Preserve Nova/VAD
  thresholds. Confirm no unrelated worker/deployment will be changed or stopped.
- Run offline validation first:

```powershell
uv sync --locked
uv run agent.py validate --mode room
uv run pytest -q
```

Validation checks shape/presence, not provider authentication. Review current SDK/version and
sanitized settings locally. For the room participant use an existing trusted LiveKit Agent
Console/client with host-issued short-lived room-scoped tokens and explicit named dispatch.
Token issuance/UI are host responsibilities; do not add them to this module.

## After explicit approval

1. Start the **local** worker with `uv run agent.py start`. This is a live operation. Wait for
   successful worker registration and dispatch into the designated room before claiming readiness.
   SDK provider prewarming may make requests. If authentication/voice/quota fails, stop and retain
   only sanitized status/reason; do not retry, change providers or enlarge budget automatically.
2. Join with the approved microphone/input device. Confirm both directions actually carry audio.
   Worker registration or room join alone is not STT/TTS or audible-playback proof.
3. Exercise five baseline turns: brief compiler explanation; decimal 42.5/identifier AB_92-x;
   an unavailable-account question; a question with one-second hesitation/trailing um; a long
   explanation interrupted with Wait, stop, explain it in one sentence instead. Verify one replacement answer,
   no old tail, no reasoning/markup spoken, and no invented tool action. Observe initial SDK AEC
   warmup separately from later interruptions.
4. Remain silent, then disconnect during a response. Confirm idle/terminal disconnect reason,
   drained-or-cancelled generation, completed job and provider cleanup. Don't delete the room or
   alter another worker. Stop the local test worker with Ctrl+C when finished; allow at least the
   configured shutdown grace (worst cooperative default path is 55 seconds). Investigate continued
   activity/cost; never label an unexplained timeout successful cleanup.
5. Retain numeric sanitized evidence only unless storage permission was separately granted:
   case IDs/counts, versions, prompt hash, voice/model, regions/device/network, warm/cold status,
   errors/reasons, SDK component timings, actual input-end/playback observations and usage when
   exposed. No raw keys, prompts, speech or provider response bodies in source/reports.
6. Manually listen and note each case's factual correctness, clarity and turn behavior. Leave
   unavailable values null/NOT MEASURED. Server sink acceptance is not caller-heard latency;
   use actual playback timestamps with a validated clock or state that E2E remains unmeasured.

## Subsequent gates after the baseline

- Five successful turns can support only the narrow Phase 2 baseline; they do not close acoustic,
  naturalness, concurrency, cost or general reliability gates by themselves.
- Compare Nova/VAD, Nova/local-mini and Flux with the same approved speech inputs: at least 20
  warm turns plus five separate cold trials per configuration. Include all scenarios.md cases.
  Measure clipped/false turns, recognition errors and audio-to-stop rather than tuning to speed.
- For humanization/voice/control and preemptive A/B, use at least 30 comparable warm turns per
  condition; apply humanization_ab.md. Audible benefit and no material accuracy/interruption
  regression are required before changing defaults. Plan targets are warm E2E p50 <=1.2 s,
  p95 <=2.0 s and genuine barge-in audio-to-stop p95 <=500 ms; no result is prefilled.
- Authorize live failure/concurrency/socket/RSS soak separately. Use provider-approved quota and
  safe fault methods; don't intentionally consume or exceed account limits.
- CLI debugger and hosted simulations need CLI >=2.19.0, current help/schema verification,
  account/credit approval and a reviewed SessionHost opt-in. Cloud audio artifacts may need
  explicit retention consent. Prepared scenarios are not runnable certification. Deployment
  requires another explicit approval even after every local audio test passes.

| Evidence | Current value |
| --- | --- |
| Approval/budget/project/voice confirmed | NOT SET |
| Real voice turns / cold / warm samples | 0 / 0 / 0 |
| Actual playback / listening scores | NOT MEASURED |
| E2E / audio-to-stop p50/p95 | NOT MEASURED |
| Provider usage / currency spend | NOT MEASURED |
| First live-audio gate | BLOCKED |
