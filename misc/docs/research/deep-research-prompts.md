# foley — Deep Research Prompt Library

**Purpose.** This file is a library of ready-to-run **deep-research prompts** for the
foley project. Each prompt is self-contained: hand it to a research-capable AI agent
(one with live web search + the Hugging Face hub) and it will produce a rigorous,
cited report on one dimension of the problem. Together they cover everything an agent
building foley should understand — the *source* of sounds, the *indexing* of sounds,
the *selection* of the right sound for a context, the *weaving* of sounds into
narration, and the cross-cutting concerns (licensing, evaluation, architecture,
and the aspects that are easy to forget).

**What foley is.** A unified Python **façade for sound effects (SFX)** used to weave
sound into AI-generated narrations (stories & commentaries). Two problems sit at its
heart: **(1) where do the sounds come from** — a bring-your-own library, SFX-service
APIs, and generative-AI models (local + hosted); and **(2) how do we find the *right*
sound for a given narrative context** — which requires every sound to be well indexed
(keyword *and* semantic search) and, on top of that, a search **AI agent**. foley
follows the design of the author's [`arioso`](https://github.com/thorwhalen/arioso)
package (a unified façade over 14 AI music-generation backends: one entry function,
config-driven plugin adapters, a unified parameter vocabulary translated to each
backend's native names, zero required core deps with lazy per-backend optional-deps,
research docs in `misc/docs/`). Where arioso *generates music*, foley is
**retrieval-first**: generation is just one of several sound sources.

## How to use these prompts

