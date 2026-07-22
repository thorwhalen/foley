# foley — research

This folder is foley's research home (same convention as `arioso`'s `misc/docs/`).
Twelve cited reports + a prompt library, all following the conventions below.

## Start here

- **[`10-facade-architecture.md`](10-facade-architecture.md)** — the **authoritative
  architecture**: it synthesizes reports 01–12 into one buildable design (component
  diagram, reconciled data models, façade API, adapter/protocol contracts, module tree,
  dependency graph, and the phased epic/subtask breakdown). Read this first; the others
  are the depth behind it. *(Prompt 10)*
- **[`deep-research-prompts.md`](deep-research-prompts.md)** — the prompt library: 12
  ready-to-run deep-research prompts. Hand any to a research agent to (re)generate or
  deepen a report.

## Reports

| # | File | Dimension |
|---|------|-----------|
| 01 | [`01-sfx-source-apis.md`](01-sfx-source-apis.md) | Where foley gets ready-made sounds (Freesound, BBC, … + UCS taxonomy) |
| 02 | [`02-genai-sfx-generation.md`](02-genai-sfx-generation.md) | Generating sounds (Stable Audio, ElevenLabs SFX, AudioGen; local + API) |
| 03 | [`03-sound-recognition-tagging.md`](03-sound-recognition-tagging.md) | Raw audio → searchable metadata (tagging, zero-shot CLAP, captioning, segmentation) |
| 04 | [`04-embeddings-indexing-search.md`](04-embeddings-indexing-search.md) | Embeddings (CLAP), vector stores, hybrid search, the sound schema |
| 05 | [`05-context-retrieval-and-agent.md`](05-context-retrieval-and-agent.md) | The core: narrative-context → right sound, and the search-agent / MCP design |
| 06 | [`06-weaving-mixing-mastering.md`](06-weaving-mixing-mastering.md) | Weaving into narration: alignment, ducking, LUFS mastering, the timeline model |
| 07 | [`07-licensing-provenance.md`](07-licensing-provenance.md) | Licensing, rights, provenance, attribution, watermarking, disclosure, safety |
| 08 | [`08-evaluation-quality.md`](08-evaluation-quality.md) | Evaluation: retrieval metrics, audio QC, fit-judging, the layered harness |
| 09 | [`09-audio-io-dsp-storage.md`](09-audio-io-dsp-storage.md) | Audio I/O, formats, DSP primitives, and the `dol` storage layout |
| 10 | [`10-facade-architecture.md`](10-facade-architecture.md) | **Authoritative architecture synthesis** (read first) |
| 11 | [`11-bootstrap-corpora-benchmarks.md`](11-bootstrap-corpora-benchmarks.md) | Bootstrap corpora, benchmarks, and the golden eval set |
| 12 | [`12-additional-dimensions.md`](12-additional-dimensions.md) | Meta-scan: the dimensions the other reports under-cover |

## Conventions

- Vancouver-style numbered citations (`[1]`, `[2]`, …) + a `REFERENCES` section with
  `[name](url)` links.
- Primary sources over blogs; note versions/access dates (this landscape moves fast).
- Every report ends with a **"Recommendations for foley"** section mapping findings to
  the façade design.

## Status

All 12 reports are complete (two background research passes + the capstone synthesis).
They are a living starting point — re-run any prompt from the prompt library to deepen
a report. Report 12 proposes four follow-on prompts (13–16: provenance/watermarking
deep-dive, observability/run-artifact, an SFX prompt-engineering guide, and optional
spatial-weave) for future rounds.
