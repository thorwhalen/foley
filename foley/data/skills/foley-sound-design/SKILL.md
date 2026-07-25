---
name: foley-sound-design
description: >-
  Use when sound-designing a NARRATION with the `foley` package — choosing sound effects for
  narrated/voiced text and weaving them under the voice. Triggers on: "add sound effects to this
  narration", "score this passage", "sound-design this audiobook/podcast/video script", "find a
  sound for this line", "weave SFX into the voiceover", "make a sound-design timeline", or any
  task that pairs narration text (or a transcript) with choosing + placing sounds. Covers the
  find→plan→weave loop, the one-call `foley.score()`, the MCP tool surface, and the taste
  heuristics (restraint, layering, ducking, licensing).
---

# Sound-designing a narration with `foley`

`foley` is a retrieval-first façade for sound effects: **find (or generate) the right sound for a
moment of narration and weave it in.** Your job with this skill is to turn narration text into a
**tasteful, license-clean** sound design — not to put a sound under every sentence.

## The one rule: restraint

Most sentences need **no** sound. A few well-placed, license-clean cues beat "sound soup." The
SELECT stage already enforces this (a salience/density budget, a fail-closed license gate, and a
verify ladder) — trust it, and prefer leaving quiet moments quiet.

## Fastest path — one call

```python
import foley

# Plan only (choose sounds, build an editable timeline):
result = foley.score("She pushed open the heavy oak door; rain hammered outside.")
print(result.rationale)  # what was chosen and why
result.timeline  # an editable SoundDesignTimeline

# Plan + render (weave under the actual narration audio):
result = foley.score(segments, audio="narration.wav", commercial_ok=True)
result.weave.audio  # mastered stereo mix (numpy)
result.weave.captions_vtt  # SDH captions (no speech text leaks)
result.weave.credits  # attribution (CREDITS.md + JSON)
```

`segments` is a string or a list of narration segments. `foley.score(...)` runs
`decompose → search → verify → decide → plan` per segment and, when `audio` is given, aligns +
weaves into a mastered mix. This is the stable contract downstream packages (`braidio`, `nw`) call.

## The full loop (when you want control)

| Step | Python | MCP tool |
|------|--------|----------|
| choose sounds for a passage | `foley.find(context)` | `foley_find` / `foley_score` |
| direct search / "more like this" | `foley.search(q)` / `foley.similar(id)` | `foley_search` / `foley_similar_to` |
| audition a candidate | — | `foley_preview(id)` (returns a store key) |
| steer with feedback | — | `foley_refine(picks, rejects, hint)` |
| accept / reject | — | `foley_pick(id, layer, onset)` / `foley_reject(id)` |
| fold picks → timeline | `foley.plan(cands)` | `foley_plan` |
| edit (non-destructive) | `foley.weave.timeline.*` | `foley_swap_clip` / `foley_set_gain` / `foley_nudge` / `foley_toggle` / `foley_set_master` |
| render | `foley.weave(narration, timeline)` | `foley_weave` |
| generate when nothing fits | `foley.generate(prompt)` | `foley_generate` |
| what's the workflow / what's installed | — | `foley_guide` / `foley_capabilities` / `foley_status` |

**MCP is JSON-in / JSON-out**: tools take/return only JSON (ids, scores, license summaries,
timeline dicts, store keys) — audio is referenced by a byte-store key, never inlined. Call
`foley_guide` first if unsure.

## Taste heuristics

- **Layers.** `sfx_fg` = a spot effect on a trigger word; `ambience` = a bed under a
  sentence/scene (loops, kept low, **ducked** under the voice); `stinger` = a sharp accent on a
  boundary; `music` sparingly.
- **Onset.** Place a spot effect **on** its trigger word; a bed **spans** its sentence. The weave
  stage resolves symbolic anchors ("on 'door'") against the forced-aligned narration.
- **Salience.** Score a moment only if the sound adds meaning. Leave silence where silence works.
- **Loudness.** Pick a master profile for the delivery target: `podcast` (-16 LUFS), `streaming`
  (-14), `broadcast_ebu` (-23). The mix is loudness-normalized + true-peak-limited.

## Licensing is load-bearing (foley's output gets published)

- Only `license_ok` candidates are ever placed — the gate is **fail-closed** (unknown license →
  refused). Set `commercial_ok=True` (or `IntendedUse(commercial=True, publish=True)`) when the
  result will be published commercially, and the filter tightens accordingly.
- Read each candidate's `license` summary: `commercial_ok`, `requires_attribution`,
  `redistribute_standalone_ok`, `is_ai_generated`. `foley.credits(sounds)` builds the attribution
  (a `CREDITS.md` + JSON) — always ship it.
- Generated audio (`foley.generate`) is disclosed (EU AI Act Art. 50) and watermarked when the
  provenance extra is installed; the mix carries a C2PA content credential.

## Offline / sensitive narration

For confidential scripts, run the offline posture: external sources **and** telemetry are
disabled, redaction is on, and generation stays on local backends. `foley_status` reports it;
`foley-mcp --offline` serves it. A local LLM (Ollama/llama.cpp/vLLM via `FOLEY_LLM_BASE_URL`) can
drive the SELECT rungs so nothing leaves the device.

## Degraded modes

`foley` works out of the box and degrades gracefully: without the CLAP/index extras it still runs
a keyword search; without an aligner it uses evenly-spaced word timings; without `ffmpeg` the
master runs in-process. Call `foley_capabilities()` to see what's installed and what's degraded,
and `foley.check_requirements()` for setup guidance.
