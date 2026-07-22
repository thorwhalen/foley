# Context-to-Sound Retrieval and the Search-Agent Architecture

**Research note 05 for `foley`** — the central capability: given a narrative *context*
(a paragraph of story or commentary), find (or generate) the *right* sound(s) to
illustrate it, and expose the whole loop as an interactive AI agent.

> Scope note. This note covers (1) the SOTA of *language-based audio retrieval*, (2) the
> hard mapping from narrative prose to sound queries, (3) reranking/verification of
> candidates, (4) the generate-vs-retrieve decision, and (5) the agent / tool / MCP
> design. Generation backends themselves (AudioLDM, Stable Audio, ElevenLabs SFX, …) are
> owned by the sibling generation note; here they appear only as a *fallback branch* of the
> retrieval agent. Dates/versions are flagged; some challenge numbers are on hidden eval
> splits and should be read as representative, not exact.

---

## Abstract

The retrieval half of `foley` is a **language-based audio retrieval (LBAR)** problem: rank a
library of sound clips by how well each matches a natural-language description. The field has a
clean benchmark lineage — **DCASE Task 6b/8**, datasets **Clotho** and **AudioCaps**, dual-encoder
**CLAP** models, and the metrics **R@1/R@5/R@10** and **mAP@10** [1,3,4]. Best 2024 systems reach
**mAP@10 ≈ 0.40–0.44** and **R@1 ≈ 0.28–0.31** on Clotho (a hard, human-written-caption set), and
**R@1 ≈ 0.37–0.42** on the easier AudioCaps [1,6,7]. But `foley`'s real input is *not* a clean
caption — it is a story paragraph. The value-add is therefore a **context→query decomposition**
stage (an LLM lists the discrete, salient, diegetic sound events implied by the passage), a
**retrieve→verify→refine** loop (CLAP shortlist, then an LLM- or audio-LM-based judge that
"listens" to confirm intent), and a **generate-vs-retrieve** policy that falls back to the
generation façade when the library has no confident match. Recent agentic Foley systems
(FoleyDesigner [11], Foley Agent [12], FilMaster [13]) validate exactly this shape:
LLM decomposition + retrieval/RAG + verification + mixing. The recommended `foley` design is a
small set of pure functional tools — `decompose_context`, `search_sounds`, `verify_match`,
`generate_sound`, `preview`, `place_in_timeline` — wrapped as a façade (arioso/accompy style) and
published verbatim as an **MCP server** via `py2mcp`.

---

## 1. Language-Based Audio Retrieval: SOTA and metrics

### 1.1 The benchmark lineage

**Task.** LBAR = given a free-text query, rank audio clips so the intended clip lands at the top.
It has run in the **DCASE Challenge** since 2022 as *Task 6b*, and as a standalone task (renumbered
**Task 8**) in 2024 [1]. The development set is **Clotho v2** (Drossos et al. [28]): ~6k Freesound
clips, 15–30 s, each with 5 crowd-written captions — deliberately *generic*, no proper nouns, which
makes it hard. **AudioCaps** (Kim et al. [29]) is ~50k AudioSet clips with one caption each; it is
larger and easier, so retrieval numbers on it run higher. External training data (AudioSet,
WavCaps, Freesound) and pretrained models are permitted [1].

**Metrics.** All are computed over the ranked candidate list per query:

| Metric | Meaning | Notes |
|---|---|---|
| **R@1 / R@5 / R@10** | fraction of queries whose *correct* clip is in the top-1/5/10 | recall of the single relevant item |
| **mAP@10** | mean average precision at 10 | **official DCASE ranking metric** [1]; with one relevant clip, AP@10 = 1/rank (0 if rank > 10), so it rewards ranking the right clip *higher*, not just *present* |

DCASE 2025 reported **mAP@16** (top-16) as a variant [8]; treat it as the same family.

### 1.2 The workhorse architecture: CLAP dual encoders

Nearly every competitive system is a **CLAP-style dual encoder** [3,4]: an audio encoder and a text
encoder trained with a contrastive (InfoNCE) loss so that matching (audio, caption) pairs are close
in a shared embedding space. At query time you embed the text once, embed every library clip once
(offline), and rank by cosine similarity — i.e. retrieval is a **nearest-neighbor lookup in a vector
index**, cheap and scalable.