- **One prompt → one agent → one report.** Run them in parallel; they are independent.
- **House conventions for every report** (the author's standing preference):
  - **Vancouver-style numbered citations** `[1]`, `[2]`, … inline, with a
    **REFERENCES** section at the end using `[name](url)` hyperlinks.
  - Prefer **primary sources** (official API docs, papers, model cards, license
    pages) over blogs/marketing. Note **versions and access dates** — this landscape
    moves fast.
  - End every report with a **"Recommendations for foley"** section that maps
    findings onto the façade design (what to build first, what the adapter/interface
    should look like, defaults to pick).
  - Write reports into `misc/docs/research/` with a `#` title + a 2–3 sentence
    abstract, then tables → detail → recommendations.
- **Seeded already.** An initial research pass has seeded reports `01`–`05` in this
  folder (matching Prompts 1–5). Those prompts are kept here so the reports can be
  **re-run and deepened** later; Prompts 6–12 are not yet seeded and are the natural
  next fan-out.

## Map of prompts

| # | Prompt | Dimension | Seeded report |
|---|--------|-----------|---------------|
| 1 | SFX source APIs & sound libraries | Source (retrieve) | `01-sfx-source-apis.md` |
| 2 | Generative-AI SFX generation (local + API) | Source (generate) | `02-genai-sfx-generation.md` |
| 3 | Sound recognition, tagging, captioning, segmentation | Index (understand) | `03-sound-recognition-tagging.md` |
| 4 | Audio embeddings, indexing, vector search, schema | Index (store & search) | `04-embeddings-indexing-search.md` |
| 5 | Context→sound retrieval SOTA & the search agent | Select (the core) | `05-context-retrieval-and-agent.md` |
| 6 | Weaving SFX into narration: alignment, timing, mixing, mastering | Compose | — |
| 7 | Licensing, rights, provenance & attribution | Cross-cutting | — |
| 8 | Evaluation & quality (retrieval metrics, audio QC, human eval) | Cross-cutting | — |
| 9 | Audio I/O, formats, DSP fundamentals & storage | Foundation | — |
| 10 | Façade & system architecture (the arioso analog for SFX) | Design | — |
| 11 | Bootstrap corpora & benchmarks for a starter library | Data | — |
| 12 | Dimensions we haven't named yet (meta-scan) | Cross-cutting | — |

---

## Prompt 1 — SFX source APIs & sound libraries

> **Role.** You are researching *where foley gets ready-made sounds*.
>
> **Investigate** the best services/APIs to source SFX programmatically. For each,
> report: whether it has an API, the interface (REST endpoints, key query params, auth),
> library size/coverage, **license terms** (commercial use, redistribution, attribution),
> pricing/tiers, rate limits, download formats, and what metadata (tags/categories/
> audio descriptors) it returns. Cover at least: **Freesound** (API v2 — the primary
> programmable CC library; note CC0 vs CC-BY vs Sampling+ and the audio-analysis
> descriptors it exposes), **BBC Sound Effects** (RemArc), **Zapsplat**, **Soundly**,
> **Epidemic Sound**, **Storyblocks**, **Pond5**, **Pixabay Audio**, **Mixkit**,
> **Uppbeat**, **ProSoundEffects**, **Boom Library**. Add any strong sources you find.
> Also cover **free bulk corpora** usable as a starter library: **Sonniss
> GameAudioGDC** packs, **FSD50K**, **AudioSet**. Finally, research the **Universal
> Category System (UCS)** — the industry SFX naming/category taxonomy — and how foley
> should adopt it as canonical categories.
>
> **Deliver** a comparison table of all services + per-service detail + a UCS section
> + a "Recommendations for foley" section: which sources to adapter-ize first, how to
> track license *per sound*, and how a `source adapter` plugin should look (mirroring
> arioso's per-platform `PLATFORM_CONFIG` pattern). Follow house conventions above.

## Prompt 2 — Generative-AI SFX generation (local models + hosted APIs)

> **Role.** You are researching *how foley generates sounds it can't find*.
>
> **Investigate** text-to-audio / text-to-SFX generation. Two buckets:
> **(a) Hosted APIs** — ElevenLabs **Sound Effects** API (params like `text`,
> `duration_seconds`, `prompt_influence`; max length; formats; pricing), Stability AI
> **Stable Audio** API, and hosted endpoints on **fal.ai** / **Replicate** (AudioGen,
> Stable Audio Open, AudioLDM2). **(b) Local/open models** — Meta **AudioGen**
> (audiocraft), **Stable Audio Open 1.0 / Small**, **AudioLDM / AudioLDM2**, **Tango /
> Tango 2**, **Make-An-Audio 1/2**, **Auffusion**, **GenAU**, video-conditioned
> **MMAudio**. For each option report: quality, max duration, latency, VRAM/hardware,
> **license of both weights and generated output** (commercial use!), and a **code
> snippet** showing how to invoke it. Clarify text-to-**SFX** vs text-to-**music** and
> the conditioning controls (duration, prompt influence, negative prompts). Use the
> **Hugging Face hub** to verify model sizes/licenses/downloads.
>
> **Deliver** a comparison table (option | access | max duration | quality | VRAM |
> license | how-to-invoke) + per-option detail with snippets + a "Recommendations for
> foley" section naming a **default local model** and a **default hosted API**, and how
> each becomes a generation adapter in foley's arioso-style façade. House conventions.

## Prompt 3 — Sound recognition, tagging, captioning & segmentation

> **Role.** You are researching *how foley turns a raw audio file into searchable
> metadata* — so a bring-your-own library becomes findable.
>
> **Investigate** four capabilities. **(a) Audio tagging/classification**: PANNs
> (CNN14), AST, BEATs, HTS-AT, PaSST, YAMNet — all AudioSet-trained (527 classes,
> AudioSet ontology). Give mAP numbers, how to run, license, output shape.
> **(b) Zero-shot tagging with CLAP** against an arbitrary vocabulary (essential for a
> custom taxonomy like UCS) — accuracy vs supervised taggers. **(c) Automated audio
> captioning** (a natural-language description of a clip): Pengi, EnCLAP, Qwen2-Audio,
> Audio-Flamingo, SALMONN, WavCaps-trained systems; benchmarks on Clotho / AudioCaps
> (CIDEr, SPICE, SPIDEr). Captions are gold for keyword + semantic search.
> **(d) Sound Event Detection (SED)** for segmenting long recordings into timestamped
> events (DCASE Task 4), and **source separation** for splitting layered recordings.
> Use the **Hugging Face hub** for model cards/licenses.
>
> **Deliver** comparison tables (taggers; captioners) + per-model detail with snippets
> + a "Recommendations for foley" section proposing a concrete **ingestion pipeline**:
> (optional segment) → tag (AudioSet supervised + zero-shot CLAP) → caption → emit
> metadata, with recommended defaults and tradeoffs. House conventions.

## Prompt 4 — Audio embeddings, indexing, vector search & the sound schema

> **Role.** You are researching *how foley stores sounds so they're searchable by
> keyword AND meaning*, local-first but cloud-scalable (fits a `dol`/store abstraction).
>
> **Investigate**: **(a) Text–audio joint embeddings** — **CLAP** (LAION-CLAP,
> Microsoft MS-CLAP) as the joint space that enables *text-query → audio* retrieval and
> *audio ↔ audio* similarity; also audio-only embeddings (PANNs, VGGish, OpenL3, PaSST).
> Which should be foley's default embedding and why. **(b) Indexing infrastructure** —
> compare FAISS, LanceDB, Qdrant, Chroma, Milvus, pgvector, sqlite-vec on local-first
> ergonomics, embeddability, scale, metadata filtering, and cloud path. **(c) Hybrid
> search** — combining BM25/keyword (over tags + captions) with vector (CLAP) search,
> plus fusion/reranking (e.g. reciprocal rank fusion); why hybrid beats pure-vector for
> SFX. **(d) The sound metadata schema** — propose a canonical record (id, source,
> uri/blob-ref, license, tags, caption, UCS category, AudioSet labels, CLAP embedding,
> duration, sample_rate, channels, loudness LUFS, provenance). **(e) Taxonomies** —
> AudioSet ontology + UCS as the category/filters backbone.
>
> **Deliver** an embeddings comparison, a vector-store comparison table, a hybrid-search
> design, the proposed schema (code block), a taxonomy section, and a "Recommendations
> for foley" section describing a **local-first index architecture** (a `Mapping` of
> sounds + a vector index + a keyword index) that scales to cloud. House conventions.

## Prompt 5 — Context→sound retrieval SOTA & the search agent (the core)

> **Role.** You are researching *the heart of foley*: given a narrative context (a
> paragraph of story/commentary), find or generate the right sound(s) — and the AI
> **agent** that does this interactively.
>
> **Investigate**: **(a) Language-based audio retrieval SOTA** — DCASE **Task 6b**,
> datasets **Clotho** / **AudioCaps**, CLAP-based retrieval, metrics (R@1/5/10, mAP@10),
> and the current best methods with numbers. **(b) Narrative context → sound queries** —
> LLM-based **scene/sound decomposition** ("list the discrete sound events implied by
> this passage"), query formulation & expansion, **salience** (which moments deserve a
> sound), diegetic vs non-diegetic; include any published work on automatic Foley /
> text-to-soundscape / video-Foley. **(c) Reranking & verification** — CLAP text↔audio
> scoring, LLM-as-judge, and **audio-language models** (e.g. Qwen2-Audio) that can
> "listen" and confirm a candidate matches intent. **(d) Generate-vs-retrieve policy** —
> when to fall back to generation. **(e) Agent architecture** — the tool surface
> (`search_sounds`, `generate_sound`, `preview/listen`, `refine_query`,
> `place_in_timeline`), an agentic retrieve→verify→refine loop, human-in-the-loop
> preview, and exposing the toolset as an **MCP server** (the author has `py2mcp`).
>
> **Deliver** a SOTA survey with metrics, the context→query pipeline, the
> reranking/verification design, the generate-vs-retrieve policy, the agent/tool/MCP
> design, and a "Recommendations for foley" end-to-end pipeline + tool schema. House
> conventions.

## Prompt 6 — Weaving SFX into narration: alignment, timing, mixing & mastering

> **Role.** You are researching *how foley actually places a chosen sound into a
> narration so it sounds professional* — the "weave" step, which is more than
> concatenation.
>
> **Investigate**: **(a) Timing / placement** — forced alignment of narration audio to
> its transcript to get word-level timestamps (WhisperX, `aeneas`, Montreal Forced
> Aligner, NeMo), so a sound can be triggered at the exact word/beat; and heuristics for
> anchoring a cue to a sentence, phrase, or scene boundary. **(b) Mixing** — automatic
> **ducking / side-chain** so SFX sit under or around narration; gain staging; stereo
> panning and distance cues; reverb/room to place a sound in a scene; crossfades and
> fade-in/out to avoid clicks. **(c) Mastering / loudness** — **EBU R128 / ITU-R BS.1770
> LUFS** integrated-loudness targets, true-peak limiting, platform loudness norms
> (podcast −16 LUFS, broadcast −23 LUFS, streaming), and the tooling (`pyloudnorm`,
> `ffmpeg loudnorm`, `pydub`, `sox`). **(d) One-shots vs beds vs stingers** — how
> ambience beds, one-shot hits, and transitional stingers differ in placement & looping.
> **(e) A render model** — a timeline/edit-decision-list representation of a narration's
> sound design that is **editable and reproducible** (so the SFX layer can be re-rendered
> or tweaked, not baked once).
>
> **Deliver** the alignment options, a mixing/ducking recipe, concrete LUFS targets per
> platform, and a "Recommendations for foley" section proposing an editable **sound-design
> timeline** data model + a default render/mix pipeline. House conventions.

## Prompt 7 — Licensing, rights, provenance & attribution

> **Role.** You are researching *the legal/traceability layer* — because foley's output
> gets **published**, and every sound (sourced or generated) carries rights obligations.
>
> **Investigate**: **(a) Creative Commons & royalty-free** — CC0 vs CC-BY vs CC
> Sampling+ vs "royalty-free" vs "rights-managed"; what each requires for commercial use
> and redistribution inside a derivative (a narrated video). **(b) Attribution
> mechanics** — how to auto-generate correct credit strings, and where they must appear.
> **(c) AI-generated audio** — the output-ownership and usage terms of ElevenLabs SFX,
> Stability/Stable Audio, and the licenses of open weights (AudioGen, Stable Audio Open
> community license) — can outputs be used commercially, and under what constraints?
> **(d) Provenance** — tracking *per sound* its source, license, and any transformations,
> plus emerging **AI-audio watermarking / disclosure** (e.g. AudioSeal, C2PA for audio)
> and platform disclosure rules. **(e) Safety** — voice/likeness and copyright pitfalls
> (e.g. generating recognizable copyrighted sounds).
>
> **Deliver** a license-comparison table, an attribution-string spec, an AI-terms
> summary per provider, and a "Recommendations for foley" section: the **provenance
> fields** every sound record must carry, and a policy for filtering candidates by
> license compatibility with the user's intended use. House conventions.

## Prompt 8 — Evaluation & quality (retrieval metrics, audio QC, human eval)

> **Role.** You are researching *how foley knows it's doing a good job* — both
> "did we retrieve the right sound?" and "is the sound technically clean?".
>
> **Investigate**: **(a) Retrieval evaluation** — recall@k, mAP@10, nDCG for
> text→audio retrieval; how to build a small gold set of (context → ideal sound)
> pairs; CLAP score as a cheap proxy relevance signal and its limits. **(b) Fit
> evaluation** — using an audio-language model or LLM-as-judge to rate whether a clip
> matches a described intent; inter-rater reliability; A/B and preference testing.
> **(c) Audio QC** — automatic checks for clipping, DC offset, silence, excessive
> noise (SNR), abrupt starts/ends, loudness outliers, and duration sanity. **(d)
> Generation QC** — detecting failed/garbled generations, and quality metrics for
> generated audio (FAD — Fréchet Audio Distance, CLAP-score). **(e) Regression** — how
> to keep a test harness so index/model upgrades don't silently degrade results
> (mirror the author's economist/trophy testing philosophy: cheap API-level checks
> first).
>
> **Deliver** a metrics catalog, a gold-set construction recipe, an audio-QC checklist
> (with thresholds), and a "Recommendations for foley" section proposing a layered eval
> harness (unit QC → retrieval metrics → human/LLM fit-judging). House conventions.

## Prompt 9 — Audio I/O, formats, DSP fundamentals & storage

> **Role.** You are researching *the boring-but-load-bearing foundation* every other
> layer sits on.
>
> **Investigate**: **(a) Formats & codecs** — wav/flac/mp3/ogg/opus/aac; when to use
> each for storage vs delivery; sample rates (44.1/48 kHz), bit depth, mono vs stereo,
> and normalization to a canonical working format. **(b) Python audio I/O** — `soundfile`,
> `librosa`, `audioread`, `pydub`, `torchaudio`, `ffmpeg-python`: strengths, gotchas
> (resampling quality, mp3 decode, streaming large files). **(c) Core DSP ops** — trim
> silence, fades, resample, channel up/down-mix, time-stretch, pitch-shift, loudness
> normalize — with the recommended library per op. **(d) Storage** — how to hold audio
> blobs behind a `dol` `Mapping` so a local folder store can be swapped for S3/blob
> without touching business logic; content-addressed storage & de-duplication;
> separating heavy audio bytes from lightweight metadata/index. **(e) Performance** —
> lazy decode, caching decoded arrays/embeddings, and batch processing large libraries.
>
> **Deliver** a format/codec table, a library-per-operation cheat sheet, and a
> "Recommendations for foley" section: a canonical working audio representation + a
> `dol`-based store layout (bytes store + metadata store + vector index) that scales from
> a local folder to cloud blob storage. House conventions.

## Prompt 10 — Façade & system architecture (the arioso analog for SFX)

> **Role.** You are designing *foley's architecture* by analogy to `arioso`/`accompy`
> and by synthesizing the other reports.
>
> **Study** the author's existing façades: `arioso` (config-driven per-backend plugin
> adapters under `platforms/`, a unified affordance vocabulary translated to native
> params, `registry.py` auto-discovery, `services`/`generators` accessors, zero required
> core deps, `dol`/`config2py` for config) and `accompy` (progressive-disclosure API +
> `Config` object, protocol-based extensibility, `check_requirements`/`verify_and_setup`
> system-dependency guidance, registry-as-`MutableMapping`).
>
> **Then propose** foley's design: **(a)** the top-level façade functions (e.g.
> `find(context)`, `search(query)`, `generate(prompt)`, `weave(narration, ...)`), the
> unified query/parameter vocabulary, and how sources (library APIs + generators) are
> **adapters** behind one interface. **(b)** The **source-adapter plugin pattern**
> (retrieve-sources and generate-sources sharing a config-driven contract, like arioso
> platforms). **(c)** The **index subsystem** boundary (ingest → tag/caption → embed →
> store) and the **retrieval-agent** boundary (context → query → rank → verify →
> place). **(d)** How the toolset is exposed as an **MCP server** via `py2mcp`. **(e)**
> The dependency & optional-extras layout (`foley[freesound]`, `foley[audiogen]`,
> `foley[clap]`, `foley[index-lance]`, …) and what belongs in the zero-dep core.
>
> **Deliver** a component diagram (described), the public façade API sketch, the adapter
> contract, and a "Recommendations for foley" section: a phased build order and the
> module layout. (This prompt synthesizes 1–9; run it after those land.) House conventions.

