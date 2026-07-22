# foley — Roadmap

A phased build order derived from [`design.md`](design.md) and the [`research/`](research/)
reports. The strategy is **retrieval-first**: get a searchable library working before
sources multiply or generation/weaving deepen — validate "find the right sound" end to
end early.

## Phase 0 — Scaffold & research  ✅ (done)

- [x] Name (`foley`), repo, wads setup, CI, `misc/docs/`
- [x] Five research reports (source APIs, generation, recognition, indexing, retrieval-agent)
- [x] Deep-research prompt library (Prompts 1–12)

## Phase 1 — Library & Index (the retrieval foundation)

*The keystone. Everything else plugs into this.*

- [ ] `SoundRecord` + `LicenseRecord` schemas (`base.py`) — the canonical SSOT record
- [ ] `SoundLibrary` façade over injected `dol` stores (blobs + metadata) — local-first
- [ ] `Embedder` protocol + CLAP default (`laion/larger_clap_general`)
- [ ] LanceDB `vindex`+`kindex`; hybrid search + RRF (`search.py`); sqlite-vec fallback
- [ ] Ingestion pipeline (`ingest.py`): probe → PANNs tag → CLAP zero-shot → EnCLAP caption → embed
- [ ] UCS + AudioSet taxonomy tables (`taxonomy/`)
- [ ] `foley.ingest(folder)` and `foley.search(query)` working end to end
- [ ] Seed corpus: FSD50K (CC0/CC-BY) as a starter library

**Done when:** `foley.ingest("~/sounds")` then `foley.search("thunder")` returns
ranked, license-tagged hits by keyword + semantics.

## Phase 2 — Sources (retrieve + generate adapters)

- [ ] Source adapter contract (`SOURCE_CONFIG`, registry auto-discovery) — arioso pattern
- [ ] **Freesound** retrieve adapter (CC0-filtered) — `foley.add_from("freesound", …)`
- [ ] **Stable Audio Open** generate adapter (local default) with `commercial_ok` guardrail
- [ ] **ElevenLabs Sound Effects** generate adapter (hosted default)
- [ ] `foley.generate(prompt, backend=…)` with unified param vocabulary
- [ ] Stub adapters for partner-gated pro APIs (Epidemic/Storyblocks/…)

**Done when:** foley can pull CC0 sounds from Freesound and generate SFX locally/hosted,
all landing in the library with correct per-sound license flags.

## Phase 3 — The search agent (`find(context)`)

*The headline capability.*

- [ ] `decompose_context` — LLM: story paragraph → salience-ranked diegetic sound-event list
- [ ] `search_sounds` tool over the hybrid index
- [ ] `verify_match` — CLAP-score → audio-LM listen-check → LLM-judge ladder
- [ ] `decide` — generate-vs-retrieve policy; cache accepted generations back
- [ ] `foley.find(context)` returns a verified shortlist of candidates

**Done when:** given a paragraph, foley returns the right sounds for its salient moments,
generating when the library has no match.

## Phase 4 — MCP server & preview UX

- [ ] Expose the tool set as an MCP server via `py2mcp`
- [ ] Preview / audition surface (shortlists, "more like this", human-in-the-loop pick)
- [ ] CLI entry (`python -m foley …`)
- [ ] `check_requirements` / setup-guidance (accompy-style) for optional deps & models

## Phase 5 — Weave (compose onto narration)

*Needs research **Prompt 6** first (alignment/mixing/mastering).*

- [ ] Forced-alignment of narration → word timestamps
- [ ] Ducking/side-chain + stereo/distance placement + crossfades
- [ ] LUFS/EBU-R128 mastering to platform targets
- [ ] Editable, re-renderable **sound-design timeline** data model
- [ ] `foley.weave(narration, candidates)` → mixed output

## Phase 6 — Evaluation, breadth & polish

- [ ] Eval harness: audio QC → retrieval metrics (R@k, mAP) → LLM/audio-LM fit-judging (**Prompt 8**)
- [ ] Golden eval set: (narrative-context → expected-sound) pairs (**Prompt 11**)
- [ ] More source & generation adapters; MS-CLAP/BEATs/Qwen2-Audio quality upgrades
- [ ] Provenance/attribution export; disclosure/watermarking (**Prompt 7, 12**)

## Parallel research track (Prompts 6–12)

The prompt library's remaining prompts feed the phases above; run them ahead of the
phase that needs them:

| Prompt | Feeds |
|--------|-------|
| 6 — weaving/mixing/mastering | Phase 5 |
| 7 — licensing/provenance | Cross-cutting, Phase 2/6 |
| 8 — evaluation | Phase 6 |
| 9 — audio I/O & storage foundation | Phase 1 |
| 10 — façade/architecture synthesis | Phase 1 (refines this design) |
| 11 — bootstrap corpora & benchmarks | Phase 1, 6 |
| 12 — meta-scan (what we're forgetting) | Ongoing |
