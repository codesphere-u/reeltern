# Roadmap: useful editing before more claims

This is a prioritized proposal, not a promise of delivery dates. Released functionality is documented in the [README](../README.md) and [validation record](../VALIDATION.md). Open an issue with a concrete editing case before committing to a large feature.

## Available now — 0.3.1

Local imports, immutable cut plans, trimming/reordering/speed, silence-assisted proposals, supplied-transcript selection, retimed captions, optional constrained Ollama drafts, verified preview/export, segment reuse, job retry, desktop controls, 21 MCP tools and client configuration generation. Optional upstream adapters remain experimental.

## Next: make the first useful edit easier

| Priority | Feature | Implementation direction | Acceptance criteria |
|---|---|---|---|
| P0 | Built-in optional transcription | Separate speech adapter; produce the existing cue format; record model/version/language/confidence and explicit model installation | Tested multilingual fixtures; timestamp bounds; words not invented during silence; cancellation; no surprise model download |
| P0 | Word-aligned text editing | Extend transcript schema with optional word timing; retain existing cue compatibility | Mid-sentence trims generate accurate captions; speed/reorder tests; missing alignment falls back visibly |
| P0 | In-app preview and waveform | Playback controller and proxy media over saved plans; visible source/output time | Seek and playback match exported cuts; audio remains synchronized; keyboard controls and small-window layout tested |
| P0 | Burned-in captions | Validated style preset and FFmpeg subtitle renderer; escaped input and explicit font handling | Unicode, multiline text and portrait safe-area fixtures; font availability check; selectable captions remain an option |
| P0 | Real-footage regression corpus | Permission-cleared short samples: phones, screen recordings, rotated/VFR clips, offset audio | Tests for rotation, sync, duration and failures on all supported OSes; documented known limits |

## Then: reliable projects at practical scale

| Priority | Feature | Implementation direction | Acceptance criteria |
|---|---|---|---|
| P1 | Storage quotas and preflight | Estimate space, inspect cache, evict only inactive reusable entries | Low-disk simulation fails clearly; originals and active jobs protected; reclaimable space reported |
| P1 | Idempotent render submissions | Request keys mapped to persisted job IDs | Retried client calls return the same job; crash/reconnect tests; explicit new-render action remains available |
| P1 | Better job monitoring | Structured phases, progress events, elapsed/estimated work and cancel semantics | MCP and desktop remain responsive during long work; estimates labeled; cancellation cleanup tested |
| P1 | Installers and versioned releases | Signed/notarized packages where feasible; reproducible build manifests | Clean-machine install/uninstall; no developer Python required for desktop; binary/license notices included |
| P1 | Agent quality evaluations | Human-reviewed transcript tasks with crucial qualifications and distracting instructions | Measure unsupported selections, lost context, budget failures, latency and review effort; publish failures alongside scores |
| P1 | Review comparison | Side-by-side plan/source evidence and preview versions | Reviewer can identify each changed range, restore a parent and verify captions before export |

## Later: deeper editing and upstream integration

| Feature | Dependency | Completion gate |
|---|---|---|
| Beat-aware assembly using librosa | Stable soundtrack/timeline mapping | Audible beat alignment measured after export, with source context retained |
| Scene-aware RIFE / Real-ESRGAN workflows | Promoted adapters with hardware/weight management | Scene cuts protected; temporal artifacts evaluated; bounded memory and audio sync tested |
| Background removal and color matching | Consistent frame pipeline and reference management | Flicker, edge stability, color-space behavior and source preservation measured |
| Titles and motion graphics through HyperFrames | Restricted project inputs and reliable render handoff | Timing/font consistency, resource bounds and trusted-template handling verified |
| Multitrack audio, transitions and compositing | Versioned timeline schema beyond simple concatenation | Overlaps and audio mixing have explicit semantics and real-media tests |
| Interchange export to other editors | Choose a supported timeline interchange format | Round-trip trim/order/speed tests and documented unsupported effects |
| Remote team rendering | Authentication, per-project isolation, uploads and quotas | Separate threat model and deployment tests; never expose current local stdio tools as an unauthenticated public endpoint |

## What makes a feature ready

A demo alone is insufficient. A feature needs a useful user-facing flow, failure behavior, data compatibility, tests on actual media, installation instructions and documented limits. Benchmark claims need a published corpus, hardware, settings and comparable outputs. Popularity should be measured by successful first edits and returning users, not the length of a feature list.

For a feature proposal, include the editing problem, current workaround, sample you can legally share, intended output, runtime/hardware constraints, implementation sketch and a measurable test. Use the [feature request template](../.github/ISSUE_TEMPLATE/feature_request.yml).
