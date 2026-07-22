# Evaluation & Quality — "Did we retrieve the right sound?" and "Is the sound clean?"

**Research note 08 for `foley`** — how foley *knows it is doing a good job*, along two
orthogonal axes: **relevance** (did we surface the right sound for the narrative moment?)
and **technical quality** (is the clip itself clean, well-formed, and correctly loud?).

> Scope note. This note owns evaluation for the SOURCE→INDEX→SELECT stages: retrieval
> metrics, fit/relevance judging, per-clip audio QC, and generation QC, plus a cheap
> regression harness that keeps model/index/prompt upgrades from silently degrading
> results. It builds directly on note 05's verification ladder (CLAP-score → audio-LM
> listen-check → LLM-judge) — that ladder is a *runtime* decision aid; this note turns the
> same primitives into an *offline* measurement discipline. Mixing/mastering evaluation for
> the WEAVE stage (note 06) is only touched where loudness QC overlaps. Numbers are flagged
> with versions/dates; many generative-audio metrics are young and moving fast.

---

## Abstract

foley's quality problem splits cleanly. **Relevance** is a language-based audio retrieval
(LBAR) evaluation task with a mature benchmark lineage — DCASE, Clotho, AudioCaps — and
standard ranking metrics **Recall@k, mAP@10, nDCG@k, MRR** computed against **graded
relevance judgments** (`qrels`) [1–5]. **Technical quality** decomposes into deterministic
**per-clip audio QC** (clipping, DC offset, silence, SNR, edge clicks, loudness/LUFS,
duration) with concrete numeric thresholds [12–17], and **generation QC** for detecting
failed/garbled synthesis. The best per-sample generative-quality signals today are
learned, no-reference predictors — **CLAP-score**, **PAM** (CLAP-prompted) [22], and
**Meta Audiobox-Aesthetics** (Production-Quality axis) [21] — while distribution-level
fidelity is measured by **Fréchet Audio Distance (FAD)** [18] and its unbiased successor
**Kernel Audio Distance (KAD)** [20], with the embedding choice (PANNs Wavegram-Logmel for
environmental sound/SFX) mattering more than the distance formula [19,7]. **Fit** — does a
clip match a *described intent* — is judged by an **audio-language model** (Qwen2-Audio /
AQAScore "does this contain {event}?") [9,10] or an **LLM-as-judge**, calibrated against
human raters via **Krippendorff's α / Fleiss' κ** [11] and validated with **2AFC / Bradley-
Terry preference tests** [24]. The recommendation is a **three-tier, economist/testing-
trophy harness**: Tier-0 deterministic audio-QC on every commit (milliseconds), Tier-1
retrieval metrics against a small frozen gold set on every index/model/prompt change
(seconds, via `ranx`/`pytrec_eval` [5,6]), and Tier-2 audio-LM/LLM fit-judging on a
stratified sample nightly/pre-release, with a human-calibrated subset. A gold-set
construction recipe (TREC-style pooling + graded 0–3 relevance, versioned to a frozen
library snapshot) closes the loop.

---

## 1. Retrieval evaluation — "did we retrieve the right sound?"

### 1.1 The metrics catalog (ranking metrics)

All are computed over the **ranked candidate list per query**, then averaged over queries.
`rel(d)` is the relevance grade of the document at a rank; `k` is the cutoff.