Key CLAP lineages and off-the-shelf checkpoints:

- **Microsoft CLAP** — Elizalde et al. 2022 (`MS-CLAP-22`, 128k pairs) and the stronger 2023 model
  (`MS-CLAP-23`, ~4.6M pairs, audio encoder trained on 22 tasks) [3].
- **LAION-CLAP** — Wu et al. 2023: HTSAT audio encoder + RoBERTa text encoder, trained on
  LAION-Audio-630k + AudioSet with **feature fusion** and **keyword-to-caption augmentation**; the
  `630k-audioset-best` / `laion/clap-htsat-unfused` checkpoints are the common baselines and ship in
  HF Transformers [4,5]. This is the pragmatic default for a first `foley` index.
- **DCASE-tuned encoders** — top challenge systems swap in stronger audio backbones
  (**PaSST**, **BEATs**, **ATST**) and text encoders (**RoBERTa-large**, **GTE-large**, BERT), with
  contrastive fine-tuning on Clotho+AudioCaps+WavCaps [1].
- **Beyond dual-encoder (2025–26)** — **GLAP** (multilingual/multi-domain) [6], **M2D-CLAP**
  (masked-modeling + CLAP) [7], and **Omni-Embed-Audio** (embeddings distilled from a multimodal
  LLM) [9] push numbers up and add robustness.

### 1.3 Current numbers (read as representative)

**DCASE 2024 Task 8, Clotho evaluation** — top teams, dual-encoder + ensembles [1]:

| System | Encoders | mAP@10 | R@1 | R@5 | R@10 |
|---|---|---|---|---|---|
| CP-JKU | PaSST/ATST/MobileNet + BERT/RoBERTa | ~0.42 | ~0.29 | ~0.59 | ~0.72 |
| SRPOL | PaSST-S + GTE-large/RoBERTa-large | ~0.44 | ~0.31 | ~0.60 | ~0.73 |
| SRCN (Samsung) | BEATs + BERT | ~0.41 | ~0.28 | ~0.58 | ~0.71 |
| Challenge baseline | contrastive dual-encoder | ~0.22 | — | — | — |

(Official ranking is on a hidden eval set; dev-test values differ by a point or two — hence the "~".
The takeaway magnitudes: **top ≈ 0.4 mAP@10 / ~0.3 R@1**, roughly **double** the baseline.)

**DCASE 2025 Task 6** — AISTAT lab: best single system **mAP@16 = 46.62**, 4-system ensemble
**48.83** on Clotho dev-test [8].

**AudioCaps text→audio** (easier set): **GLAP R@1 = 41.7** [6]; **M2D-CLAP** improves R@1 from 27.34
(stage 1) to **37.24** (stage 2) [7]. Cross-lingual and LLM-embedding models (Omni-Embed-Audio [9])
report further gains and better out-of-domain behavior.

**Practical reading for `foley`.** Even SOTA gets the exact intended clip at rank 1 only ~30% of the
time on generic captions — but R@10 ≈ 0.7 means *the right neighborhood is almost always in the
shortlist*. This is the core justification for the architecture: **retrieval produces a candidate
set; a verification/rerank stage and human preview pick the winner.** Do not treat top-1 as truth.

---

## 2. The hard mapping: narrative context → sound queries

CLAP retrieval expects a *caption-like* query ("a dog barking in the distance"). `foley`'s input is a
*passage* ("She pushed open the heavy oak door and stepped into the storm"). The gap between them is
where the product lives. Four sub-problems:

### 2.1 Scene / sound-event decomposition

Prompt an LLM to **enumerate the discrete, physically-audible events** implied by the passage, each
as a short retrieval query plus attributes. This is exactly the "FoleyScriptWriter" step in
FoleyDesigner [11] and the "resource collection" step in Foley Agent [12], and the
LLM-taxonomy idea in DiveSound [16]. Output a structured list, e.g.:

```
[
  {"event": "heavy wooden door creaking open", "layer": "foreground", "onset": "0.0s", "diegetic": true},
  {"event": "howling wind / storm ambience",   "layer": "background", "onset": "1.0s", "diegetic": true, "loop": true},
  {"event": "footstep on stone threshold",      "layer": "foreground", "onset": "2.0s", "diegetic": true}
]
```

