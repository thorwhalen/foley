# foley — Dimensions We Haven't Named Yet (Meta-Scan)

**Abstract.** Reports 01–09 and 11 cover foley's spine — sources, generation,
recognition/tagging, embeddings/indexing, the retrieval agent, weaving/mixing,
licensing, evaluation, audio I/O, and corpora. This report is the deliberate
"what are we forgetting?" pass: it surfaces, researches, and **ranks** the
cross-cutting dimensions those reports under-cover, so nothing load-bearing is
missed before code lands. It examines the ten dimensions named in Prompt 12 plus
five discovered ones (privacy/data-governance, API-quota orchestration &
graceful degradation, generation determinism/seed-capture, cultural/temporal
plausibility, and sound-continuity across a work). Each entry gives *why it
matters to foley*, the *key open questions*, and *pointers to primary sources*.
The ranking criterion is **load-bearing-ness**: legal/correctness exposure of
*published* output, how cross-cutting the concern is, and whether it is cheap to
fold into an existing module now versus needing its own deep-research prompt. A
closing **Recommendations for foley** section maps each dimension to a phase and
flags the four that deserve their own future prompt.

---

## Ranked summary

| # | Dimension | Why it's load-bearing for foley | Disposition |
|---|-----------|--------------------------------|-------------|
| 1 | **Caching & cost control** | Every generation/embedding/LLM call is metered; the "cache accepted generations back into the library" flywheel is already the design's cost-decay mechanism | Fold into `index/` + architecture; short spike |
| 2 | **Observability & decision logging** | The `decompose→search→verify→decide` loop is un-debuggable and un-*evaluable* without traces; it is the substrate Prompt 8 (eval) sits on | **Own prompt** (with #4) |
| 3 | **Safety, disclosure & watermarking** | foley's output is *published*; EU AI Act Art. 50 disclosure bites **2 Aug 2026**; C2PA/AudioSeal are the provenance rails | **Own prompt** (extends Prompt 7) |
| 4 | **Versioning & reproducibility (editable sound-design artifact)** | The author's north star: a re-renderable "snapshot/story" of a narration's SFX layer, not a one-shot bake — OTIO is the standard | **Own prompt** (with #2) |
| 5 | **Prompt engineering for SFX generation** | Prompt phrasing dominates AudioGen/Stable-Audio quality; the SFX analog of arioso's prompt guide | Fold into Prompt 2 + a guide doc |
| 6 | **Accessibility — SFX captioning + audio description** | foley *already* produces `[door creaks]` event lists → near-free SDH caption + AD output artifacts; standards are explicit | Fold into `weave/` output artifacts |
| 7 | **UX for auditioning (preview, shortlist, "more like this")** | Top-1 ≈ 30% right → the human/relevance-feedback loop is where retrieval quality is recovered | Fold into agent tool surface / Phase 4 |
| 8 | **Real-time vs offline & latency budgets** | Sets the async architecture; foley is batch-first, but interactive authoring has a perceptual budget | Fold into architecture (Prompt 10) |
| 9 | **Multilingual / non-English context→sound** | Decompose is LLM-multilingual already; the CLAP retrieval side is English-centric — GLAP is the fix | Fold into Prompt 4/5 |
| 10 | **Spatial / immersive audio** | High polish ceiling (binaural/ambisonics placement); belongs to `weave/`, later | Fold into Prompt 6 (weave) |
| 11 | **Privacy & data governance** *(discovered)* | Narration text/audio is often private/pre-release; it leaks to Freesound, ElevenLabs, and LLM APIs | Fold into architecture + licensing |
| 12 | **API-quota orchestration & graceful degradation** *(discovered)* | Many rate-limited paid APIs + optional GPU; needs throttle/retry/circuit-break and an offline fallback path | Fold into source-adapter contract |
| 13 | **Generation determinism & seed capture** *(discovered)* | Reproducibility is impossible if a generated cue can't be re-created; seed belongs in provenance | Fold into #4 + `SoundRecord` |
| 14 | **Cultural / temporal plausibility (anachronism guard)** *(discovered)* | A car horn in a medieval scene, or a US siren in a UK setting, is a *correctness* failure retrieval won't catch | Fold into `decompose`/`verify` |
| 15 | **Sound continuity & motif consistency** *(discovered)* | A recurring door should sound the same each time; ambience beds must persist across windows | Fold into the timeline data model (#4) |

---

## 1. Caching & cost control  *(rank 1 — fold in, with a spike)*

**Why it matters.** foley's cost surface is unusually broad: hosted generation
(ElevenLabs ≈ $0.12/min), embedding + LLM calls in `decompose`/`verify`, and
Freesound/other API round-trips. Three cache layers compound: (a) **content
caches** (decoded audio arrays, CLAP embeddings — never re-embed a file whose
bytes are unchanged; content-address by hash, cross-ref Report 09); (b)
**generation memoization** — an identical `generate(prompt, backend, params,
seed)` must not re-bill; and, most strategically, (c) the design's own **"cache
accepted verified generations back into the library"** flywheel — every accepted
generation converts the *next* similar request from a paid generation into a free
retrieval, so the generate-rate (and cost) decays over library life.

**Semantic caching** is the near-miss extension: cache by *embedding similarity*
of the request, not exact string match. GPTCache reports 2–10× speedups on cache
hits [1]; a follow-up "GPT Semantic Cache" cut API calls up to ~68.8% with
>97% positive-hit accuracy [2]. The risk is **false hits** (a semantically-near
but wrong cue) — so a similarity threshold plus a cheap verify gate is needed;
this is exactly foley's existing `verify_match` ladder, reused as the cache
admission test.

**Open questions.** What is the cache key for a generation (prompt + backend +
unified params + seed + model version)? What TTL/invalidation on model upgrades
(a CLAP re-train invalidates every embedding — stamp `embedding_model`/`dim`, as
Report 04 already mandates)? At what similarity threshold does a semantic-cache
hit require re-verification vs auto-serve? Does Freesound's TOS permit caching a
retrieved blob (per-source policy — already an open question in `design.md`)?

**Primary sources.** GPTCache [1]; GPT Semantic Cache [2]; and foley's own
Report 09 (content-addressed byte store) and Report 05 (the flywheel).

## 2. Observability & decision logging  *(rank 2 — own prompt, with #4)*

**Why it matters.** foley's core is a *multi-step, multi-model* pipeline
(`decompose_context` → `search_sounds` → `verify_match` → `decide` →
generate/place). When a wrong sound ships, the only way to know *why* — bad
decomposition? shortlist miss? verifier false-accept? — is a structured trace of
every step: the LLM prompts/completions, the shortlist and scores, the CLAP /
audio-LM / LLM-judge verdicts, the branch taken, latency and token/$ per step.
Without this, Prompt 8's evaluation harness has nothing to measure and no way to
attribute regressions. Observability is therefore not polish; it is the
*substrate* for both debugging and evaluation.

There is now a **standard** to conform to rather than invent: the OpenTelemetry
**GenAI semantic conventions** (GenAI SIG, formed April 2024; expanded through
2025–26 to cover LLM client spans, **agent spans**, MCP tool calls, prompt/
completion content events, and quality-eval metrics) [3][4]. Attributes such as
`gen_ai.request.model`, `gen_ai.usage.input_tokens`/`output_tokens`,
`gen_ai.response.finish_reasons` are already emitted natively by LangChain,
CrewAI, AutoGen, etc., and consumed by Langfuse/Datadog/Honeycomb [3]. foley's
tool functions (already the MCP surface) are the natural span boundaries; wrapping
each in an OTel span gives per-decision auditability for free and keeps the
telemetry vendor-neutral.

**Open questions.** How much prompt/audio content to capture vs redact (ties to
#11 privacy)? Do we emit a **run manifest** per `find()` call (the join between
telemetry and the reproducible artifact of #4)? Sampling policy for expensive
verify calls? Should the trace itself be the eval dataset (replay past traces
against a new index)?

**Primary sources.** OpenTelemetry GenAI observability blog + semantic
conventions [3]; OpenLLMetry / GenAI SIG scope note [4].

## 3. Safety, disclosure & watermarking  *(rank 3 — own prompt, extends Prompt 7)*

**Why it matters.** foley emits published media, so three obligations attach to
*generated* or *near-copyright* cues, and one is **deadline-driven**:

- **Regulatory disclosure.** EU AI Act **Article 50** requires providers to mark
  AI-generated/manipulated audio in a machine-readable, detectable way, and
  deployers to disclose deepfake audio "at the latest at the time of the first
  interaction," with a lighter obligation for evidently artistic/fictional works
  [5][6]. These transparency duties **apply from 2 August 2026** [6] — inside
  foley's plausible build window. A narration with AI-generated SFX plausibly
  triggers the generic "AI-generated content" marking duty even when it is not a
  "deepfake."
- **Provenance rails.** **C2PA / Content Credentials** (Technical Spec 2.2,
  2025-05-01; 2.x line ongoing) is the cross-industry way to cryptographically
  bind "this asset / this region was AI-generated, by this tool" into the file,
  including audio assertions [7][8]. It is the machine-readable half of Art. 50.
- **Watermarking.** Meta **AudioSeal** (ICML 2024) embeds an imperceptible,
  *localized* (sample-level) watermark with a fast single-pass detector, robust
  to cropping/re-encoding [9][10] — the SFX analog of image watermarking, and a
  way to self-label foley's own generations and to *detect* AI audio on ingest.

Cross-cut with Report 07: this is the enforcement layer over the per-sound
`LicenseRecord`. foley should (a) stamp `ai_generated`, `generator`, `model`,
`prompt`, `seed`, `watermarked` into provenance; (b) offer a **disclosure export**
(a C2PA manifest + a human-readable "contains AI-generated audio" credit); and
(c) treat "generate a recognizably copyrighted sound" as a guarded operation.

**Open questions.** Does foley *embed* C2PA/AudioSeal at generation time or only
*record* provenance and leave signing to the host app? How to detect near-copyright
outputs (a "sounds like the THX Deep Note / a Star Wars blaster" filter)? Which
disclosure string satisfies Art. 50's "artistic work" carve-out without hampering
enjoyment?

**Primary sources.** EU AI Act Art. 50 text + EC FAQ [5][6]; C2PA Spec 2.2 +
Explainer [7][8]; AudioSeal paper + repo [9][10].

## 4. Versioning & reproducibility — the editable sound-design artifact  *(rank 4 — own prompt, with #2)*

**Why it matters.** The author's explicit north star (`design.md` §4): a
narration's sound design should be an **editable, re-renderable document**,
conceptually like cosmograph's *snapshots/stories* applied to the SFX layer — not
a baked mixdown. That means the output of `find()`/`weave()` is a *declarative
plan* (which cue, from where, at what onset/gain/pan, which transform, under which
license), separable from the rendered audio, diff-able, and re-runnable when a cue
is swapped or the index improves.

The industry already has the data model: **OpenTimelineIO (OTIO)** — "a modern EDL
with an API," a schema of tracks/clips/gaps/transitions with audio-track support
and a plugin system for import/export to DAW/NLE formats [11][12]. foley's
"sound-design timeline" (Prompt 6) should either *be* an OTIO document or map
losslessly to one, so a foley plan opens in Reaper/Premiere/DaVinci. Reproducibility
additionally requires pinning the *inputs*: index snapshot/version, model versions
(CLAP, generators, LLM), **generation seeds** (#13), and the decomposition itself —
the "run manifest" that ties to the telemetry of #2.

**Open questions.** Is the canonical artifact OTIO, or a foley-native JSON that
*exports* OTIO? Store cues by-reference (SoundRecord id) or by-value (embed bytes) —
the same by-ref/by-value trade-off already open for stories? How to make a plan
*deterministically* re-renderable when a source sound has since changed or been
delisted (content-address + provenance freeze)? Versioning/migration of the plan
schema (Zod-style preprocess, mirroring cosmograph's `schemaVersion`)?

**Primary sources.** OpenTimelineIO docs + AcademySoftwareFoundation repo [11][12].

## 5. Prompt engineering for SFX generation  *(rank 5 — fold into Prompt 2 + a guide)*

**Why it matters.** Generation quality is dominated by prompt *phrasing*, and the
craft differs from music prompting. Vendor guidance converges: **be specific about
material/size/environment/distance**, describe **temporal shape** ("starts quietly,
builds to a crash"), name **acoustic space** ("in a large cathedral"), and use
**one-shot / loop / impact** style words; for layered scenes, generate *individual*
effects and combine them rather than asking for a complex mix in one prompt
[13][14]. Stable Audio's guidance favors **comma-separated tag stacks** (source,
descriptor, environment, BPM for rhythmic beds) and supports **negative prompts**
("no music, no vocals") [15][16].

But this is not trivial reliability: a 2026 study on **semantic fragility** shows
text-to-audio output diverges acoustically under small prompt perturbations even
when embedding-space alignment is stable [17], and **temporal ordering** is a known
weak spot — mixing event and timing cues in one caption *hurts* fidelity; systems
like PicoAudio2/FreeAudio decouple them with explicit timestamps [18][19]. For
foley this argues: (a) a **prompt-template layer** in each generate adapter that
maps its unified `decompose` output (source · environment · duration · onset) into
the backend's preferred phrasing/tag order; (b) **generate-per-event, then
place**, never "generate the whole scene"; (c) negative-prompt defaults per
backend. This is the SFX analog of arioso's prompt-engineering guide — ship it as
a doc + adapter config, not code.

**Open questions.** Per-backend template tables (Stable-Audio tag-stack vs
ElevenLabs prose)? Auto-tuning `prompt_influence`/duration from the event type? A
prompt→verify→re-prompt refinement loop budget?

**Primary sources.** ElevenLabs SFX docs + prompting help [13][14]; Stability AI
Stable Audio prompt guide + Jordi Pons "On Prompting Stable Audio" [15][16];
semantic-fragility study [17]; PicoAudio2 / FreeAudio temporal control [18][19].

## 6. Accessibility — SFX captioning + audio description  *(rank 6 — fold into weave output)*

**Why it matters, and why it's nearly free for foley.** foley's `decompose_context`
*already* yields a salience-ranked list of sound events with onsets — which is
exactly the input a **caption/SDH track** needs. Emitting a WebVTT/SRT
**`[door creaks]`** cue per placed SFX is a small output adapter, not new
intelligence, and it turns an internal representation into an accessibility
deliverable. Two standards frame it:

- **Captions / SDH.** WCAG 2.2 **SC 1.2.2 (Captions, Prerecorded, Level A)**
  requires captions to include not just dialogue but **"meaningful sound effects"**;
  omitting important SFX is an explicit failure (Technique F8) [20][21]. Broadcast
  house styles fix the convention foley should emit: **sound effects in square
  brackets, present tense, title case** — *[Door slams]*, not *[door slamming]*
  (Netflix Timed Text Style Guide; BBC Subtitle Guidelines) [22].
- **Audio description.** WCAG 2.2 **SC 1.2.5 (Audio Description, Level AA)** covers
  narrating *visual* information for blind/low-vision users in dialogue gaps [23].
  The deeper connection: foley's whole premise — sound conveying scene — is an
  *aid* to visually-impaired listeners of otherwise-silent narration; a
  well-placed SFX layer is itself a form of AD, and the same event list can seed an
  AD script.

So accessibility is both an **output artifact** (an SDH caption sidecar foley can
generate for free) and a **strategic framing** (foley as an accessibility tool, not
just a production sweetener).

**Open questions.** Which caption format(s) to emit (WebVTT default; SRT; TTML for
broadcast)? How to pick which of many SFX are "meaningful" enough to caption
(reuse the salience score)? De-dupe repeated ambience so captions don't spam
*[wind blows]*?

**Primary sources.** WCAG 2.2 Understanding 1.2.2 + Technique F8 [20][21]; Netflix/
BBC caption style guides (bracket/tense/case conventions) [22]; WCAG 2.2
Understanding 1.2.5 (audio description) [23].

## 7. UX for auditioning — preview, shortlist, "more like this"  *(rank 7 — fold into agent surface / Phase 4)*

**Why it matters.** Report 05's headline number: **top-1 is right only ~30% of the
time while R@10 ≈ 0.7**. That gap *is* the case for a human-in-the-loop audition
UX — retrieval yields a *shortlist*, the human (or a preference model) picks, and
the pick feeds back. Classic **relevance feedback** is the mechanism: mark
returned items relevant/irrelevant, re-weight or re-form the query, iterate — long
established for content-based *audio* retrieval [24][25], and reframed for vector
search as a modern "search feedback loop" (average positive-example embeddings,
subtract negatives, re-query — a natural fit for CLAP) [26]. "More like this" is
just query-by-example over the CLAP space using a chosen clip as the anchor
(audio↔audio, already supported by the embedding).

For foley this is a tool-surface concern (Phase 4 already lists preview + "more
like this"): expose `preview(candidate)`, `similar_to(clip)`, and a
`refine(feedback)` that updates the query vector; persist the accepted pick into
the reproducible plan (#4) and optionally into a per-user preference profile
(borders on #11/personalization).

**Open questions.** Explicit thumbs vs implicit signal (which candidate was placed)?
How many feedback rounds before generating instead? Per-user/per-project "house
style" preference vectors — where stored, and do they leak identity (#11)?

**Primary sources.** Content-based audio retrieval with relevance feedback [24];
NL-query + relevance-feedback music search [25]; vector-search feedback-loop
write-up [26].

## 8. Real-time vs offline & latency budgets  *(rank 8 — fold into architecture)*

**Why it matters.** foley is **batch-first** (author a narration, render its sound
design), which relaxes the brutal budgets of *conversational* voice AI — where the
end-to-end target is ~**700 ms** and >1 s reads as failure [27][28]. foley does not
live in that regime for rendering. But two sub-cases inherit softer budgets: (a)
the **audition loop** (#7) — a preview should feel immediate (sub-second to first
audio), which shapes caching (#1) and a streaming preview path; and (b)
**interactive authoring** in an editor/assistant, where `find()` on a paragraph
should return a shortlist in a few seconds, pushing slow steps (verify, generation)
to async/background. The architecture consequence: separate a **fast interactive
path** (cached retrieval + cheap CLAP verify) from a **slow batch path** (audio-LM
verify, generation, mastering), and make `find()` streamable (emit candidates as
they clear verification). Conversational-AI's component-budget discipline
(overlap stages; measure p50/p95; time-to-first-audio) is a useful borrowed frame
even though the numbers differ [27][28].

**Open questions.** Do we need a real-time/live mode at all, or only interactive-
authoring + batch? What is the interactive `find()` SLO (e.g. shortlist < 3 s,
verified pick < 10 s)? Streaming vs blocking tool returns over MCP?

**Primary sources.** Voice-agent latency-budget analyses (700 ms threshold,
per-stage decomposition, TTFA) [27][28].

## 9. Multilingual / non-English context→sound  *(rank 9 — fold into Prompt 4/5)*

**Why it matters.** foley's *understanding* side is already fairly language-agnostic:
`decompose_context` runs on an LLM, so a French or Japanese narration can still be
turned into an English sound-event list. The weak link is the **retrieval encoder**:
CLAP is English-centric, so a non-English query (or non-English tags/captions in a
bring-your-own library) retrieves poorly. **GLAP** (General Language-Audio
Pretraining, 2025) is the concrete fix — a CLAP-style dual encoder extended to
**145 languages** via a multilingual (SONAR) text encoder, competitive on Clotho/
AudioCaps while adding strong multilingual retrieval and 50-language zero-shot
[29]; complementary work explicitly targets "bridging language gaps in audio-text
retrieval" [30]. Practical path: keep English CLAP as default but (a) translate
non-English decompositions to English query text before search (cheap, robust
today), and/or (b) make GLAP a drop-in `Embedder` (Report 04 already stamps the
model per record so a multilingual index can coexist).

**Open questions.** Translate-then-search vs native multilingual embedding — which
wins on SFX (not speech)? Is the sound *taxonomy* culture-bound (UCS is English;
ties to #14)? Onomatopoeia across languages ("woof" vs "ouah" vs "wan")?

**Primary sources.** GLAP (145 languages) [29]; Bridging Language Gaps in Audio-Text
Retrieval [30]; foley Report 05 already cites GLAP.

## 10. Spatial / immersive audio  *(rank 10 — fold into Prompt 6 / weave)*

**Why it matters (later).** Placing a cue not just in *time* but in *space* —
left/right pan, distance, binaural elevation, or full ambisonics — is the top of
the polish ceiling for immersive narration (headphone stories, VR/AR, spatial
podcasts). It belongs to `weave/` (Prompt 6), after basic ducking/mastering. The
tooling is mature: **ambisonics → binaural** rendering via HRTFs (SOFA files) is
standard, with open libraries (`libspatialaudio` — Ambisonic encode/decode +
binauralization, v0.4 2025) and Python-adjacent tooling; **SpatialScaper**
(arXiv 2401.12238, MARL) simulates room-accurate spatial soundscapes via RIRs and
is a ready way to *place and reverberate* a cue in a virtual room, plus generate
spatial training/eval data [31][32]. A 2025 survey (ASAudio) maps the research
landscape [33]. For foley, the near-term hook is a per-cue `pan`/`distance`/
`azimuth` field in the timeline (#4) that a spatial render backend consumes; full
ambisonics is a stretch goal.

**Open questions.** Stereo-pan-only default vs optional binaural/ambisonics
backend? Where do spatial params come from — decomposition ("a car passes left to
right"), or manual? Which HRTF/SOFA default; personalization of HRTF?

**Primary sources.** `libspatialaudio` [31]; SpatialScaper (arXiv 2401.12238) +
repo [32]; ASAudio survey [33].

## 11–15. Discovered dimensions *(fold into existing modules)*

**11. Privacy & data governance.** Narration text/audio is frequently
confidential or pre-release, yet foley's pipeline *exfiltrates* it: to LLM APIs
(decompose/verify), to ElevenLabs (generation prompts), and query text to
Freesound/other services. This needs (a) a local-first / offline mode (local LLM +
local Stable Audio Open + local index) for sensitive projects; (b) explicit
per-adapter data-egress declaration (does this backend see my narration?); (c)
redaction policy for what telemetry (#2) captures. Ties to the author's
`app-data-lifecycle` discipline (data ≠ code) and to licensing/provenance
(Report 07). *Fold into architecture (Prompt 10) + a note in Prompt 7.*

**12. API-quota orchestration & graceful degradation.** foley fans out over many
rate-limited, sometimes-flaky paid APIs plus an optional GPU. Robustness needs
per-adapter throttling/backoff/retry, circuit-breaking on outage, budget caps
($/run guardrails that stop runaway generation), and a **graceful-degradation
ladder**: cloud generation → local generation → retrieval-only → link-out. This
is a natural extension of the `SOURCE_CONFIG` adapter contract (declare rate
limits, cost, offline-capability). *Fold into the source-adapter contract.*

**13. Generation determinism & seed capture.** A plan (#4) is only reproducible
if a *generated* cue can be re-created byte-for-byte or at least perceptually — so
the generation **seed**, model version, and full params must be captured in the
`SoundRecord`/plan. Many backends expose a seed; some hosted APIs do not (record
that non-determinism explicitly, and fall back to caching the produced bytes).
*Fold into #4 + `SoundRecord` provenance.*

**14. Cultural / temporal plausibility (anachronism guard).** Retrieval optimizes
*acoustic* match, not *narrative* plausibility: a car horn in a medieval scene, a
US-style siren in a UK setting, a smartphone notification in a 1970s story are all
"correct" sounds that are *wrong* for the context. This is a verification concern
the current CLAP/audio-LM ladder won't catch — it needs an LLM plausibility check
("is a {cue} consistent with a {era/place/register} scene?") in `decompose` or
`verify`, and era/culture tags on library sounds. A genuinely under-named
correctness dimension. *Fold into `decompose`/`verify`; small research spike.*

**15. Sound continuity & motif consistency.** Across a long narration, the *same*
door should sound the same each time it appears, an ambience bed should persist
smoothly across decomposition windows rather than restart per paragraph, and
recurring motifs (a character's theme) should be reused. This is a *cross-window*
constraint the current per-paragraph decompose doesn't model. It lives in the
timeline data model (#4): a notion of persistent "beds" and reusable "named cues"
carried across the whole work. *Fold into the sound-design timeline (#4).*

---

## Recommendations for foley

**Four dimensions deserve their own future deep-research prompt** (they are deep,
standards-heavy, and cross-cutting enough that folding them into an existing
report would under-serve them):

- **Prompt 13 — Provenance, watermarking & disclosure-compliance** (dim. 3, +11/13
  provenance). Deep-dive AudioSeal embedding, C2PA audio manifests, and an EU AI
  Act Art. 50 compliance checklist (marking + disclosure export), building directly
  on Report 07. *Time-sensitive: Art. 50 applies 2 Aug 2026.*
- **Prompt 14 — Observability, run-artifacts & the editable sound-design document**
  (dims. 2 + 4 + 13 + 15, unified). The join is deliberate: a `find()`/`weave()`
  run should emit **one artifact** that is simultaneously the OTel trace (debug/
  eval), the OTIO-mappable re-renderable plan (reproduce/edit), and the provenance/
  seed record (compliance). This is the "cosmograph snapshots/stories for SFX"
  vision made concrete.
- **Prompt 15 — SFX generation prompt-engineering guide** (dim. 5). The SFX analog
  of arioso's prompt guide: per-backend template tables, temporal-decoupling
  patterns, negative-prompt defaults, and a prompt→verify→re-prompt loop. Extends
  Report 02.
- **(Optional) Prompt 16 — Immersive/spatial weave** (dim. 10). Only if immersive
  output becomes a target; otherwise a section of Prompt 6.

**The rest fold into existing modules/phases now:**

- **Caching & cost control (1)** → `index/` + architecture; add a semantic-cache
  admission test reusing `verify_match`; make the flywheel measurable (track
  generate-rate decay). Do this early — it changes the store schema.
- **Accessibility captioning/AD (6)** → a small `weave/` output adapter emitting
  WebVTT/SRT SDH cues (bracket/present-tense/title-case) from the existing event
  list. High value, low cost — build alongside Phase 5.
- **Auditioning UX + relevance feedback (7)** → agent tool surface (`preview`,
  `similar_to`, `refine`) in Phase 4.
- **Latency budgets (8)** → split fast-interactive vs slow-batch paths in the
  architecture; make `find()` streamable.
- **Multilingual (9)** → translate-then-search now; GLAP as a drop-in `Embedder`
  later (Report 04/05 already anticipate model-swap).
- **Privacy/governance (11)** → an offline/local-only mode + per-adapter data-egress
  declaration in `SOURCE_CONFIG`; redaction policy for telemetry.
- **Quota orchestration & degradation (12)** → extend the source-adapter contract
  with rate/cost/offline metadata and a degradation ladder.
- **Determinism/seed (13), continuity/motif (15)** → fields + semantics in the
  timeline/`SoundRecord` (folded into Prompt 14).
- **Anachronism guard (14)** → an LLM plausibility check in `decompose`/`verify`;
  worth a short spike as it is a correctness gap nothing else catches.

**Net.** The two highest-risk omissions are **disclosure/watermarking** (a hard
legal deadline against *published* output) and **observability tied to a
reproducible run-artifact** (without it, foley cannot be debugged, evaluated, or
delivered as the editable sound-design document the design promises). Everything
else is either cheap-to-fold-now (caching, captioning, auditioning) or a
deliberate later deepening (spatial, multilingual).

---

## REFERENCES

1. Bang F. *GPTCache: An Open-Source Semantic Cache for LLM Applications Enabling Faster Answers and Cost Savings.* NLP-OSS Workshop @ EMNLP 2023. [aclanthology.org/2023.nlposs-1.24](https://aclanthology.org/2023.nlposs-1.24/) · arXiv:2311.17174 · repo [github.com/zilliztech/GPTCache](https://github.com/zilliztech/GPTCache)
2. Regmi S. et al. *GPT Semantic Cache: Reducing LLM Costs and Latency via Semantic Embedding Caching* (2024). [arxiv.org/abs/2411.05276](https://arxiv.org/abs/2411.05276)
3. OpenTelemetry. *Inside the LLM Call: GenAI Observability with OpenTelemetry* (blog, 2026) + Semantic Conventions for Generative AI. [opentelemetry.io/blog/2026/genai-observability](https://opentelemetry.io/blog/2026/genai-observability/) · [opentelemetry.io/docs/specs/semconv/gen-ai](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
4. Horovits D. *OpenTelemetry for GenAI and the OpenLLMetry project.* (GenAI SIG scope, 2024–25). [horovits.medium.com](https://horovits.medium.com/opentelemetry-for-genai-and-the-openllmetry-project-81b9cea6a771)
5. EU Artificial Intelligence Act — *Article 50: Transparency Obligations for Providers and Deployers of Certain AI Systems.* [artificialintelligenceact.eu/article/50](https://artificialintelligenceact.eu/article/50/)
6. European Commission. *Transparency obligations under Article 50 of the AI Act* (FAQ; obligations apply 2 Aug 2026). [digital-strategy.ec.europa.eu](https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act)
7. C2PA. *Content Credentials: C2PA Technical Specification 2.2* (2025-05-01). [spec.c2pa.org … 2.2](https://spec.c2pa.org/specifications/specifications/2.2/specs/_attachments/C2PA_Specification.pdf)
8. C2PA. *Content Credentials Explainer* (2.4). [spec.c2pa.org … explainer](https://spec.c2pa.org/specifications/specifications/2.4/explainer/Explainer.html)
9. San Roman R., Fernandez P., et al. *Proactive Detection of Voice Cloning with Localized Watermarking* (AudioSeal, ICML 2024). [arxiv.org/abs/2401.17264](https://arxiv.org/abs/2401.17264) · [ai.meta.com/research/publications/…](https://ai.meta.com/research/publications/proactive-detection-of-voice-cloning-with-localized-watermarking/)
10. AudioSeal implementation. [github.com/facebookresearch/audioseal](https://github.com/facebookresearch/audioseal)
11. Academy Software Foundation. *OpenTimelineIO documentation* (v0.18, stable). [opentimelineio.readthedocs.io/en/stable](https://opentimelineio.readthedocs.io/en/stable/)
12. Academy Software Foundation. *OpenTimelineIO — timeline structure / adapters* (repo). [github.com/AcademySoftwareFoundation/OpenTimelineIO](https://github.com/AcademySoftwareFoundation/OpenTimelineIO)
13. ElevenLabs. *Sound Effects — capabilities & product guide.* [elevenlabs.io/docs/overview/capabilities/sound-effects](https://elevenlabs.io/docs/overview/capabilities/sound-effects)
14. ElevenLabs. *How do I prompt for sound effects?* (help article). [help.elevenlabs.io … 25735604945041](https://help.elevenlabs.io/hc/en-us/articles/25735604945041-How-do-I-prompt-for-sound-effects)
15. Stability AI. *Stable Audio 2.5 Prompt Guide* + *stable-audio-3 prompting.md.* [stability.ai/implementations/stable-audio-25-prompt-guide](https://stability.ai/implementations/stable-audio-25-prompt-guide) · [github.com/Stability-AI/stable-audio-3 … prompting.md](https://github.com/Stability-AI/stable-audio-3/blob/main/docs/guides/prompting.md)
16. Pons J. *On Prompting Stable Audio.* [jordipons.me/on-prompting-stable-audio](https://www.jordipons.me/on-prompting-stable-audio/)
17. *Evaluating Semantic Fragility in Text-to-Audio Generation Systems Under Controlled Prompt Perturbations* (2026). [arxiv.org/html/2603.13824](https://arxiv.org/html/2603.13824)
18. *PicoAudio2: Temporal Controllable Text-to-Audio Generation with Natural Language Description* (2025). [arxiv.org/pdf/2509.00683](https://arxiv.org/pdf/2509.00683)
19. *FreeAudio: Training-Free Timing Planning for Controllable Long-Form Text-to-Audio Generation* (2025). [arxiv.org/pdf/2507.08557](https://arxiv.org/pdf/2507.08557)
20. W3C WAI. *Understanding SC 1.2.2: Captions (Prerecorded)* (WCAG 2.2). [w3.org/WAI/WCAG22/Understanding/captions-prerecorded](https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded.html)
21. W3C. *F8: Failure of SC 1.2.2 due to captions omitting … important sound effects.* [w3.org/TR/WCAG20-TECHS/F8](https://www.w3.org/TR/WCAG20-TECHS/F8.html)
22. Netflix. *Timed Text Style Guide: General Requirements* (SFX in square brackets, present tense, title case); BBC Subtitle Guidelines. [partnerhelp.netflixstudios.com … General-Requirements](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements) · [bbc.github.io/subtitle-guidelines](https://bbc.github.io/subtitle-guidelines/)
23. W3C WAI. *Understanding SC 1.2.5: Audio Description (Prerecorded)* (WCAG 2.2). [w3.org/WAI/WCAG21/Understanding/audio-description-prerecorded](https://www.w3.org/WAI/WCAG21/Understanding/audio-description-prerecorded.html)
24. *Content-based audio retrieval with relevance feedback.* Pattern Recognition Letters (ScienceDirect). [sciencedirect.com … S0167865505001947](https://www.sciencedirect.com/science/article/abs/pii/S0167865505001947)
25. *Searching for Music Using Natural Language Queries and Relevance Feedback.* Springer (AMR). [link.springer.com/chapter/10.1007/978-3-540-79860-6_9](https://link.springer.com/chapter/10.1007/978-3-540-79860-6_9)
26. Qdrant. *Relevance Feedback in Informational Retrieval* (search feedback loop for vector search). [qdrant.tech/articles/search-feedback-loop](https://qdrant.tech/articles/search-feedback-loop/)
27. Gradium. *Best Low-Latency TTS APIs in 2026: TTFA, P99 and Pipeline Impact.* [gradium.ai/content/best-low-latency-tts-apis-2026](https://gradium.ai/content/best-low-latency-tts-apis-2026)
28. AlterSquare. *Building a Production Voice Agent: The Latency Budget Nobody Talks About* (~700 ms threshold; per-stage budget). [altersquare.io/blog/production-voice-agent-latency-budget](https://altersquare.io/blog/production-voice-agent-latency-budget)
29. *GLAP: General contrastive audio-text pretraining across domains and languages* (2025; 145 languages, SONAR text encoder). [arxiv.org/abs/2506.11350](https://arxiv.org/abs/2506.11350) · model [huggingface.co/mispeech/GLAP](https://huggingface.co/mispeech/GLAP)
30. *Bridging Language Gaps in Audio-Text Retrieval* (2024). [arxiv.org/pdf/2406.07012](https://arxiv.org/pdf/2406.07012)
31. VideoLAN. *libspatialaudio* — Ambisonic encode/decode + binauralization (v0.4, 2025). [github.com/videolan/libspatialaudio](https://github.com/videolan/libspatialaudio) · [jbkempf.com/blog/2025/libspatialaudio-0.4](https://jbkempf.com/blog/2025/libspatialaudio-0.4/)
32. Roman I.R., Ick C., et al. *SpatialScaper: A Library to Simulate and Augment Soundscapes for Sound Event Localization and Detection in Realistic Rooms* (2024). [arxiv.org/abs/2401.12238](https://arxiv.org/abs/2401.12238) · repo [github.com/marl/SpatialScaper](https://github.com/marl/SpatialScaper)
33. *ASAudio: A Survey of Advanced Spatial Audio Research* (2025). [aclanthology.org/2025.ijcnlp-long.25](https://aclanthology.org/2025.ijcnlp-long.25.pdf)
34. Kreuk F. et al. *AudioGen: Textually Guided Audio Generation* (2022; autoregressive text-to-sound, temporal priors). [arxiv.org/abs/2209.15352](https://arxiv.org/abs/2209.15352)

---

*Access date for all URLs: 2026-07-22. Standards/versions noted inline where they
move fast (C2PA 2.2/2.4; WCAG 2.2; EU AI Act Art. 50 in force 2026-08-02;
OpenTelemetry GenAI semconv 2024→2026; OTIO v0.18).*