| Metric | Definition (per query, then meaned) | What it rewards | When to use in foley |
|---|---|---|---|
| **Recall@k** (R@k) | (# relevant clips in top-k) / (total relevant clips) | *Coverage* — is the right neighborhood in the shortlist? | Headline for the shortlist step; R@10 is the "does the verifier get a fair chance" gate |
| **Precision@k** | (# relevant in top-k) / k | Purity of the top-k | Secondary; noisy with few relevants |
| **MRR** (Mean Reciprocal Rank) | mean of 1/rank of the *first* relevant clip [4] | Getting *something* right fast | Known-item queries (context → the one ideal clip) |
| **AP / mAP@k** | mean over queries of Average Precision (mean of Precision@rank at each relevant hit), truncated at k | Ranking *every* relevant clip early | **Primary offline metric** — it is the official DCASE Task 8 ranking metric [1] |
| **nDCG@k** | DCG@k / IDCG@k, DCG = Σ (2^rel−1)/log₂(rank+1) [2,3] | *Graded* relevance — an "ideal" clip above a "merely related" one | Best when relevance is graded 0–3 (see §1.3) |

Notes that matter for a sound library:

- With **one** relevant clip per query (the "known-item" case), AP@10 collapses to
  `1/rank` (0 if rank > 10) — so mAP@10 and MRR@10 coincide, and both just reward ranking
  the intended clip higher. Report R@1/R@5/R@10 alongside to see the shortlist behaviour [1].
- With **graded, multi-relevant** judgments (many door-creaks are "relevant", a few are
  "ideal"), **nDCG@10 is the metric of record** — it is the only one above that distinguishes
  a perfect match from a merely acceptable one [2,3].
- **Reference numbers (read as representative, not exact).** SOTA text→audio retrieval on the
  hard, human-captioned **Clotho** set reaches **mAP@10 ≈ 0.40–0.44, R@1 ≈ 0.28–0.31,
  R@10 ≈ 0.72**; on the easier **AudioCaps**, R@1 ≈ 0.37–0.42 [1,7]. **Top-1 is right only
  ~30 % of the time; R@10 ≈ 0.7.** This is the empirical justification for foley's
  retrieve-a-shortlist-then-verify architecture (note 05): *never* score the pipeline on
  top-1 alone.

### 1.2 The tooling — don't hand-roll IR metrics

Two mature Python libraries consume a standard `(qrels, run)` pair and emit all of the above;
use one, do not re-implement (a documented failure mode the IR community calls out) [6].

- **`ranx`** (Bassani, ECIR 2022) — Numba-accelerated; `ranx.evaluate(qrels, run, ["map@10",
  "ndcg@10", "recall@10", "mrr"])`; also does statistical significance testing and model
  comparison across runs [5]. **Recommended default** for foley.
- **`pytrec_eval`** (Van Gysel & de Rijke, 2018) — a thin Python binding to NIST's canonical
  `trec_eval`; use it when you want bit-exact agreement with published TREC/DCASE numbers [6].

`qrels` = a mapping `query_id → {clip_id → relevance_grade}`; `run` = `query_id → {clip_id →
score}`. Both formats are the TREC standard, so foley's gold set (below) should be stored in
exactly that shape.

### 1.3 Building the gold set of (context → ideal sound) pairs

A gold set is *the* asset here — the encoder is a swappable commodity (note 05), but a small,
well-judged evaluation corpus is what makes every future upgrade measurable. Recipe:

1. **Collect ~50–200 narrative contexts**, stratified so the metric can't be gamed by one
   easy category. Stratify by (a) **sound family** — impacts, ambiences/beds, motion/foley,
   vocalizations, machines/UI, weather; (b) **difficulty** — literal ("a dog barks") vs
   compositional ("a robot sneezes then laughs"); (c) **diegetic vs non-diegetic** (the latter
   route to generation/music and are judged on *mood*, not literal content). Mine real usage
   logs where possible; hand-author to fill gaps.
2. **Two levels of gold, because foley has two stages** (decompose, then search):
   - **Query-level qrels** — for each *decomposed sound-event query*, a set of library clips
     with **graded relevance 0–3**: `3 = ideal` (exactly this object/action/perspective),
     `2 = relevant` (right object, wrong nuance — a small dog for "big dog"), `1 = related`
     (same family — any door for "oak door"), `0 = irrelevant`. This drives nDCG/mAP.
   - **Context-level gold** — for each *paragraph*, the ideal decomposition (the set/ordering
     of salient events with diegetic flags) and, optionally, a reference soundscape plan. This
     evaluates `decompose_context`, which note 05 calls the moat, *separately* from retrieval.
3. **Judge by pooling (TREC method) [4].** Run several retrieval configs (e.g. pure-CLAP,
   BM25, hybrid-RRF, a paraphrase-fused variant), **pool the union of their top-k** (k≈10–20),
   and have humans grade only the pool — this bounds annotation cost while keeping the qrels
   reusable across future systems. New systems that surface an unjudged clip get it treated as
   `0` (a known pooling bias; mitigate by re-pooling when the index changes materially).
4. **Multiple raters + reliability.** Have ≥2–3 people grade an overlapping subset; compute
   **Krippendorff's α** (handles missing/uneven ratings and ordinal grades) [11]; adjudicate
   disagreements. Treat α ≥ 0.8 as reliable, 0.667–0.8 as tentative/usable, < 0.667 as "rubric
   is ambiguous, revise it" (Krippendorff's own cut-offs) [11]. Where humans are scarce, an
   **LLM/audio-LM judge calibrated against the human subset** (§2) can extend judgments —
   but only after you've measured its agreement with humans on that subset.
5. **Freeze and version it.** Pin the qrels to a **specific library snapshot** (record the
   `SoundRecord` ids and the `embedding_model`/`dim` stamps, which the schema already carries)
   so a metric change is attributable to the *system*, not to a shifted corpus. Keep a small
   **held-out** slice you never tune against, to catch overfitting to the gold set.
6. **Seed corpus.** Bootstrap the library-side of the gold set from a permissive, captioned
   set — **FSD50K** (CC0/CC-BY, Freesound-derived, AudioSet-ontology labels) [26] and
   **Clotho** [8] — so there are real, licensed clips to be "relevant" and pre-existing captions
   to anchor grades.

### 1.4 CLAP score as a cheap proxy relevance signal — and its limits

The text↔audio cosine you already compute for retrieval is a *free* relevance proxy: rank by
it, and gate on it (below a calibrated threshold ⇒ "library has no good match" ⇒ generate).
But treat it as a **noisy proxy, never ground truth**:

- **Modality gap & coarseness.** CLAP aligns *global* semantics; it captures "dog-ish" but is
  weak on fine-grained/compositional intent, event ordering, and attribute binding — a *cat*
  can outrank the intended *dog* on "vibe" [10,17].
- **Relevance ≠ quality.** A degraded, clipped clip can score high on CLAP; CLAP-score says
  nothing about technical cleanliness [22]. Keep §3 audio-QC strictly separate.
- **Low human correlation as an absolute score.** CLAPScore correlates only weakly with human
  judgments at the per-item level [10]; it is far more trustworthy as a *relative ranking
  signal within one query* than as a cross-query absolute number — so **calibrate thresholds
  per-encoder** (a raw margin from `laion/larger_clap_general` is not comparable to one from
  MS-CLAP-23) and re-calibrate whenever the encoder changes.

---

## 2. Fit evaluation — "does this clip match the described intent?"

Retrieval metrics need pre-built qrels. **Fit judging** answers a fresh question per candidate
— *does this specific clip contain/depict {event}?* — and is what powers both the runtime
verifier (note 05 §3) and the offline Tier-2 harness (§5).

### 2.1 Audio-LM "listen-and-confirm" (the object check)

A large **audio-language model** ingests the *actual clip* and answers a natural-language
check. This is the **AQAScore** pattern — pose "Does this audio contain {event}?" as audio
question-answering and read the model's yes/no probability as a semantic-alignment score [10]
— supported by **Qwen2-Audio**'s instruction-following over audio-understanding tasks [9].
It catches the exact CLAP failure mode (right vibe, wrong object). Return `{match: bool,
confidence: 0–1, reason: str}`. Cost/latency are real, so run it only on the top-k when the
CLAP margin is ambiguous or the event is object-specific.

### 2.2 LLM-as-judge (the arbiter)

When several candidates pass the object check, an **LLM-as-judge** — given the passage, each
candidate's caption/tags/metadata, and the audio-LM verdicts — picks the best fit, explains
why, and enforces **cross-event scene consistency** (do the door and the storm belong to the
same acoustic space?). Design cautions from the LLM-judge literature [11, and note 05's SAM-
Audio-Judge]: judges are **self-inconsistent** across runs (fix a temperature, average a few
samples, or use pairwise not absolute scoring), carry **position/verbosity bias** (randomize
candidate order; ask for a rubric-anchored score), and must be **validated against humans**
before you trust them unattended.

### 2.3 Inter-rater reliability (trusting any judge — human or model)

Whatever judges — humans or an LLM/audio-LM — quantify agreement before believing the scores:

- **Cohen's κ** — two raters, categorical. **Fleiss' κ** — ≥3 raters, categorical, fixed set.
  **Krippendorff's α** — any number of raters, **ordinal/graded** labels (foley's 0–3 grades),
  tolerant of missing ratings; the most general and the recommended default [11].
- **Benchmarks:** α/κ ≥ 0.8 reliable; 0.667–0.8 tentative; below ⇒ fix the rubric [11]. On
  skewed label distributions (most candidates irrelevant), also report **raw % agreement** and
  a chance-corrected number, since κ/α can look pessimistic under class imbalance [11].
- **Model-vs-human:** report **Krippendorff's α (or Spearman/Pearson for continuous scores)**
  between the LLM/audio-LM judge and the human subset; only promote the model judge to
  unattended use once it reaches human-level agreement on the calibration slice.

### 2.4 A/B and preference testing (comparing systems, not scoring one)

For "is version B better than version A?", **pairwise preference** is more sensitive and less
fatiguing than absolute rating [24]:

- **2AFC / paired comparison** — a rater hears A and B for the same context and picks the
  better fit. Aggregate many pairwise outcomes with the **Bradley–Terry(–Luce) model** into a
  single strength score per system; get confidence intervals by **bootstrap resampling**, and
  call B "better" only when its CI clears A's [24].
- **Absolute subjective quality** (for the WEAVE deliverable, note 06) uses **MOS** (1–5) or,
  better, **MUSHRA / ITU-R BS.1534-3** — multiple stimuli with a **hidden reference and hidden
  anchor**, scored 0–100; the hidden reference/anchor make it more reliable than MOS and let you
  detect inattentive raters [23]. Overkill for v1 relevance work; reserve for mastering/quality
  studies.
- **Sample sizes** in recent audio studies range from ~15–20 expert listeners (MUSHRA panels)
  to thousands of crowd preference pairs for A/B [24]. For foley, a **~20–50 pair** panel per
  release candidate on the gold-set contexts is a pragmatic middle ground.

---

## 3. Audio QC — "is the sound technically clean?" (deterministic, per-clip)

These are **cheap, deterministic, dependency-light checks** (NumPy + `soundfile`/`pyloudnorm`)
that run on ingest *and* in the Tier-0 harness. Thresholds are **sensible defaults, every one
a config override** (open-closed / progressive-disclosure — matches the façade discipline).
`x` is the normalized waveform in [−1, 1]; dBFS = 20·log₁₀(|x|).

| Check | How to measure | Default threshold / action | Why |
|---|---|---|---|
| **Hard clipping** | count samples with `|x| ≥ 0.999`; look for **runs ≥ 3 consecutive** full-scale samples | flag if clipped-sample ratio > 0.01 %, or any run ≥ 10 samples ⇒ **reject/flag** | flat-topped waveform = irreversible distortion (0 dBFS is the digital ceiling) [14] |
| **True-peak / inter-sample** | 4× oversample, take peak (dBTP); `pyloudnorm`/limiter | require **≤ −1 dBTP** for deliverables (−2 dBTP if targeting Alexa/Echo) | avoids inter-sample clipping on downstream D/A & codecs [12,13] |
| **DC offset** | per-channel `mean(x)` | `|mean| > 0.01` (≈ −40 dBFS) ⇒ **correct** (high-pass/subtract); 0.001–0.01 note; < 0.001 ignore | offset wastes headroom, causes edge clicks, biases loudness [15] |
| **Whole-clip silence / empty** | integrated RMS over the file | RMS < **−60 dBFS** ⇒ **reject as empty/near-silent** | catches dead files & failed generations (§4) |
| **Leading/trailing silence** | onset/offset of energy above a gate | trim at a **−40 to −60 dB-below-peak** gate (e.g. `librosa.effects.trim(top_db=40)`) | tightens clips so onsets land on the beat in WEAVE |
| **Low SNR / noise** | estimate noise floor from the **quietest ~10 % of short-time RMS frames**, or **WADA-SNR** [16] | **> 20 dB** clean · 10–20 marginal · **< ~8–10 dB advisory reject** | flags hiss/hum. **Advisory, not hard** — a "busy street" SFX legitimately has low SNR |
| **Abrupt start/end (clicks/pops)** | boundary sample level vs peak; large sample-to-sample delta at edges | first/last sample > **−40 dBFS rel. peak**, or boundary Δ above threshold ⇒ **require ≥ 5–10 ms fade** | a nonzero edge = an audible click when placed under narration |
| **Loudness outlier** | **integrated LUFS** via `pyloudnorm` (ITU-R BS.1770-4) [12,17] | flag clips **> ±6 LU** from the **library median**; normalize deliverables to target (§3.1) | keeps a library from having wildly uneven perceived level |
| **Duration sanity** | frames / sample-rate | min ≈ **0.1 s**; max per use; generation: within **±20 %** of requested | catches truncated/runaway clips |
| **Format sanity** | header + array scan | expected sample-rate (≥ 44.1 kHz deliver), channel count, **no NaN/Inf** | corrupt-file guard; NaN/Inf ⇒ hard reject |

The canonical `SoundRecord` already carries `duration`, `sample_rate`, `channels`, and
`loudness_lufs` — so most of this table is *populating and range-checking fields the schema
already defines*, and the results become filterable metadata (e.g. `search(..., min_snr=20)`).

### 3.1 Loudness: measure with BS.1770, normalize to a target

- **Measure** integrated loudness with **`pyloudnorm`** (`meter =
  pyln.Meter(rate); L = meter.integrated_loudness(x)`), an ITU-R BS.1770-4 implementation
  depending only on NumPy/SciPy [17]. Store `L` in `SoundRecord.loudness_lufs`.
- **Normalize** deliverables with `pyln.normalize.loudness(x, L, target)` then peak-limit to
  **≤ −1 dBTP**. Default targets: **−14 LUFS** (Spotify/YouTube/Tidal/Amazon/SoundCloud),
  **−16 LUFS** (Apple Music), **−23 LUFS** (EBU R128 broadcast) [12,13]. Make it a config knob.
- **Caveat for short one-shots (< ~3 s):** BS.1770 gating can return `−inf`/unstable values for
  very short transients — fall back to **short-term/momentary loudness or peak normalization**
  for one-shot SFX, and reserve integrated-LUFS normalization for beds/ambiences and the final
  WEAVE mix [12,17].

---

## 4. Generation QC — catching failed/garbled synthesis

Generation is a fallback adapter (note 05 §4); its outputs must pass the same §3 audio-QC
*plus* generation-specific relevance/plausibility checks before being cached back into the
library.

### 4.1 Fast per-sample failure detectors (cheap, run always)

1. **Empty/silent output** — RMS < −60 dBFS ⇒ generation failed (§3).
2. **NaN/Inf / DC blowup** — hard reject.
3. **Semantic-alignment gate (CLAP-score)** — cosine(prompt, generated) below a per-encoder
   threshold ⇒ the model ignored the prompt; regenerate or fall back to retrieval [10,22].
4. **Perceptual-quality gate (no-reference, learned):**
   - **PAM** (Deshmukh et al., Interspeech 2024) — a no-reference metric that prompts a CLAP
     ALM with an **antonym prompt pair** ("high quality" vs "low quality") and reads the
     similarity as a 0–1 quality score; needs **no reference set and no trained head**, and
     correlates well with human MOS across TTA/TTM/TTS/DNS [22]. Cheap (one CLAP forward) —
     ideal as a per-sample generation gate. (`pip install`-able, `soham97/pam`.)
   - **Meta Audiobox-Aesthetics** (Tjandra et al., 2025) — a no-reference predictor giving four
     axes **PQ / PC / CE / CU** (Production Quality, Production Complexity, Content Enjoyment,
     Content Usefulness), ~1–10 scale; `pip install audiobox_aesthetics`, `audio-aes in.jsonl`
     or `initialize_predictor().forward([{"path": ...}])` [21]. Gate generations on the **PQ**
     axis; it's the closest thing to a general **SFX-quality** score and doubles as a
     **library-wide QC filter / pseudo-labeler**. (Institutionalized as AudioMOS-Challenge-2025
     Track 2 [21].)
5. **Audio-LM plausibility** — the §2.1 "does this contain {event}?" check, reused as
   "is this a plausible recording of {event}?", catches garbled-but-loud outputs that fool
   CLAP [9,10].

### 4.2 Distribution-level fidelity: FAD and KAD (set-level, for model comparison)

For "is generator A's *output distribution* closer to real SFX than generator B's?" — a
**set-level** question used to compare backends or track a model over time, **not** a per-clip
gate:

- **Fréchet Audio Distance (FAD)** (Kilgour et al., Interspeech 2019) — fit a multivariate
  Gaussian to embeddings of a *reference set* and a *generated set*, take the Fréchet distance;
  lower = closer to real [18]. Originally VGGish embeddings.
- **Embedding choice dominates the formula.** Gui et al. (2023/24, `microsoft/fadtk`) show
  **domain-matched embeddings (PANNs, CLAP) correlate with human quality far better than
  VGGish**, and add **sample-size-bias extrapolation** and **per-song FAD** for outlier
  detection [19]. **For foley's SFX/environmental domain, use PANNs Wavegram-Logmel
  embeddings** — DCASE-2024 Sound-Scene-Synthesis's "**FAD-P**" used exactly this and found it
  **strongly correlated with human sound-source-fit ratings** [4].
- **KAD (Kernel Audio Distance)** (2025, ICML; `YoonjinXD/kadtk`) — an **MMD-based, distribution-
  free, unbiased** replacement that **converges with far smaller samples** and aligns better
  with human judgment; prefer it when the reference/generated sets are small (early-stage
  eval) [20].
- **Practical:** FAD/KAD need **hundreds+ samples**; keep them for **release-level backend
  comparison** in Tier-2, not per-request. Report the embedding + toolkit + version, since
  scores are not comparable across embeddings.

### 4.3 SFX-specific gaps

There is **no single SFX-native fit metric** as mature as image FID — hence the layered proxy
stack above. The DCASE Sound-Scene-Synthesis challenge is the closest domain benchmark and
notably found a **~36 % quality gap** between the best generative systems and a human sound
designer's reference [4] — a useful sanity anchor: automatic metrics should never certify
generated SFX as "as good as a pro" without a human/MUSHRA confirmation.

---

## 5. Regression harness — keep upgrades from silently degrading results

Mirror the **economist / testing-trophy** philosophy: cheapest, most-stable checks first, run
most often; expensive human/model judging sparingly. Three tiers, each a gate on a different
class of change.

```
                         cost / brittleness ↑        frequency ↓
 ┌───────────────────────────────────────────────────────────────────────┐
 │ Tier 2  FIT-JUDGING     audio-LM listen-check + LLM-judge on a sampled  │  nightly /
 │         (relevance,     slice; FAD/KAD backend comparison; small        │  pre-release
 │          generation)    MUSHRA/2AFC human panel on release candidates   │
 ├───────────────────────────────────────────────────────────────────────┤
 │ Tier 1  RETRIEVAL       ranx/pytrec_eval over the FROZEN gold set:      │  every PR that
 │         METRICS         R@1/5/10, mAP@10, nDCG@10, MRR; gate on Δ       │  touches index/
 │         (relevance)     vs baseline beyond tolerance                     │  model/prompt
 ├───────────────────────────────────────────────────────────────────────┤
 │ Tier 0  AUDIO QC        §3 deterministic checks (clip/DC/silence/SNR/   │  every commit
 │         (technical)     LUFS/edges/duration/NaN) — pure functions       │  (ms, unit tests)
 └───────────────────────────────────────────────────────────────────────┘
```

**Tier 0 — deterministic audio-QC unit tests (every commit, milliseconds).** The §3 checks are
pure functions over a waveform → assert on fixtures with known defects (a clipped file, a
silent file, a DC-offset file, a −14-LUFS file). No models, no network, no flakiness. This is
the "always-on, cheapest tier" — a clipping check either fires or it doesn't.

**Tier 1 — retrieval metrics on a frozen gold set (every index/model/prompt PR, seconds).**
Store the gold `qrels` (§1.3) in TREC format; on each change, run the pipeline over the gold
contexts, dump the `run`, and compute R@k / mAP@10 / nDCG@10 / MRR with **`ranx`** [5]. **Gate
the PR:** fail if any metric regresses beyond a tolerance (e.g. **Δ nDCG@10 < −0.02** vs the
committed baseline), and print a per-query diff so a real regression is legible. Keep it
**deterministic** — pin the embedding model/dim (the schema already stamps these), freeze the
library snapshot, set seeds — so a metric delta means the *system* changed, not the corpus.
This is the API-level tier the economist philosophy pushes hardest: it exercises decompose →
search → rank without a browser, a human, or a paid model call.

**Tier 2 — fit-judging + generative fidelity (nightly / pre-release, cost-gated).** Run the
§2 audio-LM listen-check and LLM-judge over a **stratified sample** of gold contexts (not all —
these cost money/latency); track mean fit score and the auto-accept rate. For generation
changes, compute **FAD-P (PANNs) / KAD** against a held-out real-SFX reference and per-sample
**PAM / Audiobox-PQ** distributions [4,19,20,21,22]. Periodically run a small **2AFC/MUSHRA
human panel** on release candidates and **re-measure judge-vs-human agreement (Krippendorff α)**
[11,23,24] so the cheap model judge stays calibrated. Guardrail: never let a Tier-2 *model*
score silently replace the human calibration slice.

**Cross-cutting harness hygiene.**
- **Snapshot/golden outputs.** For a handful of canonical contexts, commit the expected top-k
  clip ids ("golden run") and diff on every change — a fast, human-readable regression tripwire
  below even Tier-1 metrics.
- **Determinism first.** Cache embeddings and decoded arrays; fixed seeds; pinned model
  versions — flaky evals erode trust and get ignored.
- **Track deltas, not absolutes.** The gold set is small, so absolute mAP is noisy; the *sign
  and size of the change* vs the committed baseline is the signal.
- **Version everything** (encoder, index build, prompt template, gold-set revision, toolkit
  versions) in the eval report so a regression is attributable.

---

## Recommendations for `foley`

### The layered eval harness (unit QC → retrieval metrics → fit-judging)

**Tier 0 — `foley.qc` (deterministic, every commit).** A pure-function module returning a
`QCReport` per clip: `clipping`, `true_peak_dbtp`, `dc_offset`, `rms_dbfs`,
`leading/trailing_silence`, `snr_db`, `edge_click`, `loudness_lufs`, `duration_s`,
`nan_inf`, plus an overall `pass|warn|fail`. Runs on **ingest** (populating `SoundRecord`
fields + becoming search filters) and as **unit tests** against defect fixtures. Defaults from
the §3 table; every threshold a keyword override. Deps: NumPy + `soundfile` + `pyloudnorm` [17].

**Tier 1 — `foley.eval.retrieval` (every index/model/prompt PR, `ranx`).** Gold `qrels` in
TREC format, pinned to a frozen library snapshot; compute **R@1/5/10, mAP@10, nDCG@10, MRR**;
**fail the PR** on `Δ nDCG@10 < −0.02` (config). Report top-1 = "~30 %-right" context so no one
misreads a low R@1. This tier is the economist workhorse — API-level, no paid calls.

**Tier 2 — `foley.eval.fit` (nightly / pre-release, cost-gated).** Audio-LM "does this contain
{event}?" (AQAScore/Qwen2-Audio) [9,10] + LLM-judge over a stratified sample; **PAM** and
**Audiobox-PQ** per-sample gates on generations [21,22]; **FAD-P (PANNs Wavegram-Logmel) / KAD**
for backend comparison [4,19,20]; a small **2AFC/Bradley-Terry** or **MUSHRA** human panel on
release candidates, with **Krippendorff-α** judge-vs-human calibration [11,23,24].

### Specific metrics & thresholds (the defaults to ship)

- **Retrieval (primary):** nDCG@10 (graded) and mAP@10; **secondary:** R@1/R@5/R@10, MRR.
  Regression gate `Δ nDCG@10 ≥ −0.02`.
- **CLAP-score gate:** per-encoder-calibrated; below-threshold ⇒ "no match" ⇒ generate. Re-
  calibrate on every encoder swap. Use only as a *relative* signal — never as absolute truth.
- **Audio-QC:** clip-run ≥ 10 samples ⇒ reject; true-peak ≤ −1 dBTP; DC |mean| > 0.01 ⇒ fix;
  whole-clip RMS < −60 dBFS ⇒ empty; SNR > 20 dB clean / < ~10 dB advisory; edge > −40 dBFS
  rel-peak ⇒ fade; loudness outlier > ±6 LU from library median; normalize deliverables to
  −14 LUFS (default) / −16 (Apple) / −23 (broadcast).
- **Generation QC:** silent/NaN reject; CLAP-score prompt-adherence gate; PAM & Audiobox-PQ
  perceptual gates; audio-LM plausibility; FAD-P/KAD for release-level backend comparison.
- **Reliability:** Krippendorff-α ≥ 0.8 reliable / ≥ 0.667 usable for any human or model judge.

### Gold-set construction recipe (condensed)

~50–200 contexts, **stratified** by sound family × difficulty × diegetic; **two gold levels**
(query→graded-0–3 qrels for retrieval; paragraph→ideal-decomposition for the decompose step);
**pool** several retrieval configs' top-k and grade only the pool; **≥2–3 raters** with
**Krippendorff-α** adjudication; **freeze to a library snapshot** (schema already stamps
`embedding_model`/`dim`); keep a **held-out** slice; **seed** the library side from **FSD50K**
[26] + **Clotho** [8]; store as TREC `qrels` so `ranx`/`pytrec_eval` consume it directly.

### Highest-leverage bets

1. **Tier 0 audio-QC is nearly free and prevents the most embarrassing failures** (a clipped
   or silent clip under narration). Build it first; it's just range-checks on fields the
   `SoundRecord` schema already defines.
2. **The gold set is the durable asset, not the encoder.** A 100-query graded gold set makes
   every future model/index/prompt change *measurable* — spend the human hours here once.
3. **PAM + Audiobox-PQ give a cheap, no-reference, SFX-usable quality signal today** [21,22];
   adopt them as the generation gate and a library-wide QC filter before chasing the harder,
   set-level FAD/KAD comparisons.
4. **Calibrate every model judge against a human slice** and re-check on each upgrade — the
   audio-LM listen-check is what lets foley auto-accept without a human on every clip (note 05),
   but only once its agreement with humans is measured.

---

## REFERENCES

1. DCASE 2024 Challenge — Task 8: Language-Based Audio Retrieval (task + results; mAP@10 is the official ranking metric). [dcase.community](https://dcase.community/challenge2024/task-language-based-audio-retrieval-results)
2. Järvelin & Kekäläinen, *Cumulated Gain-Based Evaluation of IR Techniques* (nDCG; ACM TOIS 2002). [dl.acm.org](https://dl.acm.org/doi/10.1145/582415.582418)
3. Coralogix, *A Practical Guide to Normalized Discounted Cumulative Gain (nDCG)* (metric definition/derivation). [coralogix.com](https://coralogix.com/ai-blog/a-practical-guide-to-normalized-discounted-cumulative-gain-ndcg/)
4. Lee et al., *Sound Scene Synthesis at the DCASE 2024 Challenge* (Task 7; FAD-P = PANNs-Wavegram-Logmel FAD, human fit ratings, 36 % gap to designer reference; 2024/2025). [arxiv.org/abs/2501.08587](https://arxiv.org/abs/2501.08587) · challenge: [dcase.community](https://dcase.community/challenge2024/task-sound-scene-synthesis) · workshop: [arxiv.org/abs/2410.17589](https://arxiv.org/abs/2410.17589)
5. Bassani, *ranx: A Blazing-Fast Python Library for Ranking Evaluation and Comparison* (ECIR 2022). [github.com/AmenRa/ranx](https://github.com/AmenRa/ranx) · [springer](https://link.springer.com/chapter/10.1007/978-3-030-99739-7_30)
6. Van Gysel & de Rijke, *Pytrec_eval: An Extremely Fast Python Interface to trec_eval* (SIGIR 2018). [arxiv.org/abs/1805.01597](https://arxiv.org/abs/1805.01597) · [github.com/cvangysel/pytrec_eval](https://github.com/cvangysel/pytrec_eval)
7. Niizumi et al., *M2D-CLAP: General-purpose Audio-Language Representations Beyond CLAP* (AudioCaps R@1 numbers; 2025). [arxiv.org/abs/2503.22104](https://arxiv.org/abs/2503.22104)
8. Drossos et al., *Clotho: An Audio Captioning Dataset* (ICASSP 2020). [arxiv.org/abs/1910.09387](https://arxiv.org/abs/1910.09387)
9. Chu et al., *Qwen2-Audio: Advancing Universal Audio Understanding* (2024). [arxiv.org/abs/2311.07919](https://arxiv.org/abs/2311.07919) · [github.com/QwenLM/Qwen2-Audio](https://github.com/QwenLM/Qwen2-Audio)
10. *AQAScore: Evaluating Semantic Alignment in Text-to-Audio Generation via Audio Question Answering* (2026; "does this contain {event}?" + CLAP-score limitations). [arxiv.org/abs/2601.14728](https://arxiv.org/abs/2601.14728)
11. Krippendorff, *Computing Krippendorff's Alpha-Reliability* (2011); Hayes & Krippendorff, *Answering the Call for a Standard Reliability Measure for Coding Data* (2007); reliability cut-offs α ≥ 0.8 / ≥ 0.667. [repository.upenn.edu](https://repository.upenn.edu/asc_papers/43)
12. ITU-R BS.1770-4, *Algorithms to measure audio programme loudness and true-peak audio level* (LUFS / dBTP). [itu.int](https://www.itu.int/rec/R-REC-BS.1770)
13. EBU R 128, *Loudness Normalisation and Permitted Maximum Level of Audio Signals* (−23 LUFS, −1 dBTP). [tech.ebu.ch/docs/r/r128.pdf](https://tech.ebu.ch/docs/r/r128.pdf)
14. MasteringBOX, *Clipping in Audio: Considerations and How to Avoid It* (0 dBFS ceiling; peak/limiter thresholds). [masteringbox.com](https://www.masteringbox.com/learn/what-is-clipping)
15. AudioUtils, *What Is DC Offset in Audio? How to Detect and Fix It* (offset thresholds 0.001/0.01). [audioutils.com](https://audioutils.com/guide/what-is-dc-offset)
16. Kim & Stern, *Robust Signal-to-Noise Ratio Estimation Based on Waveform Amplitude Distribution Analysis (WADA-SNR)* (Interspeech 2008); Python impl. [github.com/hrtlacek/SNR](https://github.com/hrtlacek/SNR)
17. Steinmetz & Reiss, *pyloudnorm: A Simple Yet Flexible Loudness Meter in Python* (ITU-R BS.1770-4; AES 2021). [github.com/csteinmetz1/pyloudnorm](https://github.com/csteinmetz1/pyloudnorm) · [paper](https://csteinmetz1.github.io/pyloudnorm-eval/paper/pyloudnorm_preprint.pdf)
18. Kilgour et al., *Fréchet Audio Distance: A Reference-Free Metric for Evaluating Music Enhancement Algorithms* (Interspeech 2019). [isca-archive](https://www.isca-archive.org/interspeech_2019/kilgour19_interspeech.pdf) · [arxiv.org/abs/1812.08466](https://arxiv.org/abs/1812.08466)
19. Gui et al., *Adapting Frechet Audio Distance for Generative Music Evaluation* (Microsoft; embedding choice, sample-size bias, per-song FAD; ICASSP 2024). [arxiv.org/abs/2311.01616](https://arxiv.org/abs/2311.01616) · toolkit: [github.com/microsoft/fadtk](https://github.com/microsoft/fadtk)
20. *KAD: No More FAD! An Effective and Efficient Evaluation Metric for Audio Generation* (MMD-based, unbiased, small-sample; ICML 2025). [arxiv.org/abs/2502.15602](https://arxiv.org/abs/2502.15602) · toolkit: [github.com/YoonjinXD/kadtk](https://github.com/YoonjinXD/kadtk)
21. Tjandra et al., *Meta Audiobox Aesthetics: Unified Automatic Quality Assessment for Speech, Music, and Sound* (PQ/PC/CE/CU axes, no-reference; 2025). [arxiv.org/abs/2502.05139](https://arxiv.org/abs/2502.05139) · [github.com/facebookresearch/audiobox-aesthetics](https://github.com/facebookresearch/audiobox-aesthetics)
22. Deshmukh et al., *PAM: Prompting Audio-Language Models for Audio Quality Assessment* (no-reference, antonym-prompt CLAP; Interspeech 2024). [arxiv.org/abs/2402.00282](https://arxiv.org/abs/2402.00282) · [github.com/soham97/pam](https://github.com/soham97/pam)
23. ITU-R BS.1534-3, *Method for the Subjective Assessment of Intermediate Quality Level of Audio Systems (MUSHRA)* (hidden reference + anchor; 2015). [en.wikipedia.org/wiki/MUSHRA](https://en.wikipedia.org/wiki/MUSHRA)
24. Bradley & Terry, *Rank Analysis of Incomplete Block Designs* (Bradley–Terry model; Biometrika 1952); 2AFC + bootstrap-CI usage in modern TTS A/B. [jstor.org](https://www.jstor.org/stable/2334029) · practical: [arxiv.org/abs/2604.21481](https://arxiv.org/abs/2604.21481)
25. Wu et al., *Large-scale Contrastive Language-Audio Pretraining (LAION-CLAP)* (CLAP-score backbone; 2023). [arxiv.org/abs/2211.06687](https://arxiv.org/abs/2211.06687)
26. Fonseca et al., *FSD50K: An Open Dataset of Human-Labeled Sound Events* (CC0/CC-BY seed corpus; 2022). [arxiv.org/abs/2010.00475](https://arxiv.org/abs/2010.00475)
27. Kim et al., *AudioCaps: Generating Captions for Audios in the Wild* (NAACL 2019). [aclanthology.org/N19-1011](https://aclanthology.org/N19-1011/)
28. Microsoft Data Science, *The Path to a Golden Dataset, or How to Evaluate Your RAG?* (golden-dataset-as-regression-suite practice). [medium.com](https://medium.com/data-science-at-microsoft/the-path-to-a-golden-dataset-or-how-to-evaluate-your-rag-045e23d1f13f)
29. Thor Whalen, *arioso* — unified façade for AI music generation (generation-adapter template). [github.com/thorwhalen/arioso](https://github.com/thorwhalen/arioso)