## Prompt 11 — Bootstrap corpora & benchmarks for a starter library

> **Role.** You are researching *what data to seed foley with* so it's useful on day one
> and measurable.
>
> **Investigate**: **(a) Free, redistributable SFX corpora** to ship or fetch as a
> starter library — Sonniss GameAudioGDC bundles, FSD50K, BBC Sound Effects (RemArc),
> Freesound curated packs, and any CC0 packs — with size, license, and how to obtain.
> **(b) Benchmark datasets** for evaluating retrieval — Clotho, AudioCaps, and any
> SFX-specific sets — including their (audio, caption) structure. **(c) Taxonimized sets**
> aligned to AudioSet/UCS. **(d) A "golden" evaluation set** design — a small set of
> (narrative-context → expected-sound) pairs foley can regression-test against, and how
> to build/label it cheaply. **(e) Practical ingestion** — expected corpus sizes,
> storage footprint, and embedding/index build time.
>
> **Deliver** a corpus table (name | size | license | contents | how-to-get), a
> benchmark table, and a "Recommendations for foley" section: a concrete **starter
> library** + a **golden eval set** plan. House conventions.

## Prompt 12 — Dimensions we haven't named yet (meta-scan)

> **Role.** You are the "what are we forgetting?" agent. Your job is to surface and
> research the aspects of building foley that the other prompts under-cover, so nothing
> load-bearing is missed.
>
> **Consider and research at least**: **real-time vs offline** operation and latency/cost
> budgets (interactive authoring vs batch rendering); **caching & cost control** across
> paid APIs and local inference; **multilingual / non-English** narration understanding
> for context→sound; **accessibility** (SFX as an aid, and captioning SFX for the
> hearing-impaired — the `[door creaks]` convention); **spatial / immersive audio**
> (stereo/binaural/ambisonics placement of a cue in a scene); **UX for auditioning**
> (preview, shortlists, human-in-the-loop selection, "more like this"); **versioning &
> reproducibility** of a narration's whole sound-design (an editable, re-renderable
> artifact — conceptually like the author's cosmograph "snapshots/stories"); **safety &
> disclosure** for AI-generated/near-copyright sounds and watermarking; **prompt
> engineering for SFX generation** (how prompt phrasing changes AudioGen/Stable-Audio
> output — the SFX analog of arioso's prompt-engineering guide); and **observability**
> (logging retrieval decisions so the agent's choices are debuggable).
>
> **Deliver** a ranked list of the additional dimensions with, for each, why it matters
> to foley, the key questions, and pointers to primary sources — plus a "Recommendations
> for foley" section flagging which of these deserve their own future deep-research
> prompt and which can be folded into existing modules. House conventions.

---

## Appendix — the shared context block (paste atop any prompt)

> You are researching for **foley** (github.com/thorwhalen/foley), a unified Python
> façade for sourcing, indexing, searching, and generating **sound effects** to weave
> into AI-generated narrations. It follows the author's `arioso` design: one entry
> function, config-driven plugin adapters, a unified parameter vocabulary translated to
> each backend's native params, zero required core deps with lazy per-backend
> optional-deps, `dol`-based storage, progressive disclosure. foley is **retrieval-first**
> (find the right sound for a narrative context); generation is one of several sources.
> Follow Vancouver citation conventions and end with "Recommendations for foley".