The passage "She pushed open the heavy oak door" yields *creak* + *latch* + *footstep*; "into the
storm" yields a *wind/rain bed*. FoleyDesigner does this with a **generator→validator loop**
(FilmScribe) then a **Tree-of-Thought Expand/Score/Optimize/Prune** search that grounds candidate
scripts in Foley principles and separates **onscreen physical events** from **script-inferred
narrative** sounds [11].

### 2.2 Query formulation & expansion

Retrieval quality is sensitive to phrasing. Two proven levers:

- **Caption/keyword augmentation** — the LAION-CLAP "keyword-to-caption" trick [4] and DCASE-2024
  workshop work using an **LLM to paraphrase/expand queries** (Zgorzynski et al. [10]) both raise
  recall by giving the encoder several phrasings of the same intent. In practice: for each event,
  ask the LLM for 2–4 paraphrases ("oak door creaking", "old wooden door slowly opening", "hinge
  squeak") and **fuse their embeddings** (mean-pool) or run multi-query retrieval and merge.
- **FORTE**-style logical refinement [17] — recast the query in a structured/predicate form to
  "preserve semantic invariance while adding discriminative attributes," then rerank for logical
  consistency. Overkill for v1, but the paraphrase-fusion subset is cheap and effective.

### 2.3 Salience: *which* moments deserve a sound

Not every clause should trigger a clip — over-scoring is the #1 amateur-Foley failure. Ask the LLM
to **rank events by narrative salience** and cap density (e.g. ≤ N foreground sounds per M seconds).
Film-sound theory maps directly: *foreground/spot* effects punctuate significant beats (a slammed
door, a gunshot), while a single *ambience bed* covers the setting; silence is itself a choice [30].
FoleyDesigner's Score step explicitly evaluates "visual-audio correspondence, layer separation, and
emotional consistency" to decide what survives pruning [11]. In `foley` this is a **salience score +
budget**, returned by the decomposition tool so the agent can prioritize.

### 2.4 Diegetic vs non-diegetic

- **Diegetic** = exists in the story world and its characters could hear it (the door, the storm,
  the footsteps) — the primary target of retrieval [30].
- **Non-diegetic** = for the audience only (a tension drone, a musical sting under a reveal). These
  are more *generative/musical* than *retrieval* targets and route to the music/generation façade,
  not the SFX index.

Tag each decomposed event with `diegetic: bool`; use it to **route** (diegetic→SFX retrieval;
non-diegetic→generation/music) and to set expectations for verification (a diegetic dog-bark must
literally sound like a dog; a non-diegetic "unease" bed is judged on mood, not literal content).

---

## 3. Reranking / verification of candidates

Retrieval gives ~10 candidates; the agent must pick — or reject all and generate. Three
complementary verifiers, cheapest first:

1. **CLAP score (free).** You already have the text↔audio cosine from retrieval. Use it as the
   first-pass rank *and* as a **confidence gate**: if the top candidate's calibrated score is below
   a threshold, treat the library as "no good match" (→ §4). Note CLAP has a known **modality gap**
   and struggles with fine-grained/compositional intent [17], so do not trust the raw margin alone.

2. **Audio-LM "listen-and-confirm" (Qwen2-Audio-style).** A large audio-language model can *ingest
   the candidate clip* and answer a natural-language check — the exact "Does this audio contain
   {event}?" pattern used by **AQAScore** [20] and supported by **Qwen2-Audio**'s instruction
   following over 30+ audio-understanding tasks [19]. This catches cases where CLAP ranked a clip
   high on vibe but it is actually the wrong object (e.g. a *cat* returned for "dog barking"). Return
   a boolean + short rationale + a 0–1 confidence.

3. **LLM-as-judge / ensemble selection.** When several candidates pass, an LLM (given the passage,
   each candidate's caption/metadata, and the audio-LM verdicts) picks the best fit and explains why
   — the "audio judge" pattern (e.g. SAM Audio Judge, which lifts selection MOS well above raw CLAP
   [18]). This is also where **cross-event consistency** is enforced (do the door and the storm
   belong to the same acoustic scene?).

Design guidance: run (1) always, (2) on the top-k when the CLAP margin is ambiguous or the event is
object-specific, (3) only when you need to arbitrate. Verification is *retrieve→verify→refine*: if
all candidates fail, feed the failure reason back into query expansion (§2.2) and re-retrieve before
escalating to generation.

---

## 4. Generate-vs-retrieve decision policy

Retrieval is preferred when it works (real recordings, licensed, instant, free), but the library is
finite. Make the choice a **policy function**, not a hardcoded branch:

```
decide(event, candidates):
  if best_candidate.verified and best_candidate.confidence >= τ_retrieve:  return USE(best_candidate)
  if any candidate verified but low confidence:                           return REFINE_QUERY (loop, ≤ k times)
  if event.diegetic and no candidate verified:                            return GENERATE(event.query)
  if event.non_diegetic (mood/music):                                     return GENERATE / music façade
```

Signals that push toward **generate**: (a) low CLAP top score *and* audio-LM rejects the shortlist;
(b) highly specific/compositional intent unlikely to exist as a single clip ("a robot sneezing then
laughing"); (c) precise temporal/onset control needed. Generation is the **fallback adapter** —
`foley` should wrap text-to-audio backends behind one call exactly as **arioso** wraps 14 music
backends behind `generate()` (ElevenLabs SFX, Stable Audio Open (DiT) [22], AudioLDM/AudioLDM2 [21],
TangoFlux, MeanAudio). Emerging work (**Resonate** [23], **MultiFoley** [15], **CAFA** [14]) closes
the loop by using a large audio-LM as a *reward/verifier on generated* audio too — so the same
`verify_match` tool (§3) validates generated candidates before they are accepted. Cache accepted
generations back into the library so the retrieval index grows and the generate-rate drops over time.

---

## 5. The AI-agent architecture (tools + MCP)

### 5.1 The loop

```
context paragraph
   │  decompose_context           (LLM: events + salience + diegetic + timing)
   ▼
[ event, event, … ]
   │  for each salient event:
   │     ├─ refine_query          (LLM paraphrase/expand → fused query)
   │     ├─ search_sounds         (CLAP text→audio NN over the library index)
   │     ├─ verify_match          (CLAP gate → audio-LM listen-confirm → LLM judge)
   │     ├─ decide                (retrieve vs refine vs generate — §4)
   │     ├─ generate_sound        (fallback: text-to-audio façade)
   │     └─ preview               (return clip + human-in-the-loop listen/approve)
   ▼  place_in_timeline           (onset, gain, layer: foreground vs ambience bed)
soundscape plan  ──▶  render/mix
```

This mirrors published agentic Foley pipelines: FoleyDesigner's generator/validator +
Tree-of-Thought decomposition and analysis→planning→execution mixing [11]; Foley Agent's
resource-collection → synchronization → mixing with a Visual-LLM front end and SFX search [12];
FilMaster's RAG-over-a-library + cinematic-principle planning [13]. `foley` is the *text-first,
narration* instance of the same pattern, with a human preview in the loop.

### 5.2 The tool surface (functional façade)

Keep tools **small, pure, composable** — progressive disclosure, sensible defaults, keyword-only
knobs — so the same functions serve the Python API, the agent, and the MCP server:

| Tool | Signature (sketch) | Returns |
|---|---|---|
| `decompose_context` | `(passage: str, *, max_events=6, seconds=None) -> list[SoundEvent]` | events w/ `query`, `salience`, `diegetic`, `layer`, `onset`, `loop` |
| `refine_query` | `(query: str, *, n=3) -> list[str]` | paraphrase/expansion set (for embedding fusion) |
| `search_sounds` | `(query \| queries, *, k=10, filters=None) -> list[Candidate]` | ranked clips + CLAP scores + metadata |
| `verify_match` | `(event, candidate, *, level="clap"\|"listen"\|"judge") -> Verdict` | `{match: bool, confidence, reason}` |
| `generate_sound` | `(query: str, *, backend="auto", duration=None) -> Clip` | generated clip (fallback façade → arioso-style) |
| `preview` | `(clip) -> PreviewHandle` | audio bytes/URL for human listen + approve/reject |
| `place_in_timeline` | `(clip, *, onset, gain=0.0, layer="fg") -> TimelineItem` | positioned item in the soundscape plan |

Two design choices worth locking in early:

- **Library as a `dol` store.** Back `search_sounds` with a `Mapping` from clip-id → (audio, caption,
  CLAP-embedding, license). Embeddings live in a vector index (FAISS / hnswlib / LanceDB); the store
  abstraction lets the same code run on local files now and S3/DB later without touching agent logic.
- **Generation is one adapter, not a special case.** `generate_sound` and `search_sounds` return the
  same `Clip`/`Candidate` shape, so `verify_match` and `preview` are agnostic to origin — the
  generate-vs-retrieve policy (§4) is the *only* place that branches.

### 5.3 Exposing the toolset as MCP (`py2mcp`)

Because the tools are plain functions, publishing them to any agent host (Claude Desktop, claude.ai
connector, an in-app assistant) is one line each with Thor's **`py2mcp`**: `mk_mcp_server([...])` for
a stdio bundle, or `mk_http_app([...], auth=…)` for a hosted OAuth-guarded connector [25 → py2mcp].
The **library store** can even be surfaced directly with `mk_mcp_from_store(library)` to auto-expose
`list/get/set/delete` CRUD. Input transforms (`mk_input_trans`) coerce agent-supplied JSON into numpy
/ audio objects. This is the same façade-to-MCP path arioso and accompy follow: a single
verb (`generate` / `generate_accompaniment`) plus `check_dependencies`/`verify_and_setup` for
system-dependency guidance, then wrapped for MCP without rewriting anything.

### 5.4 Relation to arioso / accompy

- **arioso** — `generate(prompt, platform=…)` over 14 backends: the *template for `foley`'s
  generation adapter*. `foley.generate_sound` should be a thin SFX-flavored sibling (reuse arioso for
  the ElevenLabs / Stable Audio / MusicGen backends; add SFX-specific ones).
- **accompy** — one façade verb + robust `check_dependencies()` / `verify_and_setup()`: the
  *template for onboarding UX* (FluidSynth-style external deps become CLAP-model / index deps).
- **py2mcp** — the *template for tool exposure*: façade functions → MCP tools, plus store→CRUD.

`foley` = **arioso's façade discipline** + **accompy's dependency-onboarding** + a **retrieval index**
+ a **decompose→verify→refine agent loop**, all published through **py2mcp**.

---

## Recommendations for `foley`

### End-to-end retrieval-agent pipeline (concrete, v1 → v2)

1. **Index the library (offline).** Precompute **LAION-CLAP** (`laion/clap-htsat-unfused` [4,5])
   audio embeddings for every clip; store `(audio, caption, embedding, license)` in a `dol` store +
   a vector index (start FAISS/hnswlib). Cheap, local, swappable for MS-CLAP-23 [3] or a
   DCASE-tuned encoder [1] later.
2. **`decompose_context`.** LLM turns the passage into ≤6 ranked `SoundEvent`s with
   `query / salience / diegetic / layer / onset / loop`. Enforce a **salience budget** (≤ N
   foreground sounds per window) so scenes don't overcrowd [11,30].
3. **`refine_query` → `search_sounds`.** For each event: 2–4 LLM paraphrases [10], **mean-pool their
   CLAP text embeddings**, retrieve top-k=10 (filter by license/duration).
4. **`verify_match` ladder.** (a) CLAP-score gate; (b) if object-specific or ambiguous, a
   **Qwen2-Audio "does this contain {event}?"** listen-check [19,20]; (c) LLM-judge to arbitrate
   ties and cross-event scene consistency [18]. Loop back to step 3 on failure (≤ k times).
5. **`decide` (generate-vs-retrieve, §4).** Confident verified clip → use it. Diegetic-but-no-match
   → **`generate_sound`** via the arioso-style façade, then run it back through `verify_match`.
   Non-diegetic/mood → music/generation route. Cache accepted generations into the library.
6. **`preview` (human-in-the-loop).** Always return the shortlist/clip for a human to hear and
   approve before committing — retrieval top-1 is right ~30% of the time [1], so keep a person (or a
   confirmed high-confidence auto-accept threshold) in the loop.
7. **`place_in_timeline` → plan.** Emit a soundscape plan (onset, gain, foreground vs ambience bed);
   hand off to render/mix (out of scope here).
8. **Publish via `py2mcp`.** `mk_mcp_server` (stdio) for local agents, `mk_http_app` for a hosted
   connector; optionally `mk_mcp_from_store` for the library. Same functions, three surfaces.

### Tool schema (lock this shape)

`decompose_context` · `refine_query` · `search_sounds` · `verify_match` · `generate_sound` ·
`preview` · `place_in_timeline` — pure functions, keyword-only knobs, a shared `Clip`/`Candidate`
return type so retrieval and generation are interchangeable and the agent branches in exactly one
place (`decide`). Defaults must make `search_sounds("a dog barking")` work out of the box; every
model/index/threshold is an optional keyword override (open-closed).

### Highest-leverage bets

- **Decomposition + salience is the moat**, not the CLAP encoder. The encoder is a swappable
  commodity [3,4,6,7,9]; turning prose into a *tastefully sparse, correctly-diegetic* event list is
  the hard, defensible part [11,30].
- **Verification unlocks trust.** The audio-LM listen-check [19,20] is what lets `foley` auto-accept
  without a human on every clip — invest here before chasing +2 mAP on the encoder.
- **Grow the library from generations.** Every verified generation cached back into the index makes
  the next similar request a retrieval, steadily cutting cost and latency.

---

## REFERENCES

1. DCASE 2024 Challenge — Task 8: Language-Based Audio Retrieval (task + results). [dcase.community](https://dcase.community/challenge2024/task-language-based-audio-retrieval-results)
2. DCASE 2023 Challenge — Task 6b: Language-Based Audio Retrieval (results). [dcase.community](https://dcase.community/challenge2023/task-language-based-audio-retrieval-results)
3. Elizalde et al., *CLAP: Learning Audio Concepts from Natural Language Supervision* (Microsoft CLAP, 2022; ICASSP 2023). [arxiv.org/abs/2206.04769](https://arxiv.org/abs/2206.04769)
4. Wu et al., *Large-scale Contrastive Language-Audio Pretraining with Feature Fusion and Keyword-to-Caption Augmentation* (LAION-CLAP, 2023). [arxiv.org/abs/2211.06687](https://arxiv.org/abs/2211.06687)
5. Hugging Face Transformers — CLAP model docs (`laion/clap-htsat-unfused`). [huggingface.co](https://huggingface.co/docs/transformers/model_doc/clap)
6. *GLAP: General Contrastive Audio-Text Pretraining Across Domains and Languages* (2025). [arxiv.org/abs/2506.11350](https://arxiv.org/abs/2506.11350)
7. Niizumi et al., *M2D-CLAP: Exploring General-purpose Audio-Language Representations Beyond CLAP* (2025). [arxiv.org/abs/2503.22104](https://arxiv.org/abs/2503.22104)
8. *AISTAT Lab System for DCASE 2025 Task 6: Language-Based Audio Retrieval* (2025). [arxiv.org/abs/2509.16649](https://arxiv.org/abs/2509.16649)
9. *Omni-Embed-Audio: Leveraging Multimodal LLMs for Robust Audio-Text Retrieval* (2026). [arxiv.org/abs/2604.18360](https://arxiv.org/abs/2604.18360)
10. Zgorzynski et al., *Improving Language-Based Audio Retrieval using LLM* (DCASE 2024 Workshop). [dcase.community](https://dcase.community/documents/workshop2024/proceedings/DCASE2024Workshop_Zgorzynski_48.pdf)
11. Li et al., *FoleyDesigner: Immersive Stereo Foley Generation with Precise Spatio-Temporal Alignment for Film Clips* (2026). [arxiv.org/abs/2604.05731](https://arxiv.org/abs/2604.05731)
12. *Foley Agent: Automatic Sound Design and Mixing Agent for Silent Videos Driven by LLMs* (Springer, 2025). [link.springer.com](https://link.springer.com/chapter/10.1007/978-981-96-2681-6_13)
13. Huang et al., *FilMaster: Bridging Cinematic Principles and Generative AI for Automated Film Generation* (2025). [arxiv.org/abs/2506.18899](https://arxiv.org/abs/2506.18899)
14. *CAFA: a Controllable Automatic Foley Artist* (2025). [arxiv.org/abs/2504.06778](https://arxiv.org/abs/2504.06778)
15. *MultiFoley: Video-Guided Foley Sound Generation with Multimodal Controls* (2024). [ificl.github.io/MultiFoley](https://ificl.github.io/MultiFoley/)
16. *DiveSound: LLM-Assisted Automatic Taxonomy Construction for Diverse Audio Generation* (2024). [promptlayer.com](https://www.promptlayer.com/research-papers/divesound-llm-assisted-automatic-taxonomy-construction-for-diverse-audio-generation)
17. Pal & Rajanala, *FORTE: FOL-guided Optimal Refinement for Text-audio rEtrieval* (2026). [arxiv.org/abs/2606.05812](https://arxiv.org/abs/2606.05812)
18. *SAM Audio Judge (SAJ)* — LLM-as-judge for audio candidate selection. [emergentmind.com](https://www.emergentmind.com/topics/sam-audio-judge-saj)
19. Chu et al., *Qwen-Audio / Qwen2-Audio: Advancing Universal Audio Understanding* (2023–24); repo [github.com/QwenLM/Qwen2-Audio](https://github.com/QwenLM/Qwen2-Audio). Paper: [arxiv.org/abs/2311.07919](https://arxiv.org/abs/2311.07919)
20. *AQAScore: Evaluating Semantic Alignment in Text-to-Audio Generation via Audio Question Answering* (2026). [arxiv.org/abs/2601.14728](https://arxiv.org/abs/2601.14728)
21. Liu et al., *AudioLDM: Text-to-Audio Generation with Latent Diffusion Models* (2023). [arxiv.org/abs/2301.12503](https://arxiv.org/abs/2301.12503)
22. Evans et al., *Stable Audio Open* (Diffusion Transformer text-to-audio, 2024). [arxiv.org/abs/2407.14358](https://arxiv.org/abs/2407.14358)
23. *Resonate: Reinforcing Text-to-Audio Generation via Online Feedback from Large Audio Language Models* (2026). [arxiv.org/abs/2603.11661](https://arxiv.org/abs/2603.11661)
24. *MMAU: A Massive Multi-Task Audio Understanding and Reasoning Benchmark* (2024). [arxiv.org/abs/2410.19168](https://arxiv.org/abs/2410.19168)
25. Model Context Protocol — specification. [modelcontextprotocol.io](https://modelcontextprotocol.io) · Thor's generator: [github.com/thorwhalen/py2mcp](https://github.com/thorwhalen/py2mcp)
26. StudioBinder, *Non-Diegetic Sound — Storytelling with the Soundtrack* (film-sound reference). [studiobinder.com](https://www.studiobinder.com/blog/what-is-non-diegetic-sound/)
27. *Challenge on Sound Scene Synthesis: Evaluating Text-to-Audio Generation* (DCASE 2024). [arxiv.org/abs/2410.17589](https://arxiv.org/abs/2410.17589)
28. Drossos et al., *Clotho: An Audio Captioning Dataset* (ICASSP 2020). [arxiv.org/abs/1910.09387](https://arxiv.org/abs/1910.09387)
29. Kim et al., *AudioCaps: Generating Captions for Audios in the Wild* (NAACL 2019). [aclanthology.org/N19-1011](https://aclanthology.org/N19-1011/)
30. Fiveable, *Diegetic and Non-Diegetic Sound in Narrative Construction* (film-theory reference). [fiveable.me](https://fiveable.me/introduction-to-film-theory/unit-8/diegetic-non-diegetic-sound-narrative-construction/study-guide/lb67y2Tc182IUkkB)
31. Thor Whalen, *arioso* — unified façade for AI music generation (14 backends). [github.com/thorwhalen/arioso](https://github.com/thorwhalen/arioso)
32. Thor Whalen, *accompy* — scriptable backing-track façade with `verify_and_setup`/`check_dependencies`. [github.com/thorwhalen/accompy](https://github.com/thorwhalen/accompy)
